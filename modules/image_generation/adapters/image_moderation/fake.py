"""Fake de moderacao visual para testes e modo de desenvolvimento."""

from __future__ import annotations

from modules.image_generation.application.ports.image_moderation import (
    ImageModerationResult,
    ImageModerationScores,
    ImageModerationThresholds,
    decide_image_moderation,
)


class FakeImageModerator:
    def __init__(
        self,
        scores: ImageModerationScores | None = None,
        thresholds: ImageModerationThresholds | None = None,
    ) -> None:
        self.scores = scores or ImageModerationScores()
        self.thresholds = thresholds or ImageModerationThresholds()
        self.calls = 0

    async def moderate(self, image_bytes: bytes) -> ImageModerationResult:
        self.calls += 1
        return decide_image_moderation(self.scores, self.thresholds)
