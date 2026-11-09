"""Testes do cliente LLM OpenAI-compatible (sem LM Studio real)."""

from __future__ import annotations

import httpx
import pytest
import structlog

from modules.image_generation.adapters.ai_agents.llm_client import (
    OpenAICompatibleLlmClient,
)
from modules.image_generation.application.ports.llm_client import (
    LlmOutputTruncatedError,
    LlmTimeoutError,
    LlmUnavailableError,
)


class _Response:
    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

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


def _content(
    content: str = "{}",
    *,
    finish_reason: str = "stop",
    reasoning: str | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> dict:
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def _client(
    http: _Http,
    *,
    reasoning_effort: str = "none",
    debug_log_content: bool = False,
) -> OpenAICompatibleLlmClient:
    return OpenAICompatibleLlmClient(
        http_client=http,
        base_url="http://localhost:1235/v1/",
        model="qwen/qwen3.5-9b",
        api_key="lm-studio",
        timeout_seconds=120,
        max_output_tokens=512,
        ttl_seconds=60,
        reasoning_effort=reasoning_effort,
        max_output_tokens_retry=1024,
        debug_log_content=debug_log_content,
    )


@pytest.mark.unit
async def test_payload_inclui_reasoning_effort_ttl_json_schema_e_temperatura_zero() -> None:
    http = _Http([_Response(200, _content())])
    client = _client(http)
    content = await client.complete(
        system_prompt="sys", user_prompt="user", json_schema={"type": "object"}
    )

    assert content == "{}"
    payload = http.calls[0]["json"]
    assert payload["temperature"] == 0
    assert payload["ttl"] == 60
    assert payload["reasoning_effort"] == "none"
    assert "chat_template_kwargs" not in payload
    assert payload["response_format"]["type"] == "json_schema"
    assert http.calls[0]["headers"]["Authorization"] == "Bearer lm-studio"
    assert http.calls[0]["url"] == "http://localhost:1235/v1/chat/completions"


@pytest.mark.unit
async def test_reasoning_effort_vazio_nao_e_enviado() -> None:
    http = _Http([_Response(200, _content())])
    client = _client(http, reasoning_effort="")
    await client.complete(system_prompt="s", user_prompt="u")

    assert "reasoning_effort" not in http.calls[0]["json"]


@pytest.mark.unit
async def test_http_400_remove_response_format_e_tenta_de_novo() -> None:
    http = _Http(
        [
            _Response(400),
            _Response(200, _content("ok")),
        ]
    )
    client = _client(http)
    assert await client.complete(system_prompt="s", user_prompt="u") == "ok"
    assert "ttl" in http.calls[0]["json"]
    assert "ttl" in http.calls[1]["json"]
    assert "reasoning_effort" in http.calls[1]["json"]
    assert "response_format" not in http.calls[1]["json"]


@pytest.mark.unit
async def test_http_400_persistente_remove_reasoning_e_depois_todos_os_opcionais() -> None:
    http = _Http(
        [
            _Response(400),
            _Response(400),
            _Response(400),
            _Response(200, _content("ok")),
        ]
    )
    client = _client(http)
    assert (
        await client.complete(system_prompt="s", user_prompt="u", json_schema={"type": "object"})
        == "ok"
    )

    assert "response_format" in http.calls[0]["json"]
    assert "response_format" not in http.calls[1]["json"]
    assert "reasoning_effort" in http.calls[1]["json"]
    assert "reasoning_effort" not in http.calls[2]["json"]
    assert "ttl" in http.calls[2]["json"]
    assert "ttl" not in http.calls[3]["json"]
    assert "chat_template_kwargs" not in http.calls[0]["json"]


@pytest.mark.unit
async def test_timeout_vira_llm_timeout() -> None:
    client = _client(_Http([httpx.ReadTimeout("timeout")]))
    with pytest.raises(LlmTimeoutError):
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


@pytest.mark.unit
async def test_truncado_faz_uma_retentativa_com_none_e_max_tokens_maior() -> None:
    http = _Http(
        [
            _Response(
                200,
                _content("", finish_reason="length", reasoning="pensando" * 100),
            ),
            _Response(200, _content('{"ok": true}')),
        ]
    )
    client = _client(http)
    assert await client.complete(system_prompt="s", user_prompt="u") == '{"ok": true}'

    assert len(http.calls) == 2
    assert http.calls[0]["json"]["max_tokens"] == 512
    assert http.calls[1]["json"]["max_tokens"] == 1024
    assert http.calls[1]["json"]["reasoning_effort"] == "none"
    assert client.last_response_info.finish_reason == "stop"
    assert client.last_response_info.truncated is False


@pytest.mark.unit
async def test_truncado_persistente_fail_closed_sem_usar_reasoning() -> None:
    http = _Http(
        [
            _Response(200, _content("", finish_reason="length", reasoning="r" * 50)),
            _Response(200, _content("", finish_reason="length", reasoning="r" * 50)),
        ]
    )
    client = _client(http, reasoning_effort="")
    with pytest.raises(LlmOutputTruncatedError) as exc:
        await client.complete(system_prompt="s", user_prompt="u")

    assert exc.value.code == "llm_output_truncated"
    assert len(http.calls) == 2
    assert http.calls[1]["json"]["reasoning_effort"] == "none"
    assert client.last_response_info.truncated is True


@pytest.mark.unit
async def test_finish_length_com_content_nao_e_tratado_como_truncado() -> None:
    client = _client(_Http([_Response(200, _content("corte", finish_reason="length"))]))
    assert await client.complete(system_prompt="s", user_prompt="u") == "corte"


@pytest.mark.unit
async def test_conteudo_nao_aparece_nos_logs_por_padrao() -> None:
    secret = "PROMPT_SECRETO_NAO_PODE_IR_PARA_LOG"
    client = _client(_Http([_Response(200, _content(f'{{"flux_prompt": "{secret}"}}'))]))
    with structlog.testing.capture_logs() as logs:
        await client.complete(system_prompt="s", user_prompt="u")

    assert secret not in repr(logs)
    assert all("content_preview" not in entry for entry in logs)


@pytest.mark.unit
async def test_conteudo_aparece_apenas_com_debug_em_dev() -> None:
    secret = "PROMPT_SECRETO_DEBUG"
    client = _client(
        _Http([_Response(200, _content(f'{{"flux_prompt": "{secret}"}}'))]),
        debug_log_content=True,
    )
    with structlog.testing.capture_logs() as logs:
        await client.complete(system_prompt="s", user_prompt="u")

    logged = [entry for entry in logs if entry.get("event") == "llm_response"]
    assert logged and secret in logged[-1]["content_preview"]


@pytest.mark.unit
async def test_logging_ascii_safe_nao_quebra_com_unicode() -> None:
    client = _client(
        _Http([_Response(200, _content('{"x": "\uff5c"}'))]),
        debug_log_content=True,
    )
    with structlog.testing.capture_logs() as logs:
        await client.complete(system_prompt="s", user_prompt="u")

    assert any(entry.get("event") == "llm_response" for entry in logs)
