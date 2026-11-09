"""Configuracao de entrega de tasks: sem perda silenciosa de jobs."""

from __future__ import annotations

import pytest

from workers.celery_app.celery import celery_app


@pytest.mark.unit
def test_tasks_de_imagem_usam_ack_tardio_e_rejeicao_em_worker_perdido() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
