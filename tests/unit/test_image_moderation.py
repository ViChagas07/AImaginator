"""Moderacao visual: limiares, fake e fail-closed do adapter local."""

from __future__ import annotations

import pytest

from modules.image_generation.adapters.image_moderation.fake import FakeImageModerator
from modules.image_generation.adapters.image_moderation.local import LocalImageModerator
from modules.image_generation.application.ports.image_moderation import (
    ImageModerationScores,
    ImageModerationThresholds,
    decide_image_moderation,
)
from modules.image_generation.domain.moderation import ModerationCategory
from shared_kernel.security_errors import ImageModerationUnavailableError

_THRESHOLDS = ImageModerationThresholds(
    sexual=0.5, gore=0.5, hate=0.5, self_harm=0.5
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "category"),
    [
        ("sexual", ModerationCategory.NSFW),
        ("gore", ModerationCategory.GORE),
        ("hate", ModerationCategory.HATE),
        ("self_harm", ModerationCategory.SELF_HARM),
    ],
)
def test_cada_categoria_acima_e_abaixo_do_limiar(field, category) -> None:
    below = decide_image_moderation(
        ImageModerationScores(**{field: 0.49}), _THRESHOLDS
    )
    above = decide_image_moderation(
        ImageModerationScores(**{field: 0.5}), _THRESHOLDS
    )
    assert below.blocked_category is None
    assert above.blocked_category is category


@pytest.mark.unit
def test_prioridade_nsfw_sobre_as_demais() -> None:
    result = decide_image_moderation(
        ImageModerationScores(sexual=0.9, gore=0.9, hate=0.9, self_harm=0.9),
        _THRESHOLDS,
    )
    assert result.blocked_category is ModerationCategory.NSFW


@pytest.mark.unit
async def test_fake_moderator_retorna_scores_e_decisao() -> None:
    moderator = FakeImageModerator(
        scores=ImageModerationScores(gore=0.8), thresholds=_THRESHOLDS
    )
    result = await moderator.moderate(b"image")
    assert result.blocked_category is ModerationCategory.GORE
    assert moderator.calls == 1


@pytest.mark.unit
async def test_local_sem_pesos_falha_fechado(tmp_path) -> None:
    moderator = LocalImageModerator(
        nsfw_model_path=str(tmp_path / "nsfw"),
        clip_model_path=str(tmp_path / "clip"),
    )
    with pytest.raises(ImageModerationUnavailableError):
        await moderator.moderate(b"not-an-image")
