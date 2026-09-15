"""Caso de uso executado pelo WORKER (Celery): processa a geracao.

Fluxo: QUEUED -> PROCESSING -> DONE/FAILED, publicando progresso no
Redis Pub/Sub a cada passo (o endpoint SSE do apps/api apenas repassa —
assim qualquer replica da API serve o stream, spec secao 13).
"""

from __future__ import annotations

from uuid import UUID

from modules.image_generation.application.ports import (
    EventPublisherPort,
    GenerationRepositoryPort,
    ImageAgentPort,
    stream_channel,
)
from modules.image_generation.application.schemas import GenerationProgressEvent
from modules.image_generation.domain.entities import GenerationStatus
from shared_kernel.errors import NotFoundError


class ProcessGeneration:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        image_agent: ImageAgentPort,
        events: EventPublisherPort,
    ) -> None:
        self._generations = generations
        self._agent = image_agent
        self._events = events

    async def execute(self, generation_id: UUID) -> None:
        generation = await self._generations.get_by_id(generation_id)
        if generation is None:
            raise NotFoundError(f"Geracao {generation_id} nao encontrada.")

        async def publish(status: GenerationStatus, progress: int, **kwargs) -> None:
            await self._events.publish_progress(
                GenerationProgressEvent(
                    generation_id=generation.id,
                    status=status,
                    progress=progress,
                    **kwargs,
                )
            )

        try:
            generation.transition_to(GenerationStatus.PROCESSING)
            await self._generations.save(generation)
            await publish(GenerationStatus.PROCESSING, 5)

            async def on_progress(percent: int) -> None:
                await publish(GenerationStatus.PROCESSING, min(5 + percent, 95))

            result_url = await self._agent.run_generation(generation, on_progress)

            generation.attach_result(result_url)
            await self._generations.save(generation)
            await publish(GenerationStatus.DONE, 100, result_image_url=result_url)
        except Exception as exc:
            generation.transition_to(GenerationStatus.FAILED, error=str(exc)[:500])
            await self._generations.save(generation)
            await publish(GenerationStatus.FAILED, 100, error="Falha no processamento.")
            raise


__all__ = ["ProcessGeneration", "stream_channel"]
