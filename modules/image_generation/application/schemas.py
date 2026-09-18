"""Schemas Pydantic de entrada/saida do modulo (fronteira da API).

Regra (spec secao 9.1): nunca expor modelo ORM na API — estes schemas
sao o contrato de transporte, validados na borda.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from modules.image_generation.domain.entities import (
    AspectRatio,
    GenerationKind,
    GenerationStatus,
    StylePreset,
)

MAX_PROMPT_LENGTH = 2000


class GenerateImageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_LENGTH)
    negative_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_LENGTH)
    style_preset: StylePreset = StylePreset.NONE
    aspect_ratio: AspectRatio = AspectRatio.SQUARE
    title: str | None = Field(default=None, max_length=200)


class EditImageInput(GenerateImageInput):
    source_image_url: HttpUrl  # validada pela guarda anti-SSRF no use case


class RenameGenerationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)


class GenerationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: GenerationKind
    status: GenerationStatus
    prompt: str
    style_preset: StylePreset
    aspect_ratio: AspectRatio
    title: str | None = None
    result_image_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    stream_url: str | None = None


class GenerationPage(BaseModel):
    """Paginacao por cursor (spec secao 16)."""

    items: list[GenerationOutput]
    next_cursor: str | None


class GalleryArtOutput(BaseModel):
    """Arte exposta na galeria (pessoal/publica) — contrato do frontend."""

    id: UUID
    image_url: str | None = Field(default=None, serialization_alias="imageUrl")
    prompt: str
    title: str | None = None
    status: GenerationStatus
    created_at: datetime = Field(serialization_alias="createdAt")


class GalleryPage(BaseModel):
    items: list[GalleryArtOutput]
    cursor: str | None


class GenerationProgressEvent(BaseModel):
    """Evento publicado no Redis Pub/Sub e repassado via SSE."""

    generation_id: UUID
    status: GenerationStatus
    progress: int = Field(ge=0, le=100, default=0)
    result_image_url: str | None = None
    error: str | None = None
