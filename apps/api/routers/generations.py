"""Rotas REST do recurso generations — spec secoes 16 e 5.

- POST /api/v1/generations        -> 202 Accepted + stream_url (async, nunca sincrono)
- POST /api/v1/generations/edits  -> 202 (edicao com imagem por URL, anti-SSRF)
- GET  /api/v1/generations        -> historico paginado por cursor
- GET  /api/v1/generations/{id}   -> detalhe (ownership)
- GET  /api/v1/gallery            -> vitrine publica (cache SWR)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from apps.api.dependencies import (
    CurrentUserDep,
    GenerationRepoDep,
    PromptGuardDep,
    SWRCacheDep,
    SettingsDep,
    TaskQueueDep,
    UrlPolicyDep,
    UserRepoDep,
    get_generation_rate_limiter,
)
from modules.image_generation.contracts import (
    EditImageFromPrompt,
    EditImageInput,
    GenerateImageFromPrompt,
    GenerateImageInput,
    GenerationOutput,
    GenerationPage,
    GetGeneration,
    ListPublicShowcase,
    ListUserGenerations,
)
from modules.rate_limiting.token_bucket import TokenBucket

router = APIRouter(prefix="/api/v1", tags=["generations"])


@router.post("/generations", response_model=GenerationOutput, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    data: GenerateImageInput,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    await limiter.consume(f"user:{current_user.id}")
    use_case = GenerateImageFromPrompt(
        generations=generations, users=users, task_queue=queue, prompt_guard=guard
    )
    return await use_case.execute(user=current_user, data=data)


@router.post(
    "/generations/edits",
    response_model=GenerationOutput,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_edit(
    data: EditImageInput,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    url_policy: UrlPolicyDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    await limiter.consume(f"user:{current_user.id}")
    use_case = EditImageFromPrompt(
        generations=generations,
        users=users,
        task_queue=queue,
        prompt_guard=guard,
        url_policy=url_policy,
    )
    return await use_case.execute(user=current_user, data=data)


@router.get("/generations", response_model=GenerationPage)
async def list_generations(
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> GenerationPage:
    return await ListUserGenerations(generations).execute(
        user_id=current_user.id, cursor=cursor, limit=limit
    )


@router.get("/generations/{generation_id}", response_model=GenerationOutput)
async def get_generation(
    generation_id: UUID,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
) -> GenerationOutput:
    return await GetGeneration(generations).execute(
        user_id=current_user.id, generation_id=generation_id
    )


@router.get("/gallery", response_model=list[GenerationOutput])
async def public_gallery(
    generations: GenerationRepoDep, cache: SWRCacheDep
) -> list[GenerationOutput]:
    return await ListPublicShowcase(generations=generations, cache=cache).execute()
