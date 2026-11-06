"""Porta de ampliacao de imagem (Lanczos ou ESRGAN)."""

from __future__ import annotations

from typing import Protocol

from modules.image_generation.application.ports.image_engine import EngineImage


class UpscalerPort(Protocol):
    async def upscale(self, image_bytes: bytes, *, factor: int = 2) -> EngineImage: ...
