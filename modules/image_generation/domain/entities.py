"""Entidades de dominio do modulo image_generation — puras, sem framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class GenerationKind(StrEnum):
    GENERATE = "generate"
    EDIT = "edit"
    UPSCALE = "upscale"


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
    FOUR_THREE = "4:3"
    PORTRAIT = "3:4"
    LANDSCAPE = "16:9"
    TALL = "9:16"


# Dimensoes canonicas por proporcao (constantes de dominio; tempos ainda a validar).
ASPECT_RATIO_DIMENSIONS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.SQUARE: (512, 512),
    AspectRatio.FOUR_THREE: (576, 448),
    AspectRatio.PORTRAIT: (448, 576),
    AspectRatio.LANDSCAPE: (704, 384),
    AspectRatio.TALL: (384, 704),
}


# Transicoes de status validas (maquina de estados do dominio).
_ALLOWED_TRANSITIONS: dict[GenerationStatus, frozenset[GenerationStatus]] = {
    GenerationStatus.QUEUED: frozenset({GenerationStatus.PROCESSING, GenerationStatus.FAILED}),
    GenerationStatus.PROCESSING: frozenset({GenerationStatus.DONE, GenerationStatus.FAILED}),
    GenerationStatus.DONE: frozenset(),
    GenerationStatus.FAILED: frozenset(),
}


@dataclass(slots=True)
class Generation:
    """Uma geracao/edicao de imagem pedida por um usuario (ou anonimo)."""

    user_id: UUID | None
    kind: GenerationKind
    prompt: str
    negative_prompt: str | None = None
    style_preset: StylePreset = StylePreset.NONE
    aspect_ratio: AspectRatio = AspectRatio.SQUARE
    source_image_url: str | None = None
    source_object_key: str | None = None
    result_image_url: str | None = None
    original_object_key: str | None = None
    result_object_key: str | None = None
    parent_generation_id: UUID | None = None
    error_message: str | None = None
    error_code: str | None = None
    warning_level: int | None = None
    warning_message: str | None = None
    title: str | None = None
    seed: int | None = None
    locale: str = "pt-BR"
    ip_hash: str | None = None
    quota_refunded: bool = False
    credits_refunded: bool = False
    upscale_refunded: bool = False
    anonymous_session_id: str | None = None
    deleted_at: datetime | None = None
    status: GenerationStatus = GenerationStatus.QUEUED
    credits_cost: int = 1
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def belongs_to(self, user_id: UUID | None, *, anonymous_session_id: str | None = None) -> bool:
        """True se o owner declarado e dono desta geracao."""
        if self.user_id is not None:
            return self.user_id == user_id
        return self.anonymous_session_id == anonymous_session_id

    def rename(self, title: str) -> None:
        self.title = title.strip()
        self.updated_at = datetime.now(UTC)

    def transition_to(
        self,
        new_status: GenerationStatus,
        *,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Maquina de estados: transicoes invalidas sao erro de dominio."""
        from shared_kernel.errors import DomainError

        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            msg = f"Transicao invalida: {self.status} -> {new_status}"
            raise DomainError(msg)
        self.status = new_status
        self.error_message = error
        self.error_code = error_code
        self.updated_at = datetime.now(UTC)
        if new_status in (GenerationStatus.DONE, GenerationStatus.FAILED):
            self.completed_at = self.updated_at

    def attach_result(self, image_url: str, *, object_key: str | None = None) -> None:
        self.result_image_url = image_url
        if object_key is not None:
            self.result_object_key = object_key
        self.transition_to(GenerationStatus.DONE)
