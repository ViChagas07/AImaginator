"""Testes do timeout do SSE derivado das configuracoes (Fase 2, Bloco 4)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.image_generation.application.stream_policy import (
    STREAM_MARGIN_SECONDS,
    stream_timeout_seconds,
)


@pytest.mark.unit
def test_stream_cobre_o_maior_timeout_mais_margem() -> None:
    settings = SimpleNamespace(generation_timeout_seconds=300, edit_timeout_seconds=600)
    assert stream_timeout_seconds(settings) == 660
    assert STREAM_MARGIN_SECONDS == 60


@pytest.mark.unit
def test_stream_inclui_timeout_do_llm_e_margem() -> None:
    settings = SimpleNamespace(
        generation_timeout_seconds=300,
        edit_timeout_seconds=600,
        llm_timeout_seconds=90,
    )
    assert stream_timeout_seconds(settings) == 780


@pytest.mark.unit
def test_stream_inclui_upscale_quando_maior() -> None:
    settings = SimpleNamespace(
        generation_timeout_seconds=300,
        edit_timeout_seconds=600,
        upscale_timeout_seconds=900,
        llm_timeout_seconds=0,
    )
    assert stream_timeout_seconds(settings) == 960


@pytest.mark.unit
def test_stream_usa_geracao_quando_ela_for_maior() -> None:
    settings = SimpleNamespace(generation_timeout_seconds=900, edit_timeout_seconds=600)
    assert stream_timeout_seconds(settings) == 960
