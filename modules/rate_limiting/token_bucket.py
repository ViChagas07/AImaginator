"""Token Bucket distribuido (Redis como store compartilhado).

Funciona corretamente com multiplas replicas da API porque o estado
do balde vive no Redis, nao em memoria de processo. Script Lua
garante atomicidade (check + consumo em uma unica operacao).
"""

from __future__ import annotations

import time

from shared_kernel.errors import RateLimitExceededError

# Lua: recarrega tokens proporcionalmente ao tempo decorrido e consome 1.
# KEYS[1] = chave do balde; ARGV = capacity, refill_per_sec, now
_LUA_TOKEN_BUCKET = """
local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local capacity = tonumber(ARGV[1])
local refill_per_sec = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local tokens = tonumber(bucket[1]) or capacity
local ts = tonumber(bucket[2]) or now

tokens = math.min(capacity, tokens + (now - ts) * refill_per_sec)

if tokens < 1 then
  redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', KEYS[1], math.ceil(capacity / refill_per_sec) + 1)
  return {0, math.ceil((1 - tokens) / refill_per_sec)}
end

tokens = tokens - 1
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], math.ceil(capacity / refill_per_sec) + 1)
return {1, 0}
"""


class TokenBucket:
    """Rate limiter por chave arbitraria (user:{id}, ip:{addr}, endpoint...)."""

    def __init__(self, redis_client, *, capacity: int, window_seconds: int) -> None:
        if capacity <= 0 or window_seconds <= 0:
            msg = "capacity e window_seconds devem ser positivos"
            raise ValueError(msg)
        self._redis = redis_client
        self.capacity = capacity
        self.refill_per_sec = capacity / window_seconds

    async def consume(self, key: str) -> None:
        """Consome 1 token ou levanta RateLimitExceededError com Retry-After."""
        now = time.monotonic()
        allowed, retry_after = await self._redis.eval(
            _LUA_TOKEN_BUCKET, 1, f"tb:{key}", self.capacity, self.refill_per_sec, now
        )
        if not allowed:
            raise RateLimitExceededError(retry_after_seconds=max(int(retry_after), 1))

    async def try_consume(self, key: str) -> bool:
        """Versao nao-excepcional (retorna False em vez de levantar)."""
        try:
            await self.consume(key)
        except RateLimitExceededError:
            return False
        return True
