"""Casos de uso do modulo prompt_quota (checar / consumir chances)."""

from __future__ import annotations

from modules.prompt_quota.application.ports import PromptQuotaStorePort
from modules.prompt_quota.domain.entities import PromptQuota


class GetPromptQuota:
    """Consulta a cota de prompts do principal (sem efeito colateral)."""

    def __init__(self, store: PromptQuotaStorePort, *, total: int) -> None:
        self._store = store
        self._total = total

    async def execute(self, principal_id: str) -> PromptQuota:
        return await self._store.get_quota(principal_id=principal_id, total=self._total)


class ConsumePromptQuota:
    """Consome uma chance de prompt (levanta QuotaExceededError se esgotada)."""

    def __init__(self, store: PromptQuotaStorePort, *, total: int) -> None:
        self._store = store
        self._total = total

    async def execute(self, principal_id: str) -> PromptQuota:
        return await self._store.consume(principal_id=principal_id, total=self._total)
