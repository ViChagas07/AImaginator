"""Ticket de stream em Redis: TTL curto e consumo atomico (GETDEL via Lua)."""

from __future__ import annotations

import json
import secrets
from uuid import UUID

from modules.image_generation.application.ports.stream_ticket import StreamTicketData

_LUA_REDEEM = """
local value = redis.call('GET', KEYS[1])
if value then
  redis.call('DEL', KEYS[1])
end
return value
"""


class RedisStreamTicketStore:
    def __init__(self, redis_client, *, ttl_seconds: int = 60) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    @staticmethod
    def _key(ticket: str) -> str:
        return f"stream-ticket:{ticket}"

    async def issue(
        self,
        *,
        generation_id: UUID,
        user_id: UUID | None,
        anonymous_session_id: str | None,
    ) -> str:
        ticket = secrets.token_urlsafe(32)
        payload = json.dumps(
            {
                "generation_id": str(generation_id),
                "user_id": str(user_id) if user_id else None,
                "anonymous_session_id": anonymous_session_id,
            }
        )
        await self._redis.set(self._key(ticket), payload, ex=self._ttl)
        return ticket

    async def redeem(self, ticket: str) -> StreamTicketData | None:
        raw = await self._redis.eval(_LUA_REDEEM, 1, self._key(ticket))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return StreamTicketData(
                generation_id=UUID(payload["generation_id"]),
                user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
                anonymous_session_id=payload.get("anonymous_session_id"),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
