"""Entidades de dominio do modulo image_generation — puras, sem framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class GenerationKind(StrEnum):
    GENERATE = "generate"
    EDIT = "edit"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class StylePreset(StrEnum):
    NONE = "none"
    PHOTOREALISTIC = "photorealistic"
    ANIME = "anime"
    OIL_PAINTING = "oil_painting"
    CYBERPUNK = "cyberpunk"
    WATERCOLOR = "watercolor"
    ISOMETRIC_3D = "isometric_3d"


class AspectRatio(StrEnum):
    SQUARE = "1:1"
    PORTRAIT = "3:4"
    LANDSCAPE = "16:9"
    TALL = "9:16"


# Transicoes de status validas (maquina de estados do dominio).
_ALLOWED_TRANSITIONS: dict[GenerationStatus, frozenset[GenerationStatus]] = {
    GenerationStatus.QUEUED: frozenset({GenerationStatus.PROCESSING, GenerationStatus.FAILED}),
    GenerationStatus.PROCESSING: frozenset({GenerationStatus.DONE, GenerationStatus.FAILED}),
    GenerationStatus.DONE: frozenset(),
    GenerationStatus.FAILED: frozenset(),
}


@dataclass(slots=True)
class Generation:
    """Uma geracao/edicao de imagem pedida por um usuario."""

    user_id: UUID
    kind: GenerationKind
    prompt: str
    negative_prompt: str | None = None
    style_preset: StylePreset = StylePreset.NONE
    aspect_ratio: AspectRatio = AspectRatio.SQUARE
    source_image_url: str | None = None
    result_image_url: str | None = None
    error_message: str | None = None
    status: GenerationStatus = GenerationStatus.QUEUED
    credits_cost: int = 1
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def transition_to(self, new_status: GenerationStatus, *, error: str | None = None) -> None:
        """Maquina de estados: transicoes invalidas sao erro de dominio."""
        from shared_kernel.errors import DomainError

        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            msg = f"Transicao invalida: {self.status} -> {new_status}"
            raise DomainError(msg)
        self.status = new_status
        self.error_message = error
        self.updated_at = datetime.now(UTC)
        if new_status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            self.completed_at = self.updated_at

    def attach_result(self, image_url: str) -> None:
        self.result_image_url = image_url
        self.transition_to(GenerationStatus.DONE)
