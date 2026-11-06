"""Cliente LLM OpenAI-compatible (LM Studio), com fallback de campos opcionais."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from modules.image_generation.application.ports.llm_client import (
    LlmClientPort,
    LlmTimeoutError,
    LlmUnavailableError,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleLlmClient(LlmClientPort):
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 90.0,
        max_output_tokens: int = 400,
        ttl_seconds: int = 60,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._ttl = ttl_seconds

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None = None,
    ) -> str:
        payload = self._payload(system_prompt, user_prompt, json_schema)
        try:
            response = await self._post(payload)
            if response.status_code in {400, 422}:
                # Servidores locais variam: tenta manter o ttl (descarrega o
                # modelo) removendo apenas o response_format.
                fallback = self._payload(
                    system_prompt,
                    user_prompt,
                    json_schema,
                    optional=True,
                    include_response_format=False,
                )
                response = await self._post(fallback)
            if response.status_code in {400, 422}:
                # Ainda rejeitado: remove todos os campos opcionais.
                fallback = self._payload(
                    system_prompt, user_prompt, json_schema, optional=False
                )
                response = await self._post(fallback)
            if response.status_code != 200:
                raise LlmUnavailableError(
                    f"LLM respondeu HTTP {response.status_code}"
                )
            try:
                content = response.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LlmUnavailableError("Resposta do LLM sem conteudo.") from exc
            if not isinstance(content, str) or not content.strip():
                raise LlmUnavailableError("Resposta do LLM vazia.")
            return content
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError("Timeout do LLM.") from exc
        except httpx.HTTPError as exc:
            raise LlmUnavailableError("Falha de transporte do LLM.") from exc

    async def _post(self, payload: dict[str, Any]) -> Any:
        return await self._http.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(self._timeout, connect=10.0),
        )

    def _payload(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict | None,
        *,
        optional: bool = True,
        include_response_format: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if optional:
            payload["ttl"] = self._ttl
            payload["chat_template_kwargs"] = {"enable_thinking": False}
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
