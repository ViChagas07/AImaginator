"""Testes do cliente LLM OpenAI-compatible (sem LM Studio real)."""

from __future__ import annotations

import httpx
import pytest

from modules.image_generation.adapters.ai_agents.llm_client import (
    OpenAICompatibleLlmClient,
)
from modules.image_generation.application.ports.llm_client import LlmUnavailableError


class _Response:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Http:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _client(http: _Http) -> OpenAICompatibleLlmClient:
    return OpenAICompatibleLlmClient(
        http_client=http,
        base_url="http://localhost:1235/v1/",
        model="qwen/qwen3.5-9b",
        api_key="lm-studio",
        timeout_seconds=90,
        max_output_tokens=400,
        ttl_seconds=60,
    )


@pytest.mark.unit
async def test_payload_inclui_ttl_json_schema_e_temperatura_zero() -> None:
    http = _Http(
        [_Response(200, {"choices": [{"message": {"content": "{}"}}]})]
    )
    client = _client(http)
    content = await client.complete(
        system_prompt="sys", user_prompt="user", json_schema={"type": "object"}
    )

    assert content == "{}"
    payload = http.calls[0]["json"]
    assert payload["temperature"] == 0
    assert payload["ttl"] == 60
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert http.calls[0]["headers"]["Authorization"] == "Bearer lm-studio"
    assert http.calls[0]["url"] == "http://localhost:1235/v1/chat/completions"


@pytest.mark.unit
async def test_http_400_remove_campos_opcionais_e_tenta_de_novo() -> None:
    http = _Http(
        [
            _Response(400),
            _Response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = _client(http)
    assert await client.complete(system_prompt="s", user_prompt="u") == "ok"
    assert "ttl" in http.calls[0]["json"]
    assert "ttl" in http.calls[1]["json"]  # preserva o descarregamento do modelo
    assert "response_format" not in http.calls[1]["json"]


@pytest.mark.unit
async def test_http_400_persistente_remove_todos_os_opcionais() -> None:
    http = _Http(
        [
            _Response(400),
            _Response(400),
            _Response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = _client(http)
    assert await client.complete(system_prompt="s", user_prompt="u") == "ok"
    assert "ttl" not in http.calls[2]["json"]
    assert "chat_template_kwargs" not in http.calls[2]["json"]


@pytest.mark.unit
async def test_timeout_vira_llm_unavailable() -> None:
    client = _client(_Http([httpx.ReadTimeout("timeout")]))
    with pytest.raises(LlmUnavailableError):
        await client.complete(system_prompt="s", user_prompt="u")


@pytest.mark.unit
async def test_resposta_sem_conteudo_vira_unavailable() -> None:
    client = _client(_Http([_Response(200, {"choices": []})]))
    with pytest.raises(LlmUnavailableError):
        await client.complete(system_prompt="s", user_prompt="u")


@pytest.mark.unit
async def test_erro_nao_400_vira_unavailable() -> None:
    client = _client(_Http([_Response(500)]))
    with pytest.raises(LlmUnavailableError):
        await client.complete(system_prompt="s", user_prompt="u")
