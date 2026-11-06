"""Porta do cliente LLM (OpenAI-compatible, incluindo LM Studio)."""

from __future__ import annotations

from typing import Protocol


class LlmUnavailableError(Exception):
    """Falha de transporte do LLM (nunca vaza detalhes ao usuario)."""


class LlmTimeoutError(LlmUnavailableError):
    """Timeout da chamada ao LLM."""


class LlmClientPort(Protocol):
    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None = None,
    ) -> str:
        """Devolve o conteudo textual da resposta do modelo."""
        ...
