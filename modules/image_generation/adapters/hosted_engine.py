"""Motor HTTP hospedado (esqueleto; nenhum provedor real em teste)."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

from modules.image_generation.application.ports.image_engine import (
    EngineImage,
    ProgressCallback,
)
from shared_kernel.security_errors import EngineOfflineError


class HttpHostedEngine:
    """Contrato simples: POST inicia; GET /jobs/{id} faz polling."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        api_key: str = "",
        generate_path: str = "/generate",
        edit_path: str = "/edit",
        poll_interval_seconds: float = 1.0,
        timeout_seconds: float = 600.0,
    ) -> None:
        self._http = http_client
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._generate_path = generate_path
        self._edit_path = edit_path
        self._poll_interval = poll_interval_seconds
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int | None,
        on_progress: ProgressCallback,
    ) -> EngineImage:
        return await self._run(
            self._generate_path,
            {"prompt": prompt, "width": width, "height": height, "seed": seed},
            on_progress,
        )

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
        return await self._run(
            self._edit_path,
            {
                "prompt": prompt,
                "source_image_base64": base64.b64encode(source_image).decode(),
                "width": width,
                "height": height,
                "seed": seed,
            },
            on_progress,
        )

    async def _run(
        self, path: str, payload: dict[str, Any], on_progress: ProgressCallback
    ) -> EngineImage:
        started = time.monotonic()
        try:
            response = await self._http.post(
                f"{self._base}{path}",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise EngineOfflineError("Motor hospedado indisponivel.") from exc

        if "image_base64" in data:
            return self._to_image(data, started)
        job_id = data.get("job_id")
        if not job_id:
            raise EngineOfflineError("Motor hospedado nao retornou job_id.")

        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll_interval)
            try:
                poll = await self._http.get(
                    f"{self._base}/jobs/{job_id}",
                    headers=self._headers(),
                    timeout=self._timeout,
                )
                poll.raise_for_status()
                data = poll.json()
            except httpx.HTTPError as exc:
                raise EngineOfflineError("Falha no polling do motor hospedado.") from exc
            status = str(data.get("status", "")).lower()
            if status in {"failed", "error", "cancelled"}:
                raise EngineOfflineError("Motor hospedado falhou.")
            if status in {"done", "completed", "succeeded"} and "image_base64" in data:
                await on_progress(90)
                return self._to_image(data, started)
            progress = data.get("progress")
            if isinstance(progress, int | float):
                await on_progress(max(10, min(90, int(progress))))
        raise EngineOfflineError("Timeout do motor hospedado.")

    @staticmethod
    def _to_image(data: dict, started: float) -> EngineImage:
        try:
            image_bytes = base64.b64decode(data["image_base64"], validate=True)
        except (KeyError, ValueError) as exc:
            raise EngineOfflineError("Resposta invalida do motor hospedado.") from exc
        return EngineImage(
            image_bytes=image_bytes,
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            seed=int(data.get("seed", 0)),
            duration_seconds=round(time.monotonic() - started, 3),
            content_type=str(data.get("content_type", "image/png")),
        )


class FallbackGenerator:
    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    async def generate(self, **kwargs):
        try:
            return await self._primary.generate(**kwargs)
        except EngineOfflineError:
            return await self._fallback.generate(**kwargs)


class FallbackEditor:
    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    async def edit(self, **kwargs):
        try:
            return await self._primary.edit(**kwargs)
        except EngineOfflineError:
            return await self._fallback.edit(**kwargs)
