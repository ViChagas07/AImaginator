"""Rotas da galeria (pessoal + publica) — Bloco 3.

- GET    /api/v1/gallery/public              -> vitrine publica (cache SWR)
- GET    /api/v1/gallery/me                  -> artes do usuario (paginado)
- PATCH  /api/v1/gallery/me/{id}             -> renomeia uma arte (dono)
- DELETE /api/v1/gallery/me/{id}             -> exclui (soft delete, dono)
- POST   /api/v1/gallery/me/claim            -> vincula artes anonimas ao usuario
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from apps.api.dependencies import (
    CurrentUserDep,
    GenerationRepoDep,
    SettingsDep,
    SWRCacheDep,
    resolve_anonymous_session,
)
from modules.image_generation.application.schemas import (
    GalleryArtOutput,
    GalleryPage,
    GenerationOutput,
)
from modules.image_generation.contracts import (
    ClaimAnonymousArts,
    DeleteGeneration,
    ListPublicShowcase,
    ListUserGenerations,
    RenameGeneration,
    RenameGenerationInput,
)

router = APIRouter(prefix="/api/v1/gallery", tags=["gallery"])

_PUBLIC_SIZE = 24


def _to_art(output: GenerationOutput) -> GalleryArtOutput:
    return GalleryArtOutput(
        id=output.id,
        image_url=output.result_image_url,
        prompt=output.prompt,
        title=output.title,
        status=output.status,
        created_at=output.created_at,
    )


@router.get("/public", response_model=GalleryPage)
async def public_gallery(
    generations: GenerationRepoDep, cache: SWRCacheDep
) -> GalleryPage:
    outputs = await ListPublicShowcase(generations=generations, cache=cache).execute()
    return GalleryPage(items=[_to_art(o) for o in outputs], cursor=None)


@router.get("/me", response_model=GalleryPage)
async def my_gallery(
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> GalleryPage:
    page = await ListUserGenerations(generations).execute(
        user_id=current_user.id, cursor=cursor, limit=limit
    )
    return GalleryPage(
        items=[_to_art(o) for o in page.items],
        cursor=page.next_cursor,
    )


@router.patch("/me/{generation_id}", response_model=GalleryArtOutput)
async def rename_art(
    generation_id: UUID,
    data: RenameGenerationInput,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
) -> GalleryArtOutput:
    output = await RenameGeneration(generations).execute(
        user_id=current_user.id, generation_id=generation_id, title=data.title
    )
    return _to_art(output)


@router.delete("/me/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_art(
    generation_id: UUID,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
) -> Response:
    await DeleteGeneration(generations).execute(
        user_id=current_user.id, generation_id=generation_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/claim")
async def claim_anonymous_arts(
    request: Request,
    current_user: CurrentUserDep,
    generations: GenerationRepoDep,
    settings: SettingsDep,
) -> dict:
    anonymous_id, _token = resolve_anonymous_session(request, settings)
    claimed = await ClaimAnonymousArts(generations).execute(
        anonymous_session_id=anonymous_id, user_id=current_user.id
    )
    return {"claimed": claimed}
