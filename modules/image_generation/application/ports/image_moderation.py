"""Moderacao visual: scores por categoria e decisao em codigo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from modules.image_generation.domain.moderation import ModerationCategory


@dataclass(frozen=True, slots=True)
class ImageModerationScores:
    sexual: float = 0.0
    gore: float = 0.0
    hate: float = 0.0
    self_harm: float = 0.0


@dataclass(frozen=True, slots=True)
class ImageModerationThresholds:
    sexual: float = 0.5
    gore: float = 0.5
    hate: float = 0.5
    self_harm: float = 0.5


@dataclass(frozen=True, slots=True)
class ImageModerationResult:
    scores: ImageModerationScores = field(default_factory=ImageModerationScores)
    blocked_category: ModerationCategory | None = None

    @property
    def blocked(self) -> bool:
        return self.blocked_category is not None


_PRIORITY = (
    ModerationCategory.NSFW,
    ModerationCategory.GORE,
    ModerationCategory.HATE,
    ModerationCategory.SELF_HARM,
)


def decide_image_moderation(
    scores: ImageModerationScores,
    thresholds: ImageModerationThresholds,
) -> ImageModerationResult:
    """Bloqueia a categoria de maior prioridade que cruzou o limiar."""
    values = {
        ModerationCategory.NSFW: (scores.sexual, thresholds.sexual),
        ModerationCategory.GORE: (scores.gore, thresholds.gore),
        ModerationCategory.HATE: (scores.hate, thresholds.hate),
        ModerationCategory.SELF_HARM: (scores.self_harm, thresholds.self_harm),
    }
    for category in _PRIORITY:
        score, threshold = values[category]
        if score >= threshold:
            return ImageModerationResult(scores=scores, blocked_category=category)
    return ImageModerationResult(scores=scores, blocked_category=None)


class ImageModeratorPort(Protocol):
    async def moderate(self, image_bytes: bytes) -> ImageModerationResult:
        """Classifica a imagem; falhas reais devem levantar erro de indisponibilidade."""
        ...
