"""Cliente LLM OpenAI-compatible (LM Studio), com fallback de campos opcionais.

Regras de seguranca:
- nunca loga prompt/conteudo por padrao (opt-in em development);
- nunca usa reasoning_content como resposta;
- saida truncada sem content tenta UMA vez com reasoning desligado.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

import httpx

from modules.image_generation.application.ports.llm_client import (
    LlmClientPort,
    LlmOutputTruncatedError,
    LlmResponseInfo,
    LlmTimeoutError,
    LlmUnavailableError,
)
from modules.observability.logging_config import get_logger
from modules.observability.sentry_setup import scrub_text

logger = get_logger(__name__)

_PREVIEW_CHARS = 500


def _safe_log_text(value: str) -> str:
    """ASCII-safe: o console do Windows pode nao codificar acentos/CJK."""
    return value.encode("ascii", "backslashreplace").decode("ascii")


class OpenAICompatibleLlmClient(LlmClientPort):
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 512,
        ttl_seconds: int = 60,
        reasoning_effort: str = "none",
        max_output_tokens_retry: int = 1024,
        debug_log_content: bool = False,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._ttl = ttl_seconds
        self._reasoning_effort = reasoning_effort.strip()
        self._max_output_tokens_retry = max_output_tokens_retry
        self._debug_log_content = debug_log_content
        self._last_response_info = LlmResponseInfo()

    @property
    def last_response_info(self) -> LlmResponseInfo:
        """Metadados da ultima resposta (inclusive em falha), sem conteudo."""
        return self._last_response_info

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None = None,
    ) -> str:
        started = time.perf_counter()
        response = await self._request(
            system_prompt,
            user_prompt,
            json_schema,
            max_tokens=self._max_output_tokens,
            reasoning_effort=self._reasoning_effort,
            phase="initial",
        )
        content, truncated = self._content_from(response, started)
        if truncated:
            logger.warning(
                "llm_request_failed",
                branch="truncated",
                phase="initial",
                finish_reason=self._last_response_info.finish_reason,
                completion_tokens=self._last_response_info.completion_tokens,
                content_chars=0,
                reasoning_chars=self._last_response_info.reasoning_chars,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            response = await self._request(
                system_prompt,
                user_prompt,
                json_schema,
                max_tokens=self._max_output_tokens_retry,
                reasoning_effort="none",
                phase="retry",
            )
            content, truncated = self._content_from(response, started)
            if truncated:
                logger.error(
                    "llm_request_failed",
                    branch="truncated_retry",
                    phase="retry",
                    finish_reason=self._last_response_info.finish_reason,
                    completion_tokens=self._last_response_info.completion_tokens,
                    content_chars=0,
                    reasoning_chars=self._last_response_info.reasoning_chars,
                    elapsed_seconds=round(time.perf_counter() - started, 3),
                )
                raise LlmOutputTruncatedError("Saida do LLM truncada sem conteudo.")
        return content

    async def _request(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None,
        *,
        max_tokens: int,
        reasoning_effort: str,
        phase: str,
    ) -> Any:
        payload = self._payload(
            system_prompt,
            user_prompt,
            json_schema,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
        attempt = 0
        attempt += 1
        response = await self._post(payload, attempt=attempt, phase=phase)
        if response.status_code in {400, 422}:
            # Servidores locais variam: remove response_format, mantendo ttl.
            fallback = self._payload(
                system_prompt,
                user_prompt,
                json_schema,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                include_response_format=False,
            )
            attempt += 1
            response = await self._post(fallback, attempt=attempt, phase=phase)
        if response.status_code in {400, 422} and reasoning_effort:
            # Campo reasoning_effort desconhecido: remove e tenta de novo.
            fallback = self._payload(
                system_prompt,
                user_prompt,
                json_schema,
                max_tokens=max_tokens,
                reasoning_effort="",
                include_response_format=False,
            )
            attempt += 1
            response = await self._post(fallback, attempt=attempt, phase=phase)
        if response.status_code in {400, 422}:
            # Ainda rejeitado: remove todos os campos opcionais.
            fallback = self._payload(
                system_prompt,
                user_prompt,
                json_schema,
                max_tokens=max_tokens,
                reasoning_effort="",
                optional=False,
            )
            attempt += 1
            response = await self._post(fallback, attempt=attempt, phase=phase)
        if response.status_code != 200:
            logger.warning(
                "llm_request_failed",
                branch="http_status",
                phase=phase,
                status_code=response.status_code,
                model=self._model,
                attempt=attempt,
                elapsed_seconds=round(self._last_response_info.elapsed_seconds, 3),
            )
            raise LlmUnavailableError(f"LLM respondeu HTTP {response.status_code}")
        return response

    async def _post(self, payload: dict[str, Any], *, attempt: int, phase: str) -> Any:
        started = time.perf_counter()
        try:
            response = await self._http.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        except httpx.TimeoutException as exc:
            fields: dict[str, Any] = {
                "branch": "timeout",
                "phase": phase,
                "error_type": type(exc).__name__,
                "error_message": _safe_log_text(str(exc))[:_PREVIEW_CHARS],
                "model": self._model,
                "attempt": attempt,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            if self._debug_log_content:
                fields["traceback"] = _safe_log_text(scrub_text(traceback.format_exc()))[
                    : _PREVIEW_CHARS * 4
                ]
            logger.warning("llm_request_failed", **fields)
            raise LlmTimeoutError("Timeout do LLM.") from exc
        except httpx.HTTPError as exc:
            fields = {
                "branch": "transport",
                "phase": phase,
                "error_type": type(exc).__name__,
                "error_message": _safe_log_text(str(exc))[:_PREVIEW_CHARS],
                "model": self._model,
                "attempt": attempt,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            if self._debug_log_content:
                fields["traceback"] = _safe_log_text(scrub_text(traceback.format_exc()))[
                    : _PREVIEW_CHARS * 4
                ]
            logger.warning("llm_request_failed", **fields)
            raise LlmUnavailableError("Falha de transporte do LLM.") from exc
        self._record_response(response, phase=phase, attempt=attempt, started=started)
        return response

    def _content_from(self, response: Any, started: float) -> tuple[str, bool]:
        """Extrai content; sinaliza truncamento quando finish_reason=length."""
        info = self._last_response_info
        try:
            data = response.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "llm_request_failed",
                branch="missing_content",
                status_code=getattr(response, "status_code", None),
                error_type=type(exc).__name__,
                error_message=_safe_log_text(str(exc))[:_PREVIEW_CHARS],
                model=self._model,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            raise LlmUnavailableError("Resposta do LLM sem conteudo.") from exc

        if info.finish_reason == "length" and not (isinstance(content, str) and content.strip()):
            return "", True
        if not isinstance(content, str) or not content.strip():
            logger.warning(
                "llm_request_failed",
                branch="empty_content",
                status_code=getattr(response, "status_code", None),
                content_chars=len(content) if isinstance(content, str) else None,
                model=self._model,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            raise LlmUnavailableError("Resposta do LLM vazia.")
        return content, False

    def _record_response(self, response: Any, *, phase: str, attempt: int, started: float) -> None:
        """Registra metadados. Conteudo so com opt-in explicito em dev."""
        finish_reason = None
        prompt_tokens = None
        completion_tokens = None
        content_chars = None
        reasoning_chars = None
        content_preview = None
        truncated = False
        try:
            data = response.json()
            choice = (data.get("choices") or [{}])[0]
            finish_reason = choice.get("finish_reason")
            message = choice.get("message") or {}
            content = message.get("content")
            reasoning = message.get("reasoning_content")
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            if isinstance(content, str):
                content_chars = len(content)
                if self._debug_log_content:
                    content_preview = _safe_log_text(scrub_text(content[:_PREVIEW_CHARS]))
            if isinstance(reasoning, str):
                reasoning_chars = len(reasoning)
            truncated = finish_reason == "length" and not (
                isinstance(content, str) and content.strip()
            )
        except Exception:  # noqa: S110 - log nunca deve quebrar a chamada
            pass

        elapsed = time.perf_counter() - started
        self._last_response_info = LlmResponseInfo(
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            content_chars=content_chars,
            reasoning_chars=reasoning_chars,
            status_code=getattr(response, "status_code", None),
            elapsed_seconds=elapsed,
            truncated=truncated,
        )
        fields: dict[str, Any] = {
            "model": self._model,
            "phase": phase,
            "attempt": attempt,
            "status_code": getattr(response, "status_code", None),
            "elapsed_seconds": round(elapsed, 3),
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "content_chars": content_chars,
            "reasoning_chars": reasoning_chars,
            "truncated": truncated,
        }
        if content_preview is not None:
            fields["content_preview"] = content_preview
        logger.info("llm_response", **fields)

    def _payload(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None,
        *,
        optional: bool = True,
        include_response_format: bool = True,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": max_tokens or self._max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if optional:
            payload["ttl"] = self._ttl
            effort = self._reasoning_effort if reasoning_effort is None else reasoning_effort
            if effort:
                payload["reasoning_effort"] = effort
            if json_schema is not None and include_response_format:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "prompt_assistant",
                        "strict": True,
                        "schema": json_schema,
                    },
                }
        return payload
