"""Testes das constantes de dominio de proporcao (Fase 2, Bloco 2)."""

from __future__ import annotations

import pytest

from modules.image_generation.domain.entities import (
    ASPECT_RATIO_DIMENSIONS,
    AspectRatio,
)


@pytest.mark.unit
def test_proporcoes_permitidas_tem_dimensoes_canonicas() -> None:
    assert ASPECT_RATIO_DIMENSIONS == {
        AspectRatio.SQUARE: (512, 512),
        AspectRatio.FOUR_THREE: (576, 448),
        AspectRatio.PORTRAIT: (448, 576),
        AspectRatio.LANDSCAPE: (704, 384),
        AspectRatio.TALL: (384, 704),
    }


@pytest.mark.unit
def test_todas_as_proporcoes_do_enum_tem_dimensao() -> None:
    assert set(ASPECT_RATIO_DIMENSIONS) == set(AspectRatio)
    assert AspectRatio.FOUR_THREE.value == "4:3"
    for width, height in ASPECT_RATIO_DIMENSIONS.values():
        assert width > 0
        assert height > 0
