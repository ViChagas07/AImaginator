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

    async def release(self, *, principal_id: str) -> bool:
        """Devolve 1 chance (se houver). Atomico; True se removeu."""
        ...


class PromptQuotaConsumerPort(Protocol):
    """Porta usada por outros modulos para consumir uma chance."""

    async def execute(self, principal_id: str) -> PromptQuota:
        """Consome uma chance do principal ou levanta QuotaExceededError."""
        ...


class PromptQuotaRefundPort(Protocol):
    """Porta usada pelo worker para devolver a chance em falhas/recusas."""

    async def refund(self, principal_id: str) -> bool:
        """Devolve uma chance consumida; idempotencia fica a cargo do chamador."""
        ...
