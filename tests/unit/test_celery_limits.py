"""Testes da selecao de timeouts por kind (Fase 2, Bloco 4)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from workers.celery_app.limits import task_time_limits


def _settings(gen: int = 300, edit: int = 600):
    return SimpleNamespace(generation_timeout_seconds=gen, edit_timeout_seconds=edit)


@pytest.mark.unit
def test_geracao_usa_timeout_de_geracao() -> None:
    soft, hard = task_time_limits("generate", _settings())
    assert soft == 270
    assert hard == 300


@pytest.mark.unit
def test_edicao_usa_timeout_de_edicao() -> None:
    soft, hard = task_time_limits("edit", _settings())
    assert soft == 570
    assert hard == 600


@pytest.mark.unit
def test_kind_desconhecido_cai_no_timeout_de_geracao() -> None:
    soft, hard = task_time_limits("desconhecido", _settings())
    assert soft == 270
    assert hard == 300


@pytest.mark.unit
def test_limites_incluem_o_timeout_do_llm() -> None:
    settings = SimpleNamespace(
        generation_timeout_seconds=300,
        edit_timeout_seconds=600,
        llm_timeout_seconds=90,
    )
    assert task_time_limits("generate", settings) == (390, 420)
    assert task_time_limits("edit", settings) == (690, 720)


@pytest.mark.unit
def test_upscale_usa_timeout_proprio_sem_llm() -> None:
    settings = SimpleNamespace(upscale_timeout_seconds=300)
    assert task_time_limits("upscale", settings) == (300, 330)


@pytest.mark.unit
def test_soft_limit_nunca_e_menor_que_um() -> None:
    soft, hard = task_time_limits("generate", _settings(gen=10, edit=10))
    assert soft == 1
    assert hard == 10
