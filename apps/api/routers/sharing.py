"""Links publicos de imagem (somente versao com marca d'agua)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    CurrentUserDep,
    LibraryRepoDep,
    ObjectStorageDep,
)

router = APIRouter(prefix="/api/v1", tags=["sharing"])


class ShareInput(BaseModel):
    generation_id: UUID
    allow_prompt: bool = False
    expires_in_hours: int | None = Field(default=None, ge=1, le=24 * 30)


@router.post("/shares", status_code=status.HTTP_201_CREATED)
async def create_share(
    data: ShareInput,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> dict:
    expires_at = (
        datetime.now(UTC) + timedelta(hours=data.expires_in_hours)
        if data.expires_in_hours
        else None
    )
    raw, model = await library.create_share(
        user_id=current_user.id,
        generation_id=data.generation_id,
        allow_prompt=data.allow_prompt,
        expires_at=expires_at,
    )
    return {
        "id": str(model.id),
        "token": raw,
        "path": f"/s/{raw}",
        "allow_prompt": model.allow_prompt,
        "expires_at": model.expires_at.isoformat() if model.expires_at else None,
    }


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: UUID, current_user: CurrentUserDep, library: LibraryRepoDep
) -> Response:
    await library.revoke_share(current_user.id, share_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/shares/{token}")
async def public_share(
    token: str,
    library: LibraryRepoDep,
    storage: ObjectStorageDep,
) -> dict:
    found = await library.share_by_token(token)
    if found is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Link indisponivel.")
    link, generation = found
    image_url = await storage.presigned_get_url(generation.result_object_key, expires_seconds=300)
    payload = {
        "imageUrl": image_url,
        "title": generation.title,
        "createdAt": generation.created_at.isoformat(),
    }
    if link.allow_prompt:
        payload["prompt"] = generation.prompt
    return payload
