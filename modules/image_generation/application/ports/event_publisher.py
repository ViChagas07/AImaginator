"""Porta de publicacao de eventos de progresso (Redis Pub/Sub -> SSE)."""

from __future__ import annotations

from typing import Protocol

from modules.image_generation.application.schemas import GenerationProgressEvent


class EventPublisherPort(Protocol):
    async def publish_progress(self, event: GenerationProgressEvent) -> None: ...


def stream_channel(generation_id) -> str:
    """Canal Pub/Sub de uma geracao (bridge SSE do apps/api)."""
    return f"generations:{generation_id}:events"
