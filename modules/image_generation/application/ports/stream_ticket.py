"""Ticket efemero de uso unico para o stream SSE (nunca JWT na URL)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StreamTicketData:
    generation_id: UUID
    user_id: UUID | None
    anonymous_session_id: str | None


class StreamTicketStorePort(Protocol):
    async def issue(
        self,
        *,
        generation_id: UUID,
        user_id: UUID | None,
        anonymous_session_id: str | None,
    ) -> str: ...

    async def redeem(self, ticket: str) -> StreamTicketData | None: ...
