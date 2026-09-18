"""Rotas REST do recurso generations — spec secoes 16 e 5.

- POST /api/v1/generations        -> 202 Accepted + stream_url (auth opcional)
- POST /api/v1/generations/edits  -> 202 (edicao com imagem por URL, anti-SSRF)
- GET  /api/v1/generations        -> historico paginado por cursor
- GET  /api/v1/generations/{id}   -> detalhe (ownership)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from apps.api.dependencies import (
    CurrentUserDep,
    GenerationRepoDep,
    OptionalCurrentUserDep,
    PromptGuardDep,
    PromptQuotaStoreDep,
    SettingsDep,
    TaskQueueDep,
    UrlPolicyDep,
    UserRepoDep,
    get_generation_rate_limiter,
    resolve_anonymous_session,
    set_anonymous_session_cookie,
)
from modules.image_generation.contracts import (
    EditImageFromPrompt,
    EditImageInput,
    GenerateImageAnonymous,
    GenerateImageFromPrompt,
    GenerateImageInput,
    GenerationOutput,
    GenerationPage,
    GetGeneration,
    ListUserGenerations,
)
from modules.prompt_quota.contracts import ConsumePromptQuota
from modules.rate_limiting.token_bucket import TokenBucket

router = APIRouter(prefix="/api/v1", tags=["generations"])


@router.post("/generations", response_model=GenerationOutput, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    data: GenerateImageInput,
    request: Request,
    response: Response,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    if current_user is not None:
        await limiter.consume(f"user:{current_user.id}")
        total = settings.authenticated_prompt_chances_per_day
        await ConsumePromptQuota(store, total=total).execute(f"user:{current_user.id}")
        return await GenerateImageFromPrompt(
            generations=generations, users=users, task_queue=queue, prompt_guard=guard
        ).execute(user=current_user, data=data)

    anonymous_id, token = resolve_anonymous_session(request, settings)
    set_anonymous_session_cookie(response, settings, token)
    await limiter.consume(f"anon:{anonymous_id}")
    total = settings.anonymous_prompt_chances_per_day
    await ConsumePromptQuota(store, total=total).execute(f"anon:{anonymous_id}")
    return await GenerateImageAnonymous(
        generations=generations, task_queue=queue, prompt_guard=guard
    ).execute(anonymous_session_id=anonymous_id, data=data)


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
