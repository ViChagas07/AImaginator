"""Aplicacao Celery: broker RabbitMQ, backend Redis, filas isoladas (Bulkhead).

- Fila unica de geracao/edicao (`generation.standard`) + DLQ
  (`generation.dlq`). A antiga `generation.priority` era codigo morto e foi
  removida na Fase 2.
- Limites soft/hard sao aplicados por kind no enqueue e incluem o
  assistente LLM + motor; os defaults abaixo cobrem o maior job.
- Retry com backoff exponencial + DLQ para falhas persistentes.
- NUNCA rodar geracao sincrona no request HTTP (spec secao 14).
"""

from __future__ import annotations

import math

from celery import Celery
from celery.signals import worker_init, worker_shutdown
from kombu import Exchange, Queue

from infra.dev_guard import enforce_local_infra
from infra.settings import get_settings
from modules.observability.logging_config import configure_logging
from modules.observability.prometheus_env import (
    clean_multiproc_dir,
    configure_prometheus_env,
)

settings = get_settings()
configure_logging(app_env=settings.app_env)
configure_prometheus_env(settings.prometheus_multiproc_dir)
_default_time_limit = (
    max(settings.generation_timeout_seconds, settings.edit_timeout_seconds)
    + math.ceil(settings.llm_timeout_seconds)
    + 30
)

celery_app = Celery(
    "aimaginator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.celery_app.tasks"],
)


@worker_init.connect
def _init_worker_observability(**_kwargs) -> None:
    configure_logging(app_env=settings.app_env)
    enforce_local_infra(settings)
    if settings.prometheus_multiproc_dir:
        # Limpa ANTES de importar as metricas; com max-tasks-per-child o
        # processo filho recria os arquivos a cada job.
        clean_multiproc_dir(settings.prometheus_multiproc_dir)
    from workers.celery_app.worker_metrics import (
        start_metrics_server,
        start_queue_metrics_thread,
    )

    if settings.prometheus_multiproc_dir:
        start_metrics_server(settings.worker_metrics_port, settings.prometheus_multiproc_dir)
    start_queue_metrics_thread(settings.worker_metrics_interval_seconds)

    from workers.celery_app.heartbeat import init_heartbeat
    from workers.celery_app.reconciler import (
        reconcile_stale_generations_sync,
        reset_monthly_credits_sync,
    )

    init_heartbeat(settings)
    reconcile_stale_generations_sync()
    reset_monthly_credits_sync()


@worker_shutdown.connect
def _stop_worker_heartbeat(**_kwargs) -> None:
    from workers.celery_app.heartbeat import stop_heartbeat

    stop_heartbeat()


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=_default_time_limit,
    task_soft_time_limit=max(1, _default_time_limit - 30),
    worker_prefetch_multiplier=1,  # fair dispatch (tasks longas)
    worker_concurrency=1,  # uma difusao por vez (VRAM/RAM)
    worker_max_tasks_per_child=1,  # recicla o processo apos cada task
    # ack so depois de concluir: worker morto reentrega a task (idempotente).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=5,
    broker_connection_retry_on_startup=True,
    task_queues=(
        Queue("generation.standard", Exchange("generation"), routing_key="standard"),
        Queue("generation.dlq", Exchange("generation.dlx"), routing_key="dlq"),
    ),
    task_routes={
        "workers.celery_app.tasks.process_generation_task": {"queue": "generation.standard"},
    },
    beat_schedule={
        "purge-expired-edit-sources": {
            "task": "workers.celery_app.tasks.purge_sources_task",
            "schedule": 3600.0,
        },
    },
)
