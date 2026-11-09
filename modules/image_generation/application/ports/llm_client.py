"""Porta do cliente LLM (OpenAI-compatible, incluindo LM Studio)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LlmUnavailableError(Exception):
    """Falha de transporte do LLM (nunca vaza detalhes ao usuario)."""


class LlmTimeoutError(LlmUnavailableError):
    """Timeout da chamada ao LLM."""


class LlmOutputTruncatedError(LlmUnavailableError):
    """Saida truncada sem content (ex.: reasoning consumiu max_tokens)."""

    code = "llm_output_truncated"


@dataclass(frozen=True, slots=True)
class LlmResponseInfo:
    """Metadados da ultima resposta, para diagnostico/log (sem prompt)."""

    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    content_chars: int | None = None
    reasoning_chars: int | None = None
    status_code: int | None = None
    elapsed_seconds: float = 0.0
    truncated: bool = False


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
