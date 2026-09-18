"""Store Redis da cota de prompts (janela deslizante de 24h por chance).

Cada chance consumida vira um membro de um sorted set cujo score e o
timestamp de consumo. A cada leitura/consumo, membros com mais de 24h
sao removidos, de modo que cada chance "renasce" individualmente 24h
apos o uso (nao ha reset fixo a meia-noite). Scripts Lua garantem
atomicidade do check+consume mesmo com multiplas replicas da API.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from modules.prompt_quota.application.ports import PromptQuotaStorePort
from modules.prompt_quota.domain.entities import PromptQuota
from shared_kernel.errors import QuotaExceededError

_WINDOW_SECONDS = 24 * 60 * 60

# KEYS[1] = chave do sorted set; ARGV = total, now, window, member
_LUA_CONSUME = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[2] - ARGV[3])
local count = redis.call('ZCARD', KEYS[1])
local total = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local window = tonumber(ARGV[3])

if count >= total then
  local earliest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local next_ts = 0
  if earliest[2] then
    next_ts = tonumber(earliest[2]) + window
  else
    next_ts = now + window
  end
  redis.call('PEXPIRE', KEYS[1], math.max(1000, (next_ts - now) * 1000 + 1000))
  return {0, count, next_ts}
end

redis.call('ZADD', KEYS[1], now, ARGV[4])
count = count + 1
redis.call('PEXPIRE', KEYS[1], window * 1000 + 1000)
return {1, count, 0}
"""

# KEYS[1] = chave do sorted set; ARGV = total, now, window
_LUA_STATUS = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[2] - ARGV[3])
local count = redis.call('ZCARD', KEYS[1])
local total = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local window = tonumber(ARGV[3])
local remaining = math.max(0, total - count)
local next_ts = 0
if remaining == 0 and count > 0 then
  local earliest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  next_ts = tonumber(earliest[2]) + window
end
if count == 0 then
  redis.call('DEL', KEYS[1])
else
  redis.call('PEXPIRE', KEYS[1], window * 1000 + 1000)
end
return {remaining, total, next_ts}
"""


class RedisPromptQuotaStore(PromptQuotaStorePort):
    def __init__(self, redis_client, *, namespace: str = "prompt-quota") -> None:
        self._redis = redis_client
        self._namespace = namespace

    def _key(self, principal_id: str) -> str:
        return f"{self._namespace}:{principal_id}"

    async def get_quota(self, *, principal_id: str, total: int) -> PromptQuota:
        now = int(time.time())
        remaining, total, next_ts = await self._redis.eval(
            _LUA_STATUS, 1, self._key(principal_id), total, now, _WINDOW_SECONDS
        )
        return self._to_quota(int(remaining), int(total), int(next_ts))

    async def consume(self, *, principal_id: str, total: int) -> PromptQuota:
        now = int(time.time())
        member = uuid4().hex
        allowed, count, next_ts = await self._redis.eval(
            _LUA_CONSUME, 1, self._key(principal_id), total, now, _WINDOW_SECONDS, member
        )
        allowed = int(allowed)
        count = int(count)
        next_ts = int(next_ts)
        if not allowed:
            retry_after = max(1, next_ts - now)
            raise QuotaExceededError(
                "Cota de prompts esgotada.",
                retry_after_seconds=retry_after,
                details={"next_available_at": next_ts},
            )
        return PromptQuota(
            chances_remaining=max(0, total - count),
            chances_total=total,
            next_available_at=None,
        )

    @staticmethod
    def _to_quota(remaining: int, total: int, next_ts: int) -> PromptQuota:
        return PromptQuota(
            chances_remaining=max(0, remaining),
            chances_total=total,
            next_available_at=datetime.fromtimestamp(next_ts, UTC) if next_ts else None,
        )
