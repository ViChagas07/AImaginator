"""Porta do orquestrador de agentes de IA.

Todo agente vive atras desta porta (spec secao 12): apenas
adapters/ai_agents/ conhece CrewAI/LangChain/LangGraph. O resto do
sistema so conhece ImageAgentPort — trocar o framework de orquestracao
nao toca em regra de negocio.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from modules.image_generation.domain.entities import Generation

ProgressCallback = Callable[[int], Awaitable[None]]


class ImageAgentPort(Protocol):
    async def run_generation(
        self, generation: Generation, on_progress: ProgressCallback
    ) -> str:
        """Executa o pipeline interpretar -> checar -> gerar -> pos-processar.

        Devolve a URL da imagem resultante. Levanta DomainError em falha.
        """
        ...
