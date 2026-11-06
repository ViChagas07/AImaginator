"""Cronometro reutilizavel de etapas, com log estruturado e metrica."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import structlog

from modules.observability.metrics import STAGE_DURATION

logger = structlog.get_logger(__name__)


@contextmanager
def stage_timer(
    stage: str,
    *,
    correlation_id: str | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Iterator[None]:
    """Mede a etapa; falhas registram apenas o tipo/codigo, nunca payload."""
    started = clock()
    try:
        yield
    except Exception as exc:
        duration = max(0.0, clock() - started)
        STAGE_DURATION.labels(stage=stage).observe(duration)
        logger.error(
            "stage_failed",
            stage=stage,
            duration_seconds=round(duration, 4),
            correlation_id=correlation_id,
            error_type=type(exc).__name__,
            error_code=getattr(exc, "code", None),
        )
        raise
    else:
        duration = max(0.0, clock() - started)
        STAGE_DURATION.labels(stage=stage).observe(duration)
        logger.info(
            "stage_completed",
            stage=stage,
            duration_seconds=round(duration, 4),
            correlation_id=correlation_id,
        )
