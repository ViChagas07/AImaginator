"""Presets deterministicos: composicao e lista fechada."""

from __future__ import annotations

import pytest

from modules.image_generation.domain.entities import StylePreset
from modules.image_generation.domain.style_presets import (
    STYLE_FRAGMENTS,
    apply_style_preset,
)


@pytest.mark.unit
def test_none_nao_altera_prompt() -> None:
    assert apply_style_preset("um castelo", StylePreset.NONE) == "um castelo"


@pytest.mark.unit
def test_preset_anexa_fragmento_ingles() -> None:
    result = apply_style_preset("um castelo", StylePreset.WATERCOLOR)
    assert result.startswith("um castelo,")
    assert "watercolor painting" in result


@pytest.mark.unit
def test_catalogo_e_fechado_e_nao_tem_fragmento_vazio() -> None:
    assert set(STYLE_FRAGMENTS) == set(StylePreset)
    assert all(
        fragment for preset, fragment in STYLE_FRAGMENTS.items() if preset is not StylePreset.NONE
    )


@pytest.mark.unit
def test_preset_desconhecido_e_rejeitado() -> None:
    with pytest.raises(ValueError):
        apply_style_preset("x", "unknown")  # type: ignore[arg-type]
