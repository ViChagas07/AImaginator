"""Rotas REST do recurso generations â€” spec secoes 16 e 5.

- POST /api/v1/generations        -> 202 Accepted + stream_url (auth opcional)
- POST /api/v1/generations/edits  -> 202 (edicao com imagem por URL, anti-SSRF)
- GET  /api/v1/generations        -> historico paginado por cursor
- GET  /api/v1/generations/{id}   -> detalhe (ownership)
- PATCH /api/v1/generations/{id}  -> renomeia o titulo (dono ou sessao anonima)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from apps.api.dependencies import (
    CreditLedgerDep,
    CurrentUserDep,
    EngineAvailabilityDep,
    EventPublisherDep,
    GenerationRepoDep,
    ImageFetcherDep,
    ImageGenerationEnabledDep,
    LocaleDep,
    ModerationServiceDep,
    ObjectStorageDep,
    OptionalCurrentUserDep,
    PromptGuardDep,
    PromptQuotaStoreDep,
    QueueReconcilerDep,
    RedisDep,
    SettingsDep,
    TaskQueueDep,
    UpscaleQuotaDep,
    UrlPolicyDep,
    UserRepoDep,
    ensure_not_moderation_blocked,
    get_client_ip_hash,
    get_generation_rate_limiter,
    resolve_anonymous_session,
    set_anonymous_session_cookie,
)
from modules.image_generation.application.schemas import (
    MAX_PROMPT_LENGTH,
    GenerationProgressEvent,
)
from modules.image_generation.application.use_cases.cancel_generation import (
    CancelGeneration,
)
from modules.image_generation.contracts import (
    CreateEditFromUpload,
    CreateUpscale,
    CreateVariation,
    EditImageFromPrompt,
    EditImageInput,
    GenerateImageAnonymous,
    GenerateImageFromPrompt,
    GenerateImageInput,
    GenerationOutput,
    GenerationPage,
    GetGeneration,
    ListUserGenerations,
    RenameGeneration,
    RenameGenerationInput,
)
from modules.image_generation.domain.entities import (
    AspectRatio,
    Generation,
    GenerationKind,
    GenerationStatus,
    StylePreset,
)
from modules.image_generation.domain.storage_errors import StorageUnavailableError
from modules.prompt_quota.contracts import ConsumePromptQuota, RefundPromptQuota
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
    credits: CreditLedgerDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    events: EventPublisherDep,
    moderation: ModerationServiceDep,
    locale: LocaleDep,
    availability: EngineAvailabilityDep,
    _enabled: ImageGenerationEnabledDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    ip_hash = get_client_ip_hash(request)
    await availability.ensure_available("generate", locale=locale)
    if current_user is not None:
        await ensure_not_moderation_blocked(
            moderation,
            user=current_user,
            anonymous_session_id=None,
            ip_hash=ip_hash,
            locale=locale,
        )
        await limiter.consume(f"user:{current_user.id}")
        total = settings.authenticated_prompt_chances_per_day
        return await GenerateImageFromPrompt(
            generations=generations,
            users=users,
            task_queue=queue,
            prompt_guard=guard,
            events=events,
            prompt_quota=ConsumePromptQuota(store, total=total),
            quota_refund=RefundPromptQuota(store),
            credits=credits,
        ).execute(user=current_user, data=data, locale=locale, ip_hash=ip_hash)

    anonymous_id, token = resolve_anonymous_session(request, settings)
    set_anonymous_session_cookie(response, settings, token)
    await ensure_not_moderation_blocked(
        moderation,
        user=None,
        anonymous_session_id=anonymous_id,
        ip_hash=ip_hash,
        locale=locale,
    )
    await limiter.consume(f"anon:{anonymous_id}")
    total = settings.anonymous_prompt_chances_per_day
    created = await GenerateImageAnonymous(
        generations=generations,
        task_queue=queue,
        prompt_guard=guard,
        events=events,
        prompt_quota=ConsumePromptQuota(store, total=total),
        quota_refund=RefundPromptQuota(store),
    ).execute(
        anonymous_session_id=anonymous_id,
        data=data,
        locale=locale,
        ip_hash=ip_hash,
    )
    return created.model_copy(update={"anonymous_token": token})


@router.post(
    "/generations/{generation_id}/upscale",
    response_model=GenerationOutput,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_upscale(
    generation_id: UUID,
    request: Request,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    queue: TaskQueueDep,
    settings: SettingsDep,
    events: EventPublisherDep,
    quota: UpscaleQuotaDep,
    locale: LocaleDep,
    availability: EngineAvailabilityDep,
    _enabled: ImageGenerationEnabledDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    ip_hash = get_client_ip_hash(request)
    await availability.ensure_available("upscale", locale=locale)
    await limiter.consume(f"upscale:{current_user.id}")
    return await CreateUpscale(
        generations=generations,
        task_queue=queue,
        quota_store=quota,
        daily_limit=settings.upscale_daily_limit,
        events=events,
    ).execute(
        generation_id=generation_id,
        user=current_user,
        locale=locale,
        ip_hash=ip_hash,
    )


@router.post(
    "/generations/{generation_id}/variations",
    response_model=GenerationOutput,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_variation(
    generation_id: UUID,
    request: Request,
    response: Response,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    credits: CreditLedgerDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    events: EventPublisherDep,
    moderation: ModerationServiceDep,
    locale: LocaleDep,
    availability: EngineAvailabilityDep,
    _enabled: ImageGenerationEnabledDep,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    ip_hash = get_client_ip_hash(request)
    await availability.ensure_available("generate", locale=locale)
    if current_user is not None:
        await ensure_not_moderation_blocked(
            moderation,
            user=current_user,
            anonymous_session_id=None,
            ip_hash=ip_hash,
            locale=locale,
        )
        await limiter.consume(f"user:{current_user.id}")
        generate = GenerateImageFromPrompt(
            generations=generations,
            users=users,
            task_queue=queue,
            prompt_guard=guard,
            events=events,
            prompt_quota=ConsumePromptQuota(
                store, total=settings.authenticated_prompt_chances_per_day
            ),
            quota_refund=RefundPromptQuota(store),
            credits=credits,
        )
        return await CreateVariation(
            generations=generations, generate_authenticated=generate
        ).execute(
            generation_id=generation_id,
            user=current_user,
            anonymous_session_id=None,
            locale=locale,
            ip_hash=ip_hash,
        )

    anonymous_id, token = resolve_anonymous_session(request, settings)
    set_anonymous_session_cookie(response, settings, token)
    await ensure_not_moderation_blocked(
        moderation,
        user=None,
        anonymous_session_id=anonymous_id,
        ip_hash=ip_hash,
        locale=locale,
    )
    await limiter.consume(f"anon:{anonymous_id}")
    generate_anon = GenerateImageAnonymous(
        generations=generations,
        task_queue=queue,
        prompt_guard=guard,
        events=events,
        prompt_quota=ConsumePromptQuota(store, total=settings.anonymous_prompt_chances_per_day),
        quota_refund=RefundPromptQuota(store),
    )
    created = await CreateVariation(
        generations=generations, generate_anonymous=generate_anon
    ).execute(
        generation_id=generation_id,
        user=None,
        anonymous_session_id=anonymous_id,
        locale=locale,
        ip_hash=ip_hash,
    )
    return created.model_copy(update={"anonymous_token": token})


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
    credits: CreditLedgerDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    url_policy: UrlPolicyDep,
    events: EventPublisherDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    storage: ObjectStorageDep,
    image_fetcher: ImageFetcherDep,
    moderation: ModerationServiceDep,
    locale: LocaleDep,
    availability: EngineAvailabilityDep,
    _enabled: ImageGenerationEnabledDep,
    request: Request,
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    ip_hash = get_client_ip_hash(request)
    await availability.ensure_available("edit", locale=locale)
    await ensure_not_moderation_blocked(
        moderation,
        user=current_user,
        anonymous_session_id=None,
        ip_hash=ip_hash,
        locale=locale,
    )
    await limiter.consume(f"user:{current_user.id}")
    use_case = EditImageFromPrompt(
        generations=generations,
        users=users,
        task_queue=queue,
        prompt_guard=guard,
        url_policy=url_policy,
        events=events,
        prompt_quota=ConsumePromptQuota(store, total=settings.authenticated_prompt_chances_per_day),
        quota_refund=RefundPromptQuota(store),
        credits=credits,
        image_fetcher=image_fetcher,
        storage=storage,
        max_upload_bytes=settings.edit_upload_max_bytes,
        max_upload_dimension=settings.edit_upload_max_dimension,
        max_upload_pixels=settings.edit_upload_max_pixels,
    )
    return await use_case.execute(user=current_user, data=data, locale=locale, ip_hash=ip_hash)


@router.post(
    "/generations/edits/upload",
    response_model=GenerationOutput,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_edit_upload(
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    credits: CreditLedgerDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    events: EventPublisherDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    storage: ObjectStorageDep,
    moderation: ModerationServiceDep,
    locale: LocaleDep,
    availability: EngineAvailabilityDep,
    _enabled: ImageGenerationEnabledDep,
    request: Request,
    prompt: str = Form(..., min_length=1, max_length=MAX_PROMPT_LENGTH),
    file: UploadFile = File(...),
    negative_prompt: str | None = Form(default=None, max_length=MAX_PROMPT_LENGTH),
    style_preset: StylePreset = Form(default=StylePreset.NONE),
    aspect_ratio: AspectRatio = Form(default=AspectRatio.SQUARE),
    seed: int | None = Form(default=None, ge=0, le=2**32 - 1),
    title: str | None = Form(default=None, max_length=200),
    limiter: TokenBucket = Depends(get_generation_rate_limiter),
) -> GenerationOutput:
    """Valida, persiste a origem no S3 e enfileira a edicao."""
    if storage is None:
        raise StorageUnavailableError()
    ip_hash = get_client_ip_hash(request)
    await availability.ensure_available("edit", locale=locale)
    await ensure_not_moderation_blocked(
        moderation,
        user=current_user,
        anonymous_session_id=None,
        ip_hash=ip_hash,
        locale=locale,
    )
    await limiter.consume(f"user:{current_user.id}")
    image_bytes = await file.read(settings.edit_upload_max_bytes + 1)
    data = GenerateImageInput(
        prompt=prompt,
        negative_prompt=negative_prompt,
        style_preset=style_preset,
        aspect_ratio=aspect_ratio,
        seed=seed,
        title=title,
    )
    return await CreateEditFromUpload(
        generations=generations,
        users=users,
        task_queue=queue,
        prompt_guard=guard,
        storage=storage,
        events=events,
        prompt_quota=ConsumePromptQuota(store, total=settings.authenticated_prompt_chances_per_day),
        quota_refund=RefundPromptQuota(store),
        credits=credits,
        max_upload_bytes=settings.edit_upload_max_bytes,
        max_upload_dimension=settings.edit_upload_max_dimension,
        max_upload_pixels=settings.edit_upload_max_pixels,
    ).execute(
        user=current_user,
        data=data,
        image_bytes=image_bytes,
        declared_content_type=file.content_type,
        locale=locale,
        ip_hash=ip_hash,
    )


@router.post("/generations/{generation_id}/retry")
async def retry_generation(
    generation_id: UUID,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    users: UserRepoDep,
    queue: TaskQueueDep,
    guard: PromptGuardDep,
    events: EventPublisherDep,
    credits: CreditLedgerDep,
    store: PromptQuotaStoreDep,
    settings: SettingsDep,
) -> dict:
    original = await generations.get_by_id(generation_id)
    if original is None or original.user_id != current_user.id:
        from shared_kernel.errors import NotFoundError

        raise NotFoundError("Geracao nao encontrada.")
    if not original.can_retry():
        from shared_kernel.errors import DomainError

        raise DomainError("Esta geracao nao pode ser retentada.")
    if original.kind is not GenerationKind.GENERATE:
        from shared_kernel.errors import DomainError

        raise DomainError("Retentativa disponivel apenas para geracoes.")
    guard.validate(original.prompt)
    await credits.reset_if_due(current_user.id)
    generation = Generation(
        user_id=current_user.id,
        kind=GenerationKind.GENERATE,
        prompt=original.prompt,
        negative_prompt=original.negative_prompt,
        style_preset=original.style_preset,
        aspect_ratio=original.aspect_ratio,
        seed=original.seed,
        title=original.title,
        locale=original.locale,
    )
    await credits.consume(
        current_user.id,
        ref_type="generation",
        ref_id=str(generation.id),
        idempotency_key=f"consume:{generation.id}",
    )
    await ConsumePromptQuota(store, total=settings.plan_daily_prompts(current_user.plan)).execute(
        f"user:{current_user.id}"
    )
    await generations.save(generation)
    queue.enqueue_generation(generation.id, kind="generate")
    await events.publish_progress(
        GenerationProgressEvent(
            generation_id=generation.id,
            status=GenerationStatus.QUEUED,
            progress=0,
        )
    )
    return {"id": str(generation.id), "status": "queued"}


@router.post("/generations/{generation_id}/cancel")
async def cancel_generation(
    generation_id: UUID,
    request: Request,
    settings: SettingsDep,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    events: EventPublisherDep,
    redis: RedisDep,
    credits: CreditLedgerDep,
    store: PromptQuotaStoreDep,
) -> JSONResponse:
    anonymous_id = None
    if current_user is None:
        anonymous_id, _ = resolve_anonymous_session(request, settings)
    result = await CancelGeneration(
        generations=generations,
        events=events,
        redis=redis,
        credits=credits,
        quota_refund=RefundPromptQuota(store),
    ).execute(
        user_id=current_user.id if current_user is not None else None,
        anonymous_session_id=anonymous_id,
        generation_id=generation_id,
    )
    status_code = (
        status.HTTP_202_ACCEPTED
        if result["status"] == "cancel_requested"
        else status.HTTP_409_CONFLICT
        if result.get("already_finished")
        else status.HTTP_200_OK
    )
    return JSONResponse(result, status_code=status_code)


@router.patch("/generations/{generation_id}", response_model=GenerationOutput)
async def rename_generation(
    generation_id: UUID,
    data: RenameGenerationInput,
    request: Request,
    settings: SettingsDep,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    storage: ObjectStorageDep,
) -> GenerationOutput:
    """Renomeia a imagem (titulo) para o dono autenticado ou sessao anonima."""
    anonymous_id = None
    if current_user is None:
        anonymous_id, _ = resolve_anonymous_session(request, settings)
    return await RenameGeneration(generations, storage=storage).execute(
        user_id=current_user.id if current_user is not None else None,
        anonymous_session_id=anonymous_id,
        generation_id=generation_id,
        title=data.title,
    )


@router.get("/generations", response_model=GenerationPage)
async def list_generations(
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    storage: ObjectStorageDep,
    reconciler: QueueReconcilerDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> GenerationPage:
    return await ListUserGenerations(generations, storage=storage, reconciler=reconciler).execute(
        user_id=current_user.id, cursor=cursor, limit=limit
    )


@router.get("/generations/{generation_id}", response_model=GenerationOutput)
async def get_generation(
    generation_id: UUID,
    request: Request,
    settings: SettingsDep,
    current_user: OptionalCurrentUserDep,
    generations: GenerationRepoDep,
    storage: ObjectStorageDep,
    reconciler: QueueReconcilerDep,
) -> GenerationOutput:
    anonymous_id = None
    if current_user is None:
        anonymous_id, _ = resolve_anonymous_session(request, settings)
    return await GetGeneration(generations, storage=storage, reconciler=reconciler).execute(
        user_id=current_user.id if current_user is not None else None,
        anonymous_session_id=anonymous_id,
        generation_id=generation_id,
    )
