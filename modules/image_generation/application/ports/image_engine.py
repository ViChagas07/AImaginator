"""Portas do motor de imagem: geracao e edicao separadas por kind.

Os adapters devolvem os bytes da imagem e metadados (largura, altura, seed e
duracao). O storage e a apresentacao (URL assinada) ficam fora destas portas.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from modules.image_generation.domain.entities import Generation

ProgressCallback = Callable[[int], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class EngineImage:
    """Resultado cru do motor de imagem."""

    image_bytes: bytes
    width: int
    height: int
    seed: int
    duration_seconds: float
    content_type: str = "image/png"


class ImageGeneratorPort(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int | None,
        on_progress: ProgressCallback,
    ) -> EngineImage:
        """Gera uma imagem nova a partir do prompt."""
        ...


class ImageEditorPort(Protocol):
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
        """Edita uma imagem de origem ja validada."""
        ...


class ImagePostProcessor(Protocol):
    """Ponto de extensao para marca d'agua e moderacao de imagem."""

    def process(self, image: EngineImage, generation: Generation) -> EngineImage:
        """Recebe e devolve a imagem; deve preservar as dimensoes."""
        ...
