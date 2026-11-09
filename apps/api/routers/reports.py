"""Denuncias de imagens publicas/galeria com anti-spam."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    LibraryRepoDep,
    OptionalCurrentUserDep,
    ReportLimiterDep,
    SettingsDep,
    get_client_ip_hash,
    resolve_anonymous_session,
)

router = APIRouter(prefix="/api/v1", tags=["reports"])

ReportReason = Literal["nsfw", "gore", "hate", "self_harm", "other"]


class ReportInput(BaseModel):
    generation_id: UUID
    reason: ReportReason
    details: str | None = Field(default=None, max_length=500)


class PublicReportInput(BaseModel):
    reason: ReportReason
    details: str | None = Field(default=None, max_length=500)


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    data: ReportInput,
    request: Request,
    current_user: OptionalCurrentUserDep,
    library: LibraryRepoDep,
    settings: SettingsDep,
    limiter: ReportLimiterDep,
) -> dict:
    ip_hash = get_client_ip_hash(request)
    anonymous_id = None
    if current_user is None:
        anonymous_id, _ = resolve_anonymous_session(request, settings)
    principal = f"user:{current_user.id}" if current_user is not None else f"anon:{anonymous_id}"
    await limiter.consume(f"report:{principal}")
    return await library.create_report(
        generation_id=data.generation_id,
        reason=data.reason,
        details=data.details,
        reporter_user_id=current_user.id if current_user else None,
        anonymous_session_id=anonymous_id,
        ip_hash=ip_hash,
    )


@router.post("/public/shares/{token}/reports", status_code=status.HTTP_202_ACCEPTED)
async def report_shared(
    token: str,
    data: PublicReportInput,
    request: Request,
    library: LibraryRepoDep,
    settings: SettingsDep,
    limiter: ReportLimiterDep,
) -> dict:
    found = await library.share_by_token(token)
    if found is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Link indisponivel.")
    _link, generation = found
    ip_hash = get_client_ip_hash(request)
    anonymous_id, _ = resolve_anonymous_session(request, settings)
    await limiter.consume(f"report:anon:{anonymous_id}")
    return await library.create_report(
        generation_id=generation.id,
        reason=data.reason,
        details=data.details,
        reporter_user_id=None,
        anonymous_session_id=anonymous_id,
        ip_hash=ip_hash,
    )
