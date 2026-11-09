"""Servicos de administracao: usuarios, moderacao, creditos e auditoria."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from modules.admin.adapters.repository import SQLAlchemyAdminAuditRepository
from modules.image_generation.application.ports.moderation import (
    ModerationEventRepositoryPort,
)
from modules.users.application.credits import CreditLedgerService
from modules.users.application.ports import UserRepositoryPort
from modules.users.domain.entities import User
from shared_kernel.errors import ForbiddenError, NotFoundError


class AdminService:
    def __init__(
        self,
        *,
        users: UserRepositoryPort,
        audit: SQLAlchemyAdminAuditRepository,
        moderation: ModerationEventRepositoryPort,
        credits: CreditLedgerService,
        clock=None,
    ) -> None:
        self._users = users
        self._audit = audit
        self._moderation = moderation
        self._credits = credits
        self._clock = clock or (lambda: datetime.now(UTC))

    async def _record(
        self,
        *,
        actor: User,
        action: str,
        target_type: str | None,
        target_id: str | None,
        result: str,
        detail: dict | None = None,
    ) -> None:
        await self._audit.add(
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            detail=detail or {},
        )

    async def record(
        self,
        *,
        actor: User,
        action: str,
        target_type: str | None,
        target_id: str | None,
        result: str,
        detail: dict | None = None,
    ) -> None:
        await self._record(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            detail=detail,
        )

    async def list_flagged_users(self, *, limit: int = 100) -> list[dict]:
        users = await self._users.list_flagged(limit=limit)
        return [
            {
                "id": str(user.id),
                "handle": user.handle,
                "plan": user.plan,
                "moderation_flag": user.moderation_flag,
                "blocked_until": (
                    user.moderation_blocked_until.isoformat()
                    if user.moderation_blocked_until
                    else None
                ),
                "generation_credits": user.generation_credits,
            }
            for user in users
        ]

    async def moderation_stats(self, *, days: int = 7) -> list[dict]:
        since = self._clock() - timedelta(days=max(1, min(days, 90)))
        return await self._moderation.aggregate_since(since=since)

    async def block_user(self, *, actor: User, user_id: UUID, minutes: int) -> dict:
        user = await self._users.get_by_id(user_id)
        if user is None:
            await self._record(
                actor=actor,
                action="user.block",
                target_type="user",
                target_id=str(user_id),
                result="not_found",
            )
            raise NotFoundError("Usuario nao encontrado.")
        until = self._clock() + timedelta(minutes=max(1, min(minutes, 60 * 24 * 30)))
        user.moderation_flag = True
        user.moderation_blocked_until = until
        user.updated_at = self._clock()
        await self._users.save(user)
        await self._record(
            actor=actor,
            action="user.block",
            target_type="user",
            target_id=str(user.id),
            result="ok",
            detail={"minutes": minutes},
        )
        return {"id": str(user.id), "blocked_until": until.isoformat()}

    async def unblock_user(self, *, actor: User, user_id: UUID) -> dict:
        user = await self._users.get_by_id(user_id)
        if user is None:
            await self._record(
                actor=actor,
                action="user.unblock",
                target_type="user",
                target_id=str(user_id),
                result="not_found",
            )
            raise NotFoundError("Usuario nao encontrado.")
        user.moderation_flag = False
        user.moderation_blocked_until = None
        user.updated_at = self._clock()
        await self._users.save(user)
        await self._record(
            actor=actor,
            action="user.unblock",
            target_type="user",
            target_id=str(user.id),
            result="ok",
        )
        return {"id": str(user.id), "blocked_until": None}

    async def adjust_credits(self, *, actor: User, user_id: UUID, delta: int, reason: str) -> dict:
        user = await self._users.get_by_id(user_id)
        if user is None:
            await self._record(
                actor=actor,
                action="credits.adjust",
                target_type="user",
                target_id=str(user_id),
                result="not_found",
            )
            raise NotFoundError("Usuario nao encontrado.")
        key = f"admin:{uuid4()}"
        updated = await self._credits.admin_adjust(
            user_id,
            delta=delta,
            idempotency_key=key,
            ref_id=str(actor.id),
            meta={"reason": reason[:80]},
        )
        await self._record(
            actor=actor,
            action="credits.adjust",
            target_type="user",
            target_id=str(user.id),
            result="ok",
            detail={"delta": delta, "reason": reason[:80]},
        )
        return {
            "id": str(updated.id),
            "generation_credits": updated.generation_credits,
        }

    async def list_audit(self, *, days: int = 7, limit: int = 100) -> list[dict]:
        since = self._clock() - timedelta(days=max(1, min(days, 90)))
        return await self._audit.list_since(since, limit=limit)

    async def reports_queue(self) -> list[dict]:
        # Estrutura pronta para a Fase 10; nunca inclui prompt.
        return []


def ensure_admin(user: User | None) -> User:
    if user is None or not user.is_admin:
        raise ForbiddenError("Acesso restrito a administradores.")
    return user
