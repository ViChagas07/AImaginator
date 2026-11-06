"""Ampliacao 2x: Pillow Lanczos e ESRGAN via sd-cli (lazy/fake-testable)."""

from __future__ import annotations

import asyncio
import contextlib
import io
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Protocol

from PIL import Image

from modules.image_generation.application.ports.image_engine import EngineImage
from modules.image_generation.domain.engine_errors import (
    EngineFailedError,
    EngineOutOfMemoryError,
    EngineTimeoutError,
    InsufficientResourcesError,
)
from modules.observability.metrics import ENGINE_PEAK_RAM_BYTES, RAM_FREE_BYTES


class UpscaleSettings(Protocol):
    sdcpp_binary_path: str
    sdcpp_upscale_model_path: str
    upscale_timeout_seconds: int
    min_free_ram_mb: int
    cooldown_seconds_between_jobs: float


def build_esrgan_command(
    *,
    binary_path: str,
    model_path: str,
    input_path: str,
    output_path: str,
) -> list[str]:
    """argv do sd-cli para upscale; sem shell e com paths como argumentos."""
    return [
        binary_path,
        "--upscale-model",
        model_path,
        "--upscale-repeats",
        "1",
        "-i",
        input_path,
        "-o",
        output_path,
    ]


class LanczosUpscaler:
    def __init__(self, *, factor: int = 2) -> None:
        self._factor = factor

    async def upscale(self, image_bytes: bytes, *, factor: int = 2) -> EngineImage:
        return await asyncio.to_thread(self._upscale_sync, image_bytes, factor)

    def _upscale_sync(self, image_bytes: bytes, factor: int) -> EngineImage:
        started = time.monotonic()
        source = Image.open(io.BytesIO(image_bytes))
        source.load()
        target = (source.width * factor, source.height * factor)
        resized = source.resize(target, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        resized.save(out, format="PNG")
        return EngineImage(
            image_bytes=out.getvalue(),
            width=target[0],
            height=target[1],
            seed=0,
            duration_seconds=round(time.monotonic() - started, 3),
        )


class EsrganUpscaler:
    def __init__(
        self,
        settings: UpscaleSettings,
        *,
        available_ram_mb_fn=None,
        sleep_fn=None,
    ) -> None:
        self._settings = settings
        self._available_ram_mb = available_ram_mb_fn or _available_ram_mb
        self._sleep = sleep_fn or asyncio.sleep

    async def upscale(self, image_bytes: bytes, *, factor: int = 2) -> EngineImage:
        free_mb = self._available_ram_mb()
        RAM_FREE_BYTES.labels(kind="upscale").set(free_mb * 1024 * 1024)
        if free_mb < self._settings.min_free_ram_mb:
            raise InsufficientResourcesError()
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="aimaginator-upscale-") as temp:
            if os.name != "nt":
                os.chmod(temp, 0o700)
            source_path = Path(temp) / "source.png"
            output_path = Path(temp) / "upscaled.png"
            source_path.write_bytes(image_bytes)
            command = build_esrgan_command(
                binary_path=self._settings.sdcpp_binary_path,
                model_path=self._settings.sdcpp_upscale_model_path,
                input_path=str(source_path),
                output_path=str(output_path),
            )
            try:
                await self._execute(command)
            finally:
                if self._settings.cooldown_seconds_between_jobs > 0:
                    await self._sleep(self._settings.cooldown_seconds_between_jobs)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise EngineFailedError()
            data = output_path.read_bytes()
        meta = Image.open(io.BytesIO(data))
        return EngineImage(
            image_bytes=data,
            width=meta.width,
            height=meta.height,
            seed=0,
            duration_seconds=round(time.monotonic() - started, 3),
        )

    async def _execute(self, command: list[str]) -> None:
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
                self._consume(process, output),
                timeout=self._settings.upscale_timeout_seconds,
            )
            returncode = await process.wait()
        except TimeoutError:
            await self._kill_tree(process)
            raise EngineTimeoutError() from None
        finally:
            sampler.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                peak_ram = await sampler
            ENGINE_PEAK_RAM_BYTES.labels(kind="upscale").observe(peak_ram)
        if returncode != 0:
            lowered = "".join(output).lower()
            if "out of memory" in lowered or "failed to allocate" in lowered:
                raise EngineOutOfMemoryError()
            raise EngineFailedError()

    async def _consume(self, process, output: list[str]) -> None:
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            output.append(line.decode("utf-8", errors="replace"))

    async def _sample_peak_ram(self, process) -> int:
        import psutil

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

    async def _kill_tree(self, process) -> None:
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


def _available_ram_mb() -> int:
    import psutil

    return int(psutil.virtual_memory().available // (1024 * 1024))
