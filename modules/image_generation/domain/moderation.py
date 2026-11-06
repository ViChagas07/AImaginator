"""Entidades e regras de moderacao/penalidade (dominio puro)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ModerationCategory(StrEnum):
    NSFW = "nsfw"
    GORE = "gore"
    HATE = "hate"
    SELF_HARM = "self_harm"


class ModerationLayer(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    IMAGE_INPUT = "image_input"
    IMAGE_OUTPUT = "image_output"


CATEGORY_REFUSAL_CODE = {
    ModerationCategory.NSFW: "content_blocked_nsfw",
    ModerationCategory.GORE: "content_blocked_gore",
    ModerationCategory.HATE: "content_blocked_hate",
    ModerationCategory.SELF_HARM: "content_blocked_self_harm",
}


@dataclass(frozen=True, slots=True)
class ModerationEvent:
    category: ModerationCategory
    layer: ModerationLayer
    confidence: float
    locale: str
    prompt_hash: str
    prompt_length: int
    user_id: UUID | None = None
    anonymous_session_id: str | None = None
    ip_hash: str | None = None
    prompt_text: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PenaltyOutcome:
    level: int
    warning_level: int | None
    warning_message: str | None
    blocked_until: datetime | None = None
