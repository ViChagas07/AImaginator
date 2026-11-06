"""Porta de enfileiramento de tasks (application nunca conhece Celery)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class TaskQueuePort(Protocol):
    def enqueue_generation(self, generation_id: UUID, *, kind: str = "generate") -> None:
        """Enfileira o processamento assincrono de uma geracao/edicao (202)."""
        ...
