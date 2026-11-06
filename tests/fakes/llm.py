"""Cliente LLM falso para testes: nunca chama LM Studio/Qwen real."""

from __future__ import annotations

import json

from modules.image_generation.application.ports.llm_client import LlmUnavailableError


class FakeLlmClient:
    def __init__(self, responses: list[str | Exception] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    async def complete(self, *, system_prompt, user_prompt, json_schema=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "json_schema": json_schema,
            }
        )
        if not self.responses:
            raise AssertionError("FakeLlmClient sem resposta configurada")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def assistant_json(**overrides) -> str:
    payload = {
        "detected_language": "pt",
        "is_image_request": True,
        "in_scope": True,
        "moderation": {
            "sexual": False,
            "gore": False,
            "hate": False,
            "self_harm": False,
        },
        "blocked_category": None,
        "confidence": 0.95,
        "image_part_extracted": None,
        "corrected_text": "um castelo nas nuvens",
        "flux_prompt": "a castle in the clouds, cinematic lighting",
        "kontext_instruction": None,
        "suggested_aspect_ratio": "1:1",
        "flags": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


__all__ = ["FakeLlmClient", "assistant_json", "LlmUnavailableError"]
