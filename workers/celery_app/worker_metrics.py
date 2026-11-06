"""Metricas do worker: endpoint multiprocesso + gauge das filas do broker."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable

from prometheus_client import CollectorRegistry, start_http_server
from prometheus_client.multiprocess import MultiProcessCollector

from modules.observability.metrics import CELERY_QUEUE_SIZE

logger = logging.getLogger(__name__)

_thread_started = False
_metrics_server_started = False


def start_metrics_server(port: int, multiproc_dir: str) -> None:
    """Expõe /metrics do processo principal agregando os arquivos multiproc."""
    global _metrics_server_started
    if _metrics_server_started or not multiproc_dir:
        return
    registry = CollectorRegistry()
    MultiProcessCollector(registry, path=multiproc_dir)
    start_http_server(port, registry=registry)
    _metrics_server_started = True
    logger.info("worker_metrics_server_started", extra={"port": port})


def _queue_size(queue: str) -> int | None:
    try:
        from workers.celery_app.celery import celery_app

        with celery_app.connection_for_read() as connection:
            channel = connection.channel()
            try:
                declared = channel.queue_declare(queue=queue, passive=True)
                return int(declared.message_count)
            finally:
                channel.close()
    except Exception:
        logger.warning("queue_metrics_failed", exc_info=True)
        return None


def collect_queue_sizes(queues: Iterable[str] = ("generation.standard",)) -> None:
    for queue in queues:
        size = _queue_size(queue)
        if size is not None:
            CELERY_QUEUE_SIZE.labels(queue=queue).set(size)


def start_queue_metrics_thread(interval_seconds: float = 10.0) -> None:
    """Thread daemon curta, sem bloquear o worker."""
    global _thread_started
    if _thread_started:
        return
    _thread_started = True

    def _loop() -> None:
        while True:
            collect_queue_sizes()
            time.sleep(interval_seconds)

    threading.Thread(target=_loop, name="aimaginator-queue-metrics", daemon=True).start()
    logger.info("queue_metrics_thread_started")
