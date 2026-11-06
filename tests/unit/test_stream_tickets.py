"""Ticket de stream: TTL curto, uso unico e vinculacao a geracao."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.adapters.redis_stream_tickets import RedisStreamTicketStore


@pytest.mark.unit
async def test_ticket_e_single_use(fake_redis) -> None:
    store = RedisStreamTicketStore(fake_redis, ttl_seconds=60)
    generation_id = uuid4()
    user_id = uuid4()
    ticket = await store.issue(
        generation_id=generation_id,
        user_id=user_id,
        anonymous_session_id=None,
    )
    first = await store.redeem(ticket)
    assert first is not None
    assert first.generation_id == generation_id
    assert first.user_id == user_id
    assert await store.redeem(ticket) is None


@pytest.mark.unit
async def test_ticket_anonimo_e_invalido_quando_sumiu(fake_redis) -> None:
    store = RedisStreamTicketStore(fake_redis, ttl_seconds=60)
    assert await store.redeem("ticket-que-nao-existe") is None
