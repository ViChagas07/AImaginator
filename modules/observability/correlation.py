"""Correlation id por geracao para logs estruturados (nunca como label)."""

from __future__ import annotations

import structlog


def bind_generation_context(*, generation_id: str, kind: str) -> None:
    structlog.contextvars.bind_contextvars(
        correlation_id=generation_id, generation_kind=kind
    )


def clear_generation_context() -> None:
    structlog.contextvars.clear_contextvars()
