"""Testes do adapter Celery: limites por kind e fila standard (Fase 2, Bloco 4)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.image_generation.adapters.celery_task_queue import CeleryTaskQueue


def _install_fake_task(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    def apply_async(**kwargs) -> None:
        calls.append(kwargs)

    fake_module = types.ModuleType("workers.celery_app.tasks")
    fake_module.process_generation_task = SimpleNamespace(apply_async=apply_async)
    monkeypatch.setitem(sys.modules, "workers.celery_app.tasks", fake_module)
    monkeypatch.setattr(
        "infra.settings.get_settings",
        lambda: SimpleNamespace(generation_timeout_seconds=300, edit_timeout_seconds=600),
    )
    return calls


@pytest.mark.unit
def test_enqueue_de_edicao_usa_timeout_de_edicao(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_task(monkeypatch)
    generation_id = uuid4()

    CeleryTaskQueue().enqueue_generation(generation_id, kind="edit")

    assert calls == [
        {
            "args": [str(generation_id), "edit"],
            "queue": "generation.standard",
            "soft_time_limit": 570,
            "time_limit": 600,
        }
    ]


@pytest.mark.unit
def test_enqueue_de_geracao_usa_timeout_de_geracao(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_task(monkeypatch)
    generation_id = uuid4()

    CeleryTaskQueue().enqueue_generation(generation_id, kind="generate")

    assert calls[0]["soft_time_limit"] == 270
    assert calls[0]["time_limit"] == 300
    assert calls[0]["queue"] == "generation.standard"
