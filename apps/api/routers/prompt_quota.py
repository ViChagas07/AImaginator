"""Endpoints de cota de prompts (Bloco 1).

- GET  /api/v1/prompt-quota         -> consulta a cota (sem consumir)
- POST /api/v1/prompt-quota/consume -> consome uma chance (429 se esgotada)

O principal pode ser um usuario autenticado (3 chances/24h) ou uma
sessao anonima assinada (1 chance/24h). A sessao anonima e emitida/renovada
aqui e devolvida ao cliente (cookie + corpo) para ser reutilizada.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from apps.api.dependencies import (
    OptionalCurrentUserDep,
    PromptQuotaStoreDep,
    SettingsDep,
    get_prompt_quota_rate_limiter,
    resolve_anonymous_session,
    set_anonymous_session_cookie,
)
from modules.prompt_quota.contracts import ConsumePromptQuota, GetPromptQuota
from modules.rate_limiting.token_bucket import TokenBucket

router = APIRouter(prefix="/api/v1/prompt-quota", tags=["prompt-quota"])


def _quota_payload(quota, *, authenticated: bool, anonymous_token: str | None) -> dict:
    return {
        "chances_remaining": quota.chances_remaining,
        "chances_total": quota.chances_total,
        "next_available_at": quota.next_available_at.isoformat()
        if quota.next_available_at
        else None,
        "authenticated": authenticated,
        "anonymous_token": anonymous_token,
    }


@router.get("")
async def get_prompt_quota(
    request: Request,
    response: Response,
    current_user: OptionalCurrentUserDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    limiter: TokenBucket = Depends(get_prompt_quota_rate_limiter),
) -> dict:
    await limiter.consume("quota:read")
    if current_user is not None:
        total = settings.authenticated_prompt_chances_per_day
        quota = await GetPromptQuota(store, total=total).execute(f"user:{current_user.id}")
        return _quota_payload(quota, authenticated=True, anonymous_token=None)

    anonymous_id, token = resolve_anonymous_session(request, settings)
    set_anonymous_session_cookie(response, settings, token)
    total = settings.anonymous_prompt_chances_per_day
    quota = await GetPromptQuota(store, total=total).execute(f"anon:{anonymous_id}")
    return _quota_payload(quota, authenticated=False, anonymous_token=token)


@router.post("/consume")
async def consume_prompt_quota(
    request: Request,
    response: Response,
    current_user: OptionalCurrentUserDep,
    settings: SettingsDep,
    store: PromptQuotaStoreDep,
    limiter: TokenBucket = Depends(get_prompt_quota_rate_limiter),
) -> dict:
    await limiter.consume("quota:consume")
    if current_user is not None:
        total = settings.authenticated_prompt_chances_per_day
        quota = await ConsumePromptQuota(store, total=total).execute(f"user:{current_user.id}")
        return _quota_payload(quota, authenticated=True, anonymous_token=None)

    anonymous_id, token = resolve_anonymous_session(request, settings)
    set_anonymous_session_cookie(response, settings, token)
    total = settings.anonymous_prompt_chances_per_day
    quota = await ConsumePromptQuota(store, total=total).execute(f"anon:{anonymous_id}")
    return _quota_payload(quota, authenticated=False, anonymous_token=token)
