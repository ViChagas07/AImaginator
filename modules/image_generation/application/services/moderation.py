"""Servico de moderacao: registra eventos e aplica penalidades configuraveis."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from modules.image_generation.application.localization import warning_message_for
from modules.image_generation.application.ports.moderation import (
    ModerationEventRepositoryPort,
    PenaltyStorePort,
)
from modules.image_generation.domain.moderation import (
    ModerationCategory,
    ModerationEvent,
    ModerationLayer,
    PenaltyOutcome,
)
from modules.observability.metrics import MODERATION_EVENTS_TOTAL, PENALTIES_TOTAL
from modules.users.contracts import User, UserRepositoryPort

logger = logging.getLogger(__name__)


class ModerationService:
    def __init__(
        self,
        *,
        events: ModerationEventRepositoryPort,
        users: UserRepositoryPort,
        penalty_store: PenaltyStorePort,
        warn_at: int = 3,
        block_at: int = 5,
        review_at: int = 10,
        block_minutes: int = 60,
        review_block_hours: int = 24,
        window_hours: int = 24,
        store_prompt_text: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._events = events
        self._users = users
        self._penalty_store = penalty_store
        self._warn_at = warn_at
        self._block_at = block_at
        self._review_at = review_at
        self._block_minutes = block_minutes
        self._review_block_hours = review_block_hours
        self._window_hours = window_hours
        self._store_prompt_text = store_prompt_text
        self._clock = clock or (lambda: datetime.now(UTC))

    def principal_keys(
        self,
        *,
        user_id: UUID | None,
        anonymous_session_id: str | None,
        ip_hash: str | None,
    ) -> tuple[str, ...]:
        keys: list[str] = []
        if user_id is not None:
            keys.append(f"user:{user_id}")
        else:
            if anonymous_session_id:
                keys.append(f"anon:{anonymous_session_id}")
            if ip_hash:
                keys.append(f"ip:{ip_hash}")
        return tuple(keys)

    async def current_block(
        self,
        *,
        user: User | None,
        anonymous_session_id: str | None,
        ip_hash: str | None,
    ) -> datetime | None:
        now = self._clock()
        stored = await self._penalty_store.get_block_until(
            keys=self.principal_keys(
                user_id=user.id if user else None,
                anonymous_session_id=anonymous_session_id if user is None else None,
                ip_hash=ip_hash if user is None else None,
            )
        )
        db_until = user.moderation_blocked_until if user else None
        candidates = [value for value in (stored, db_until) if value is not None]
        active = [value for value in candidates if value > now]
        return max(active) if active else None

    async def record_moderation(
        self,
        *,
        category: ModerationCategory,
        layer: ModerationLayer,
        confidence: float,
        locale: str,
        prompt_text: str,
        user: User | None,
        anonymous_session_id: str | None,
        ip_hash: str | None,
        apply_penalty: bool = True,
    ) -> PenaltyOutcome:
        now = self._clock()
        event = ModerationEvent(
            category=category,
            layer=layer,
            confidence=confidence,
            locale=locale,
            prompt_hash=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            prompt_length=len(prompt_text),
            user_id=user.id if user else None,
            anonymous_session_id=anonymous_session_id if user is None else None,
            ip_hash=ip_hash,
            prompt_text=prompt_text[:200] if self._store_prompt_text else None,
            created_at=now,
        )
        await self._events.add(event)
        MODERATION_EVENTS_TOTAL.labels(
            category=category.value, layer=layer.value
        ).inc()

        if not apply_penalty:
            return PenaltyOutcome(
                level=0, warning_level=None, warning_message=None
            )

        count = await self._events.count_since(
            since=now - timedelta(hours=self._window_hours),
            user_id=user.id if user else None,
            anonymous_session_id=anonymous_session_id if user is None else None,
            ip_hash=ip_hash if user is None else None,
        )
        level = self._level_for(count)
        blocked_until: datetime | None = None
        keys = self.principal_keys(
            user_id=user.id if user else None,
            anonymous_session_id=anonymous_session_id if user is None else None,
            ip_hash=ip_hash if user is None else None,
        )

        if level >= 3:
            blocked_until = now + timedelta(hours=self._review_block_hours)
            if user is not None:
                user.moderation_flag = True
                user.moderation_blocked_until = blocked_until
                await self._users.save(user)
            await self._penalty_store.set_block(keys=keys, until=blocked_until)
            logger.warning(
                "moderation_account_under_review",
                extra={
                    "user_id": str(user.id) if user else None,
                    "anonymous_session_id": anonymous_session_id,
                    "count": count,
                    "category": category.value,
                    "locale": locale,
                },
            )
        elif level == 2:
            blocked_until = now + timedelta(minutes=self._block_minutes)
            if user is not None:
                user.moderation_blocked_until = blocked_until
                await self._users.save(user)
            await self._penalty_store.set_block(keys=keys, until=blocked_until)

        if level > 0:
            PENALTIES_TOTAL.labels(level=str(level)).inc()
        return PenaltyOutcome(
            level=level,
            warning_level=level if level > 0 else None,
            warning_message=warning_message_for(level, locale) if level > 0 else None,
            blocked_until=blocked_until,
        )

    def _level_for(self, count: int) -> int:
        if count >= self._review_at:
            return 3
        if count >= self._block_at:
            return 2
        if count >= self._warn_at:
            return 1
        return 0
