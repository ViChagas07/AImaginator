"""Portas de persistencia/estado das penalidades de moderacao."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from modules.image_generation.domain.moderation import ModerationEvent


class ModerationEventRepositoryPort(Protocol):
    async def add(self, event: ModerationEvent) -> None: ...

    async def count_since(
        self,
        *,
        since: datetime,
        user_id: UUID | None = None,
        anonymous_session_id: str | None = None,
        ip_hash: str | None = None,
    ) -> int: ...


class PenaltyStorePort(Protocol):
    async def get_block_until(self, *, keys: Sequence[str]) -> datetime | None: ...

    async def set_block(self, *, keys: Sequence[str], until: datetime) -> None: ...
