"""Portas de processamento de imagem (marca d'agua/metadados/C2PA)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ImageWatermarkerPort(Protocol):
    def apply(self, image_bytes: bytes) -> bytes: ...


class AiMetadataWriterPort(Protocol):
    def apply(
        self,
        image_bytes: bytes,
        *,
        model_name: str,
        created_at: datetime | None = None,
    ) -> bytes: ...


class C2PASignerPort(Protocol):
    def sign(self, image_bytes: bytes) -> bytes: ...
