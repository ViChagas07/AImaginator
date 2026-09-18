"""Testes do store Redis de cota de prompts (janela deslizante de 24h)."""

from __future__ import annotations

import pytest

from modules.prompt_quota.adapters.redis_quota_store import RedisPromptQuotaStore
from shared_kernel.errors import QuotaExceededError


@pytest.mark.unit
class TestRedisPromptQuotaStore:
    async def test_quota_inicial_cheia(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        quota = await store.get_quota(principal_id="anon:x", total=1)
        assert quota.chances_remaining == 1
        assert quota.chances_total == 1
        assert quota.next_available_at is None

    async def test_consume_decrementa(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        quota = await store.consume(principal_id="user:1", total=3)
        assert quota.chances_remaining == 2

    async def test_consome_todas_e_esgota(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        await store.consume(principal_id="user:1", total=3)
        await store.consume(principal_id="user:1", total=3)
        quota = await store.consume(principal_id="user:1", total=3)
        assert quota.chances_remaining == 0

        with pytest.raises(QuotaExceededError) as exc_info:
            await store.consume(principal_id="user:1", total=3)
        assert exc_info.value.retry_after_seconds is not None
        assert "next_available_at" in exc_info.value.details

    async def test_anonimo_tem_uma_chance(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        quota = await store.get_quota(principal_id="anon:a", total=1)
        assert quota.chances_total == 1
        assert quota.chances_remaining == 1

    async def test_usuarios_diferentes_nao_compartilham_cota(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        await store.consume(principal_id="user:1", total=1)  # esgota o user:1
        quota = await store.get_quota(principal_id="user:2", total=1)
        assert quota.chances_remaining == 1

    async def test_expiracao_libera_chance(self, fake_redis) -> None:
        store = RedisPromptQuotaStore(fake_redis)
        # Simula consumo antigo (fora da janela) removendo o membro via janela.

        await store.consume(principal_id="anon:old", total=1)
        # Remove manualmente o membro expirado simulando passagem de tempo.
        key = "prompt-quota:anon:old"
        members = await fake_redis.zrange(key, 0, -1, withscores=True)
        assert len(members) == 1
        old_score = members[0][1]
        # Reinsere com timestamp antigo (fora da janela de 24h).
        await fake_redis.zadd(key, {members[0][0]: old_score - 90000})
        quota = await store.get_quota(principal_id="anon:old", total=1)
        assert quota.chances_remaining == 1
