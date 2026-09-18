"""Caso de uso: gerar imagem nova a partir de prompt (spec: GenerateImageFromPrompt)."""

from __future__ import annotations

from modules.image_generation.application.ports import (
    GenerationRepositoryPort,
    TaskQueuePort,
)
from modules.image_generation.application.schemas import GenerateImageInput, GenerationOutput
from modules.image_generation.domain.entities import Generation, GenerationKind
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.users.contracts import User, UserRepositoryPort

_STREAM_PATH = "/api/v1/generations/{id}/stream"


def _to_output(generation: Generation) -> GenerationOutput:
    output = GenerationOutput(
        id=generation.id,
        kind=generation.kind,
        status=generation.status,
        prompt=generation.prompt,
        style_preset=generation.style_preset,
        aspect_ratio=generation.aspect_ratio,
        title=generation.title,
        result_image_url=generation.result_image_url,
        error_message=generation.error_message,
        created_at=generation.created_at,
        completed_at=generation.completed_at,
    )
    output.stream_url = _STREAM_PATH.format(id=generation.id)
    return output


class GenerateImageFromPrompt:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        users: UserRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
    ) -> None:
        self._generations = generations
        self._users = users
        self._queue = task_queue
        self._guard = prompt_guard

    async def execute(self, *, user: User, data: GenerateImageInput) -> GenerationOutput:
        clean_prompt = self._guard.validate(data.prompt)
        clean_negative = (
            self._guard.validate(data.negative_prompt) if data.negative_prompt else None
        )

        user.consume_credit()  # regra de negocio na entidade (QuotaExceeded -> 429)
        await self._users.save(user)

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.GENERATE,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            title=data.title,
        )
        await self._generations.save(generation)
        self._queue.enqueue_generation(generation.id)

        return _to_output(generation)


class GenerateImageAnonymous:
    """Geracao por usuario nao logado (sessao anonima assinada, Bloco 3-A)."""

    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
    ) -> None:
        self._generations = generations
        self._queue = task_queue
        self._guard = prompt_guard

    async def execute(
        self, *, anonymous_session_id: str, data: GenerateImageInput
    ) -> GenerationOutput:
        clean_prompt = self._guard.validate(data.prompt)
        clean_negative = (
            self._guard.validate(data.negative_prompt) if data.negative_prompt else None
        )

        generation = Generation(
            user_id=None,
            anonymous_session_id=anonymous_session_id,
            kind=GenerationKind.GENERATE,
            prompt=clean_prompt,
            negative_prompt=clean_negative,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            title=data.title,
        )
        await self._generations.save(generation)
        self._queue.enqueue_generation(generation.id)

        return _to_output(generation)
