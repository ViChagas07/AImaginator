"""Aplicacao Celery: broker RabbitMQ, backend Redis, filas isoladas (Bulkhead).

- Filas separadas por custo (bulkhead em nivel de workers, spec 11/14):
  generation.priority, generation.standard, tasks.light.
- Retry com backoff exponencial + DLQ para falhas persistentes.
- NUNCA rodar geracao sincrona no request HTTP (spec secao 14).
"""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from infra.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "aimaginator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.celery_app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,  # fair dispatch (tasks longas)
    task_default_retry_delay=5,
    broker_connection_retry_on_startup=True,
    task_queues=(
        Queue("generation.standard", Exchange("generation"), routing_key="standard"),
        Queue("generation.priority", Exchange("generation"), routing_key="priority"),
        Queue("generation.dlq", Exchange("generation.dlx"), routing_key="dlq"),
    ),
    task_routes={
        "workers.celery_app.tasks.process_generation_task": {"queue": "generation.standard"},
    },
)
