"""Persistencia de auditoria de administracao."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.admin.adapters.models import AdminAuditLogModel


class SQLAlchemyAdminAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_type: str | None,
        target_id: str | None,
        result: str,
        detail: dict | None = None,
    ) -> None:
        self._session.add(
            AdminAuditLogModel(
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                result=result,
                detail=detail,
            )
        )
        await self._session.flush()

    async def list_since(self, since: datetime, *, limit: int = 100) -> list[dict]:
        stmt = (
            select(AdminAuditLogModel)
            .where(AdminAuditLogModel.created_at >= since)
            .order_by(AdminAuditLogModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            {
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "result": row.result,
                "detail": row.detail or {},
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
