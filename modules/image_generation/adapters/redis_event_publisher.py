"""Publisher de eventos de progresso via Redis Pub/Sub (bridge SSE)."""

from __future__ import annotations

from typing import Any

from modules.image_generation.application.ports import EventPublisherPort, stream_channel
from modules.image_generation.application.schemas import GenerationProgressEvent


class RedisEventPublisher(EventPublisherPort):
    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def publish_progress(self, event: GenerationProgressEvent) -> None:
        channel = stream_channel(event.generation_id)
        await self._redis.publish(channel, event.model_dump_json())
