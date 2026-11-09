"""Resultado e regras de decisao do assistente de prompts (puro dominio)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from modules.image_generation.domain.entities import AspectRatio, GenerationKind


class BlockedCategory(StrEnum):
    NSFW = "nsfw"
    GORE = "gore"
    HATE = "hate"
    SELF_HARM = "self_harm"


_BLOCKED_CODE = {
    BlockedCategory.NSFW: "content_blocked_nsfw",
    BlockedCategory.GORE: "content_blocked_gore",
    BlockedCategory.HATE: "content_blocked_hate",
    BlockedCategory.SELF_HARM: "content_blocked_self_harm",
}

# Prioridade de recusa quando mais de uma flag vem verdadeira:
# sexual > hate > gore > self_harm.
_PRIORITY = (
    BlockedCategory.NSFW,
    BlockedCategory.HATE,
    BlockedCategory.GORE,
    BlockedCategory.SELF_HARM,
)


@dataclass(frozen=True, slots=True)
class AssistantInput:
    text: str
    kind: GenerationKind
    locale: str = "pt-BR"
    previous_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ModerationFlags:
    sexual: bool = False
    gore: bool = False
    hate: bool = False
    self_harm: bool = False

    def enabled_categories(self) -> tuple[BlockedCategory, ...]:
        mapping = (
            (BlockedCategory.NSFW, self.sexual),
            (BlockedCategory.HATE, self.hate),
            (BlockedCategory.GORE, self.gore),
            (BlockedCategory.SELF_HARM, self.self_harm),
        )
        return tuple(category for category, enabled in mapping if enabled)

    def derived_category(self) -> BlockedCategory | None:
        """Categoria decidida pelos booleanos, na prioridade de recusa."""
        for category in _PRIORITY:
            if category in self.enabled_categories():
                return category
        return None


@dataclass(frozen=True, slots=True)
class AssistantResult:
    detected_language: str
    is_image_request: bool
    in_scope: bool
    moderation: ModerationFlags
    blocked_category: BlockedCategory | None
    confidence: float
    image_part_extracted: str | None
    corrected_text: str | None
    flux_prompt: str | None
    kontext_instruction: str | None
    suggested_aspect_ratio: AspectRatio | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)

    def engine_prompt(self, kind: GenerationKind) -> str:
        if kind is GenerationKind.EDIT:
            return (
                self.kontext_instruction or self.flux_prompt or self.corrected_text or ""
            ).strip()
        return (self.flux_prompt or self.corrected_text or "").strip()

    def moderation_category(self, *, block_confidence: float) -> BlockedCategory | None:
        if self.confidence < block_confidence:
            return None
        # Booleanos vencem o campo declarado pelo modelo. O campo so e usado
        # como fallback quando nenhum booleano veio true (inconsistencia).
        derived = self.moderation.derived_category()
        if derived is not None:
            return derived
        if self.blocked_category is not None:
            return self.blocked_category
        return None

    def refusal_code(self, *, block_confidence: float) -> str | None:
        """Decisao em codigo: moderacao de alta confianca e escopo.

        O LLM nao decide sozinho: flags abaixo do limiar nao bloqueiam.
        """
        category = self.moderation_category(block_confidence=block_confidence)
        if category is not None:
            return _BLOCKED_CODE[category]
        if not self.in_scope or not self.is_image_request:
            return "out_of_scope"
        return None

    @property
    def is_penalizable(self) -> bool:
        """Escopo/injecao nao geram penalidade; moderacao sim."""
        return bool(self.moderation.enabled_categories()) or self.blocked_category is not None
