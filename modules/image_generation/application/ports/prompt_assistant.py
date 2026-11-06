"""Porta do assistente de prompts (classificacao, moderacao e reescrita)."""

from __future__ import annotations

from typing import Protocol

from modules.image_generation.domain.prompt_assistant import (
    AssistantInput,
    AssistantResult,
)


class PromptAssistantPort(Protocol):
    async def analyze(self, data: AssistantInput) -> AssistantResult:
        """Analisa o texto e devolve classificacao + reescrita para o motor."""
        ...
