"""Persistencia de colecoes, tags, favoritos, links e denuncias."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.image_generation.adapters.repositories.models import (
    CollectionItemModel,
    CollectionModel,
    GenerationModel,
    GenerationTagModel,
    ReportModel,
    ShareLinkModel,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
)
from shared_kernel.errors import DomainError, NotFoundError

MAX_COLLECTIONS = 50
MAX_TAGS = 5
MAX_TAG_LEN = 32
MAX_BATCH_DELETE = 50
MAX_EXPORT = 50


def normalize_tag(tag: str) -> str:
    cleaned = re.sub(r"\s+", " ", tag.strip().lower())
    if not cleaned or len(cleaned) > MAX_TAG_LEN:
        raise DomainError("Tag invalida.")
    if not re.fullmatch(r"[\w\- ]+", cleaned, flags=re.UNICODE):
        raise DomainError("Tag invalida.")
    return cleaned


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _owned_generation(self, user_id: UUID, generation_id: UUID) -> GenerationModel:
        model = await self._session.get(GenerationModel, generation_id)
        if model is None or model.deleted_at is not None or model.user_id != user_id:
            raise NotFoundError("Geracao nao encontrada.")
        return model

    async def create_collection(self, user_id: UUID, name: str) -> dict:
        count = (
            await self._session.execute(
                select(func.count(CollectionModel.id)).where(CollectionModel.user_id == user_id)
            )
        ).scalar_one()
        if count >= MAX_COLLECTIONS:
            raise DomainError("Limite de colecoes atingido.")
        model = CollectionModel(
            user_id=user_id,
            name=name.strip()[:80],
            position=int(count),
        )
        self._session.add(model)
        await self._session.flush()
        return {"id": str(model.id), "name": model.name, "position": model.position}

    async def list_collections(self, user_id: UUID) -> list[dict]:
        models = (
            (
                await self._session.execute(
                    select(CollectionModel)
                    .where(CollectionModel.user_id == user_id)
                    .order_by(CollectionModel.position, CollectionModel.created_at)
                )
            )
            .scalars()
            .all()
        )
        result = []
        for model in models:
            count = (
                await self._session.execute(
                    select(func.count(CollectionItemModel.generation_id)).where(
                        CollectionItemModel.collection_id == model.id
                    )
                )
            ).scalar_one()
            result.append(
                {
                    "id": str(model.id),
                    "name": model.name,
                    "position": model.position,
                    "items": int(count),
                }
            )
        return result

    async def _owned_collection(self, user_id: UUID, collection_id: UUID) -> CollectionModel:
        model = await self._session.get(CollectionModel, collection_id)
        if model is None or model.user_id != user_id:
            raise NotFoundError("Colecao nao encontrada.")
        return model

    async def rename_collection(self, user_id: UUID, collection_id: UUID, name: str) -> dict:
        model = await self._owned_collection(user_id, collection_id)
        model.name = name.strip()[:80]
        model.updated_at = datetime.now(UTC)
        await self._session.flush()
        return {"id": str(model.id), "name": model.name}

    async def delete_collection(self, user_id: UUID, collection_id: UUID) -> None:
        model = await self._owned_collection(user_id, collection_id)
        await self._session.delete(model)
        await self._session.flush()

    async def add_to_collection(
        self, user_id: UUID, collection_id: UUID, generation_id: UUID
    ) -> None:
        await self._owned_collection(user_id, collection_id)
        await self._owned_generation(user_id, generation_id)
        exists = await self._session.get(CollectionItemModel, (collection_id, generation_id))
        if exists is not None:
            return
        max_pos = (
            await self._session.execute(
                select(func.coalesce(func.max(CollectionItemModel.position), -1)).where(
                    CollectionItemModel.collection_id == collection_id
                )
            )
        ).scalar_one()
        self._session.add(
            CollectionItemModel(
                collection_id=collection_id,
                generation_id=generation_id,
                position=int(max_pos) + 1,
            )
        )
        await self._session.flush()

    async def remove_from_collection(
        self, user_id: UUID, collection_id: UUID, generation_id: UUID
    ) -> None:
        await self._owned_collection(user_id, collection_id)
        await self._session.execute(
            delete(CollectionItemModel).where(
                CollectionItemModel.collection_id == collection_id,
                CollectionItemModel.generation_id == generation_id,
            )
        )
        await self._session.flush()

    async def collection_items(self, user_id: UUID, collection_id: UUID) -> list[dict]:
        await self._owned_collection(user_id, collection_id)
        rows = (
            await self._session.execute(
                select(CollectionItemModel, GenerationModel)
                .join(
                    GenerationModel,
                    GenerationModel.id == CollectionItemModel.generation_id,
                )
                .where(
                    CollectionItemModel.collection_id == collection_id,
                    GenerationModel.deleted_at.is_(None),
                )
                .order_by(
                    CollectionItemModel.position,
                    CollectionItemModel.added_at,
                )
            )
        ).all()
        return [
            {
                "id": str(gen.id),
                "title": gen.title,
                "image_url": gen.result_image_url,
                "position": item.position,
                "favorite": gen.is_favorite,
                "hidden": gen.hidden_at is not None,
            }
            for item, gen in rows
        ]

    async def set_favorite(self, user_id: UUID, generation_id: UUID, favorite: bool) -> None:
        model = await self._owned_generation(user_id, generation_id)
        model.is_favorite = favorite
        await self._session.flush()

    async def set_tags(self, user_id: UUID, generation_id: UUID, tags: list[str]) -> list[str]:
        await self._owned_generation(user_id, generation_id)
        normalized = []
        for tag in tags:
            value = normalize_tag(tag)
            if value not in normalized:
                normalized.append(value)
        if len(normalized) > MAX_TAGS:
            raise DomainError("Limite de tags atingido.")
        await self._session.execute(
            delete(GenerationTagModel).where(GenerationTagModel.generation_id == generation_id)
        )
        for value in normalized:
            self._session.add(
                GenerationTagModel(
                    generation_id=generation_id,
                    tag=value[:MAX_TAG_LEN],
                    normalized=value,
                )
            )
        await self._session.flush()
        return normalized

    async def list_tags(self, user_id: UUID) -> list[dict]:
        rows = (
            await self._session.execute(
                select(
                    GenerationTagModel.normalized,
                    func.count(GenerationTagModel.generation_id),
                )
                .join(GenerationModel, GenerationModel.id == GenerationTagModel.generation_id)
                .where(
                    GenerationModel.user_id == user_id,
                    GenerationModel.deleted_at.is_(None),
                )
                .group_by(GenerationTagModel.normalized)
                .order_by(func.count(GenerationTagModel.generation_id).desc())
            )
        ).all()
        return [{"tag": tag, "count": int(count)} for tag, count in rows]

    async def search(
        self,
        user_id: UUID,
        *,
        query: str | None,
        kind: GenerationKind | None,
        aspect_ratio: str | None,
        favorite: bool | None,
        collection_id: UUID | None,
        since: datetime | None,
        until: datetime | None,
        cursor: UUID | None,
        limit: int,
    ) -> tuple[list[Generation], UUID | None]:
        conditions = [
            GenerationModel.user_id == user_id,
            GenerationModel.deleted_at.is_(None),
            GenerationModel.hidden_at.is_(None),
        ]
        if query:
            fts = func.to_tsvector("simple", GenerationModel.prompt).op("@@")(
                func.plainto_tsquery("simple", query)
            )
            conditions.append(or_(fts, GenerationModel.prompt.ilike(f"%{query[:100]}%")))
        if kind is not None:
            conditions.append(GenerationModel.kind == kind.value)
        if aspect_ratio is not None:
            conditions.append(GenerationModel.aspect_ratio == aspect_ratio)
        if favorite is not None:
            conditions.append(GenerationModel.is_favorite.is_(favorite))
        if since is not None:
            conditions.append(GenerationModel.created_at >= since)
        if until is not None:
            conditions.append(GenerationModel.created_at <= until)
        stmt = select(GenerationModel)
        if collection_id is not None:
            await self._owned_collection(user_id, collection_id)
            stmt = stmt.join(
                CollectionItemModel,
                CollectionItemModel.generation_id == GenerationModel.id,
            ).where(CollectionItemModel.collection_id == collection_id)
        stmt = stmt.where(*conditions).order_by(
            GenerationModel.created_at.desc(), GenerationModel.id.desc()
        )
        if cursor is not None:
            cursor_model = await self._session.get(GenerationModel, cursor)
            if cursor_model is not None:
                stmt = stmt.where(
                    or_(
                        GenerationModel.created_at < cursor_model.created_at,
                        and_(
                            GenerationModel.created_at == cursor_model.created_at,
                            GenerationModel.id < cursor_model.id,
                        ),
                    )
                )
        models = (await self._session.execute(stmt.limit(limit + 1))).scalars().all()
        next_cursor = models[-1].id if len(models) > limit else None
        models = models[:limit]
        from modules.image_generation.adapters.repositories.generation_repository import (
            SQLAlchemyGenerationRepository,
        )

        repo = SQLAlchemyGenerationRepository(self._session)
        return [repo._to_entity(model) for model in models], next_cursor

    async def batch_soft_delete(self, user_id: UUID, ids: list[UUID]) -> int:
        if len(ids) > MAX_BATCH_DELETE:
            raise DomainError("Limite de exclusao em lote excedido.")
        result = await self._session.execute(
            select(GenerationModel).where(
                GenerationModel.user_id == user_id,
                GenerationModel.id.in_(ids),
                GenerationModel.deleted_at.is_(None),
            )
        )
        models = result.scalars().all()
        now = datetime.now(UTC)
        for model in models:
            model.deleted_at = now
        await self._session.flush()
        return len(models)

    async def hide_generation(self, generation_id: UUID) -> bool:
        model = await self._session.get(GenerationModel, generation_id)
        if model is None:
            return False
        model.hidden_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def owned_by_ids(self, user_id: UUID, ids: list[UUID]) -> list[GenerationModel]:
        if not ids or len(ids) > MAX_EXPORT:
            raise DomainError("Limite de exportacao excedido.")
        return (
            (
                await self._session.execute(
                    select(GenerationModel).where(
                        GenerationModel.user_id == user_id,
                        GenerationModel.id.in_(ids),
                        GenerationModel.deleted_at.is_(None),
                        GenerationModel.hidden_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

    # ---- sharing ----

    async def create_share(
        self,
        *,
        user_id: UUID,
        generation_id: UUID,
        allow_prompt: bool,
        expires_at: datetime | None,
    ) -> tuple[str, ShareLinkModel]:
        await self._owned_generation(user_id, generation_id)
        raw = secrets.token_urlsafe(32)
        model = ShareLinkModel(
            user_id=user_id,
            generation_id=generation_id,
            token_hash=token_hash(raw),
            allow_prompt=allow_prompt,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return raw, model

    async def share_by_token(self, raw: str) -> tuple[ShareLinkModel, GenerationModel] | None:
        model = (
            await self._session.execute(
                select(ShareLinkModel).where(ShareLinkModel.token_hash == token_hash(raw))
            )
        ).scalar_one_or_none()
        if model is None or model.revoked_at is not None:
            return None
        if model.expires_at is not None and model.expires_at <= datetime.now(UTC):
            return None
        generation = await self._session.get(GenerationModel, model.generation_id)
        if (
            generation is None
            or generation.deleted_at is not None
            or generation.hidden_at is not None
            or generation.result_object_key is None
        ):
            return None
        return model, generation

    async def revoke_share(self, user_id: UUID, share_id: UUID) -> bool:
        model = await self._session.get(ShareLinkModel, share_id)
        if model is None or model.user_id != user_id:
            return False
        model.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def revoke_shares_for_generation(self, generation_id: UUID) -> int:
        result = await self._session.execute(
            select(ShareLinkModel).where(
                ShareLinkModel.generation_id == generation_id,
                ShareLinkModel.revoked_at.is_(None),
            )
        )
        models = result.scalars().all()
        now = datetime.now(UTC)
        for model in models:
            model.revoked_at = now
        await self._session.flush()
        return len(models)

    # ---- reports ----

    async def create_report(
        self,
        *,
        generation_id: UUID,
        reason: str,
        details: str | None,
        reporter_user_id: UUID | None,
        anonymous_session_id: str | None,
        ip_hash: str | None,
    ) -> dict:
        generation = await self._session.get(GenerationModel, generation_id)
        if generation is None or generation.deleted_at is not None:
            raise NotFoundError("Imagem nao encontrada.")
        model = ReportModel(
            id=uuid4(),
            generation_id=generation_id,
            reporter_user_id=reporter_user_id,
            anonymous_session_id=anonymous_session_id,
            ip_hash=ip_hash,
            reason=reason[:32],
            details=(details or "")[:500] or None,
        )
        self._session.add(model)
        await self._session.flush()
        return {"id": str(model.id), "status": model.status}

    async def report_owner(self, report_id: UUID) -> UUID | None:
        row = await self._session.execute(
            select(GenerationModel.user_id)
            .join(ReportModel, ReportModel.generation_id == GenerationModel.id)
            .where(ReportModel.id == report_id)
        )
        return row.scalar_one_or_none()

    async def list_reports(self, *, status: str = "pending", limit: int = 100) -> list[dict]:
        models = (
            (
                await self._session.execute(
                    select(ReportModel)
                    .where(ReportModel.status == status)
                    .order_by(ReportModel.created_at.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": str(model.id),
                "generation_id": str(model.generation_id),
                "reason": model.reason,
                "details": model.details,
                "status": model.status,
                "created_at": model.created_at.isoformat(),
            }
            for model in models
        ]

    async def review_report(
        self,
        report_id: UUID,
        *,
        action: str,
        reviewer_id: UUID,
    ) -> dict:
        model = await self._session.get(ReportModel, report_id)
        if model is None:
            raise NotFoundError("Denuncia nao encontrada.")
        model.status = "reviewed"
        model.action = action[:32]
        model.reviewer_id = reviewer_id
        model.reviewed_at = datetime.now(UTC)
        if action == "hide":
            await self.hide_generation(model.generation_id)
            await self.revoke_shares_for_generation(model.generation_id)
        elif action == "remove_link":
            await self.revoke_shares_for_generation(model.generation_id)
        await self._session.flush()
        return {"id": str(model.id), "action": model.action, "status": model.status}
