"""Caso de uso: editar imagem existente (URL validada anti-SSRF)."""

from __future__ import annotations

from modules.image_generation.application.ports import GenerationRepositoryPort, TaskQueuePort
from modules.image_generation.application.schemas import EditImageInput, GenerationOutput
from modules.image_generation.application.use_cases.generate_image import _STREAM_PATH
from modules.image_generation.domain.entities import Generation, GenerationKind
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.url_policy import UrlPolicy
from modules.users.contracts import User, UserRepositoryPort


class EditImageFromPrompt:
    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        users: UserRepositoryPort,
        task_queue: TaskQueuePort,
        prompt_guard: PromptInjectionGuard,
        url_policy: UrlPolicy,
    ) -> None:
        self._generations = generations
        self._users = users
        self._queue = task_queue
        self._guard = prompt_guard
        self._url_policy = url_policy

    async def execute(self, *, user: User, data: EditImageInput) -> GenerationOutput:
        clean_prompt = self._guard.validate(data.prompt)
        source_url = self._url_policy.validate(str(data.source_image_url))

        user.consume_credit()
        await self._users.save(user)

        generation = Generation(
            user_id=user.id,
            kind=GenerationKind.EDIT,
            prompt=clean_prompt,
            negative_prompt=self._guard.validate(data.negative_prompt)
            if data.negative_prompt
            else None,
            style_preset=data.style_preset,
            aspect_ratio=data.aspect_ratio,
            source_image_url=source_url,
        )
        await self._generations.save(generation)
        self._queue.enqueue_generation(generation.id)

        output = GenerationOutput(
            id=generation.id,
            kind=generation.kind,
            status=generation.status,
            prompt=generation.prompt,
            style_preset=generation.style_preset,
            aspect_ratio=generation.aspect_ratio,
            result_image_url=generation.result_image_url,
            error_message=generation.error_message,
            created_at=generation.created_at,
            completed_at=generation.completed_at,
        )
        output.stream_url = _STREAM_PATH.format(id=generation.id)
        return output
