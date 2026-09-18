"""Porta de saida do modulo prompt_quota (application -> infra)."""

from __future__ import annotations

from typing import Protocol

from modules.prompt_quota.domain.entities import PromptQuota


class PromptQuotaStorePort(Protocol):
    """Persistencia das chances consumidas (janela deslizante de 24h)."""

    async def get_quota(self, *, principal_id: str, total: int) -> PromptQuota:
        """Devolve o estado atual da cota sem consumir."""
        ...

    async def consume(self, *, principal_id: str, total: int) -> PromptQuota:
        """Consome uma chance. Levanta QuotaExceededError se esgotada."""
        ...
