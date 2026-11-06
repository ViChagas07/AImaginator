"""Cria uma variacao de uma geracao existente (mesmo prompt/proporcao)."""

from __future__ import annotations

import secrets
from uuid import UUID

from modules.image_generation.application.ports import GenerationRepositoryPort
from modules.image_generation.application.schemas import GenerateImageInput, GenerationOutput
from modules.image_generation.application.use_cases.generate_image import (
    GenerateImageAnonymous,
    GenerateImageFromPrompt,
)
from modules.image_generation.domain.entities import GenerationKind, GenerationStatus
from modules.users.contracts import User
from shared_kernel.errors import (
    DomainError,
    ForbiddenError,
    NotFoundError,
)

MAX_SEED = 2**32 - 1


class CreateVariation:
    """Reaproveita prompt, proporcao e estilo; sorteia uma seed nova."""

    def __init__(
        self,
        *,
        generations: GenerationRepositoryPort,
        generate_authenticated: GenerateImageFromPrompt | None = None,
        generate_anonymous: GenerateImageAnonymous | None = None,
    ) -> None:
        self._generations = generations
        self._generate_authenticated = generate_authenticated
        self._generate_anonymous = generate_anonymous

    async def execute(
        self,
        *,
        generation_id: UUID,
        user: User | None,
        anonymous_session_id: str | None,
        locale: str = "pt-BR",
        ip_hash: str | None = None,
    ) -> GenerationOutput:
        source = await self._generations.get_by_id(generation_id)
        if source is None:
            raise NotFoundError("Geracao nao encontrada.")
        self._ensure_owner(
            source, user=user, anonymous_session_id=anonymous_session_id
        )
        if source.kind is not GenerationKind.GENERATE:
            raise DomainError("Somente geracoes podem originar variacoes.")
        if source.status is not GenerationStatus.DONE:
            raise DomainError("A geracao ainda nao esta pronta para variacoes.")

        data = GenerateImageInput(
            prompt=source.prompt,
            negative_prompt=source.negative_prompt,
            style_preset=source.style_preset,
            aspect_ratio=source.aspect_ratio,
            seed=secrets.randbelow(MAX_SEED + 1),
            title=source.title,
        )
        if user is not None:
            if self._generate_authenticated is None:
                raise DomainError("Geracao autenticada nao configurada.")
            return await self._generate_authenticated.execute(
                user=user, data=data, locale=locale, ip_hash=ip_hash
            )
        if self._generate_anonymous is None or anonymous_session_id is None:
            raise DomainError("Sessao anonima obrigatoria.")
        return await self._generate_anonymous.execute(
            anonymous_session_id=anonymous_session_id,
            data=data,
            locale=locale,
            ip_hash=ip_hash,
        )

    @staticmethod
    def _ensure_owner(source, *, user: User | None, anonymous_session_id: str | None) -> None:
        if user is not None:
            if source.user_id != user.id:
                raise ForbiddenError("Acesso negado a esta geracao.")
            return
        if (
            source.user_id is not None
            or anonymous_session_id is None
            or source.anonymous_session_id != anonymous_session_id
        ):
            raise ForbiddenError("Acesso negado a esta geracao.")
