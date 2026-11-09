"""Biblioteca pessoal: colecoes, favoritos, tags, busca, lote e export."""

from __future__ import annotations

import base64
import io
import zipfile
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    CurrentUserDep,
    LibraryRepoDep,
    ObjectStorageDep,
)
from modules.image_generation.application.use_cases.read_generations import _to_output
from modules.image_generation.domain.entities import GenerationKind

router = APIRouter(prefix="/api/v1/library", tags=["library"])


class CollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class FavoriteInput(BaseModel):
    favorite: bool


class TagsInput(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=5)


class BatchDeleteInput(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=50)


def _encode_cursor(generation_id: UUID | None) -> str | None:
    if generation_id is None:
        return None
    return base64.urlsafe_b64encode(str(generation_id).encode()).decode()


@router.get("/collections")
async def list_collections(current_user: CurrentUserDep, library: LibraryRepoDep) -> list[dict]:
    return await library.list_collections(current_user.id)


@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionInput, current_user: CurrentUserDep, library: LibraryRepoDep
) -> dict:
    return await library.create_collection(current_user.id, data.name)


@router.patch("/collections/{collection_id}")
async def rename_collection(
    collection_id: UUID,
    data: CollectionInput,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> dict:
    return await library.rename_collection(current_user.id, collection_id, data.name)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID, current_user: CurrentUserDep, library: LibraryRepoDep
) -> Response:
    await library.delete_collection(current_user.id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/collections/{collection_id}/items")
async def collection_items(
    collection_id: UUID, current_user: CurrentUserDep, library: LibraryRepoDep
) -> list[dict]:
    return await library.collection_items(current_user.id, collection_id)


@router.post(
    "/collections/{collection_id}/items/{generation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_to_collection(
    collection_id: UUID,
    generation_id: UUID,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> Response:
    await library.add_to_collection(current_user.id, collection_id, generation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/collections/{collection_id}/items/{generation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_from_collection(
    collection_id: UUID,
    generation_id: UUID,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> Response:
    await library.remove_from_collection(current_user.id, collection_id, generation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/generations/{generation_id}/favorite")
async def set_favorite(
    generation_id: UUID,
    data: FavoriteInput,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> dict:
    await library.set_favorite(current_user.id, generation_id, data.favorite)
    return {"id": str(generation_id), "favorite": data.favorite}


@router.put("/generations/{generation_id}/tags")
async def set_tags(
    generation_id: UUID,
    data: TagsInput,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> dict:
    tags = await library.set_tags(current_user.id, generation_id, data.tags)
    return {"id": str(generation_id), "tags": tags}


@router.get("/tags")
async def list_tags(current_user: CurrentUserDep, library: LibraryRepoDep) -> list[dict]:
    return await library.list_tags(current_user.id)


@router.get("/search")
async def search_library(
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
    storage: ObjectStorageDep,
    q: str | None = Query(default=None, max_length=200),
    kind: GenerationKind | None = None,
    aspect_ratio: str | None = Query(default=None, max_length=16),
    favorite: bool | None = None,
    collection_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=24, ge=1, le=50),
) -> dict:
    import base64 as _b64

    cursor_id = None
    if cursor:
        try:
            cursor_id = UUID(_b64.urlsafe_b64decode(cursor.encode()).decode())
        except Exception as exc:
            from shared_kernel.errors import DomainError

            raise DomainError("Cursor invalido.") from exc
    items, next_cursor_id = await library.search(
        current_user.id,
        query=q,
        kind=kind,
        aspect_ratio=aspect_ratio,
        favorite=favorite,
        collection_id=collection_id,
        since=since,
        until=until,
        cursor=cursor_id,
        limit=limit,
    )
    outputs = [await _to_output(item, storage) for item in items]
    return {
        "items": outputs,
        "next_cursor": _encode_cursor(next_cursor_id),
    }


@router.post("/batch-delete")
async def batch_delete(
    data: BatchDeleteInput,
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
) -> dict:
    deleted = await library.batch_soft_delete(current_user.id, data.ids)
    return {"deleted": deleted}


@router.get("/export")
async def export_zip(
    current_user: CurrentUserDep,
    library: LibraryRepoDep,
    storage: ObjectStorageDep,
    ids: str = Query(..., description="IDs separados por virgula"),
) -> StreamingResponse:
    parsed: list[UUID] = []
    for raw in ids.split(",")[:50]:
        try:
            parsed.append(UUID(raw.strip()))
        except ValueError:
            continue
    models = await library.owned_by_ids(current_user.id, parsed)
    spool = io.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_STORED) as archive:
        for model in models:
            if not model.result_object_key:
                continue
            try:
                data = await storage.get_object(model.result_object_key)
            except Exception:  # noqa: S112
                continue
            archive.writestr(f"{model.id}.png", data)
        archive.writestr(
            "README.txt",
            "Exportacao AImaginator: somente versoes com marca d'agua.\n",
        )
    spool.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="aimaginator.zip"'}

    def _iter():
        while chunk := spool.read(64 * 1024):
            yield chunk
        spool.close()

    return StreamingResponse(_iter(), media_type="application/zip", headers=headers)
