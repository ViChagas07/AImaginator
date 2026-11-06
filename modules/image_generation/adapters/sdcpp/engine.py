"""Execucao do sd-cli com timeout por kind, kill da arvore e progresso real."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import secrets
import signal
import subprocess
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

import psutil

from modules.image_generation.adapters.sdcpp.command import (
    build_sdcpp_command,
    ensure_allowed_dimensions,
)
from modules.image_generation.adapters.sdcpp.progress import (
    parse_progress_line,
    progress_for_step,
)
from modules.image_generation.application.ports import EngineImage, ProgressCallback
from modules.image_generation.domain.engine_errors import (
    EngineFailedError,
    EngineOutOfMemoryError,
    EngineTimeoutError,
    InsufficientResourcesError,
)
from modules.image_generation.domain.image_bytes import JPEG_SIGNATURE
from modules.observability.metrics import ENGINE_PEAK_RAM_BYTES, RAM_FREE_BYTES

logger = logging.getLogger(__name__)

_OOM_MARKERS = ("out of memory", "failed to allocate")
_MAX_CAPTURED_LOG_CHARS = 200_000


class SdCppSettings(Protocol):
    sdcpp_binary_path: str
    sdcpp_vae_path: str
    sdcpp_clip_l_path: str
    sdcpp_t5xxl_path: str
    sdcpp_gen_model_path: str
    sdcpp_edit_model_path: str
    gen_width: int
    gen_height: int
    gen_steps: int
    gen_guidance: float
    edit_width: int
    edit_height: int
    edit_steps: int
    edit_guidance: float
    generation_timeout_seconds: int
    edit_timeout_seconds: int
    min_free_ram_mb: int
    cooldown_seconds_between_jobs: float


def available_ram_mb() -> int:
    return int(psutil.virtual_memory().available // (1024 * 1024))


class _SdCppBase:
    _timeout_setting = "generation_timeout_seconds"
    _kind = "generate"

    def __init__(
        self,
        settings: SdCppSettings,
        *,
        available_ram_mb_fn: Callable[[], int] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._settings = settings
        self._available_ram_mb = available_ram_mb_fn or available_ram_mb
        self._sleep = sleep_fn or asyncio.sleep

    def _check_resources(self) -> None:
        free_mb = self._available_ram_mb()
        RAM_FREE_BYTES.labels(kind=self._kind).set(free_mb * 1024 * 1024)
        if free_mb < self._settings.min_free_ram_mb:
            logger.warning(
                "sdcpp_insufficient_ram",
                extra={"free_mb": free_mb, "required_mb": self._settings.min_free_ram_mb},
            )
            raise InsufficientResourcesError()

    @property
    def _timeout_seconds(self) -> float:
        return float(getattr(self._settings, self._timeout_setting))

    async def _run_engine(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        diffusion_model_path: str,
        seed: int | None,
        on_progress: ProgressCallback,
        source_image: bytes | None = None,
    ) -> EngineImage:
        ensure_allowed_dimensions(width, height)
        self._check_resources()

        resolved_seed = seed if seed is not None else secrets.randbelow(2**32)
        started_at = time.monotonic()
        await on_progress(10)

        try:
            with tempfile.TemporaryDirectory(prefix="aimaginator-sdcpp-") as temp_dir:
                if os.name != "nt":
                    os.chmod(temp_dir, 0o700)
                output_path = str(Path(temp_dir) / "result.png")
                source_path = None
                if source_image is not None:
                    suffix = ".jpg" if source_image.startswith(JPEG_SIGNATURE) else ".png"
                    source_file = Path(temp_dir) / f"source{suffix}"
                    source_file.write_bytes(source_image)
                    source_path = str(source_file)

                command = build_sdcpp_command(
                    binary_path=self._settings.sdcpp_binary_path,
                    vae_path=self._settings.sdcpp_vae_path,
                    clip_l_path=self._settings.sdcpp_clip_l_path,
                    t5xxl_path=self._settings.sdcpp_t5xxl_path,
                    diffusion_model_path=diffusion_model_path,
                    prompt=prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    guidance=guidance,
                    seed=resolved_seed,
                    output_path=output_path,
                    source_image_path=source_path,
                )
                await self._execute(
                    command, max_seconds=self._timeout_seconds, on_progress=on_progress
                )

                result_path = Path(output_path)
                if not result_path.exists() or result_path.stat().st_size == 0:
                    raise EngineFailedError()
                image_bytes = result_path.read_bytes()
        finally:
            await self._cooldown()

        return EngineImage(
            image_bytes=image_bytes,
            width=width,
            height=height,
            seed=resolved_seed,
            duration_seconds=round(time.monotonic() - started_at, 3),
        )

    async def _execute(
        self, command: list[str], *, max_seconds: float, on_progress: ProgressCallback
    ) -> None:

        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=creationflags,
        )
        output: list[str] = []
        peak_ram = 0
        sampler = asyncio.create_task(self._sample_peak_ram(process))
        try:
            await asyncio.wait_for(
                self._consume_output(process, output, on_progress), timeout=max_seconds
            )
            returncode = await process.wait()
        except TimeoutError:
            await self._kill_process_tree(process)
            logger.error(
                "sdcpp_timeout",
                extra={
                    "timeout_seconds": max_seconds,
                    "output": "".join(output)[-_MAX_CAPTURED_LOG_CHARS:],
                },
            )
            raise EngineTimeoutError() from None
        finally:
            sampler.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                peak_ram = await sampler
            ENGINE_PEAK_RAM_BYTES.labels(kind=self._kind).observe(peak_ram)

        full_output = "".join(output)
        if returncode != 0:
            logger.error(
                "sdcpp_failed",
                extra={
                    "returncode": returncode,
                    "output": full_output[-_MAX_CAPTURED_LOG_CHARS:],
                },
            )
            if self._looks_like_oom(full_output):
                raise EngineOutOfMemoryError()
            raise EngineFailedError()

    async def _consume_output(
        self,
        process: asyncio.subprocess.Process,
        output: list[str],
        on_progress: ProgressCallback,
    ) -> None:
        last_progress = 10
        assert process.stdout is not None
        while True:
            raw_line = await process.stdout.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace")
            output.append(line)
            parsed = parse_progress_line(line)
            if parsed is None:
                continue
            mapped = progress_for_step(parsed)
            if mapped > last_progress:
                last_progress = mapped
                await on_progress(mapped)

    async def _sample_peak_ram(self, process) -> int:
        peak = 0
        try:
            root = psutil.Process(process.pid)
        except (psutil.NoSuchProcess, ValueError):
            return 0
        while process.returncode is None:
            try:
                total = root.memory_info().rss
                total += sum(
                    child.memory_info().rss
                    for child in root.children(recursive=True)
                    if child.is_running()
                )
                peak = max(peak, int(total))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            await asyncio.sleep(0.5)
        return peak

    async def _kill_process_tree(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            if os.name == "nt":
                await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=10)

    async def _cooldown(self) -> None:
        seconds = float(self._settings.cooldown_seconds_between_jobs)
        if seconds > 0:
            logger.info("sdcpp_cooldown", extra={"seconds": seconds})
            await self._sleep(seconds)

    @staticmethod
    def _looks_like_oom(output: str) -> bool:
        lowered = output.lower()
        return any(marker in lowered for marker in _OOM_MARKERS)


class SdCppImageGenerator(_SdCppBase):
    """Geracao FLUX.1 Dev (Q4_K_S no spike)."""

    _timeout_setting = "generation_timeout_seconds"

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int | None,
        on_progress: ProgressCallback,
    ) -> EngineImage:
        return await self._run_engine(
            prompt=prompt,
            width=width or self._settings.gen_width,
            height=height or self._settings.gen_height,
            steps=self._settings.gen_steps,
            guidance=self._settings.gen_guidance,
            diffusion_model_path=self._settings.sdcpp_gen_model_path,
            seed=seed,
            on_progress=on_progress,
        )


class SdCppImageEditor(_SdCppBase):
    """Edicao FLUX Kontext dev (Q4_0 no spike)."""

    _timeout_setting = "edit_timeout_seconds"
    _kind = "edit"

    async def edit(
        self,
        *,
        prompt: str,
        source_image: bytes,
        width: int,
        height: int,
        seed: int | None,
        on_progress: ProgressCallback,
    ) -> EngineImage:
        return await self._run_engine(
            prompt=prompt,
            width=width or self._settings.edit_width,
            height=height or self._settings.edit_height,
            steps=self._settings.edit_steps,
            guidance=self._settings.edit_guidance,
            diffusion_model_path=self._settings.sdcpp_edit_model_path,
            seed=seed,
            on_progress=on_progress,
            source_image=source_image,
        )
