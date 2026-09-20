"""Orquestrador de agentes de IA — UNICA camada que conhece LangGraph.

Pipeline (maquina de estados, spec secao 12):
    interpret_prompt -> safety_check -> scope_check -> generate_or_edit -> post_process

- Imports LAZY de langgraph/langchain/crewai: o nucleo da app e os
  testes nao dependem dessas libs pesadas; sem elas instaladas o
  pipeline cai no executor sequencial equivalente.
- SafetyReviewerAgent: revalida o prompt no pipeline (defesa em
  profundidade — a guarda do domain ja barrou no request).
- ScopeGuardrail (Camada 2): recusa deterministisca de conteudo sem
  instrucao clara de imagem (OUT_OF_SCOPE), via system prompt hardenizado
  compartilhado (guardrails.SCOPE_GUARDRAIL_PROMPT).
- O input do usuario NUNCA e concatenado direto em prompt de sistema:
  usa delimitadores estruturados (anti prompt injection).
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from modules.image_generation.adapters.ai_agents.guardrails import (
    ScopeGuardrail,
    build_scope_system_prompt,
)
from modules.image_generation.adapters.ai_agents.providers import ImageProvider
from modules.image_generation.application.ports.image_agent_port import (
    ImageAgentPort,
    ProgressCallback,
)
from modules.image_generation.domain.entities import Generation
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from shared_kernel.errors import DomainError

logger = logging.getLogger(__name__)

_SYSTEM_DELIMITER = "<<<USER_PROMPT_BEGIN>>>"


class _PipelineState(TypedDict, total=False):
    generation: Generation
    interpreted_prompt: str
    scope_system_prompt: str
    progress: int
    result_url: str
    error: str


class LangGraphImageAgent(ImageAgentPort):
    _SYSTEM_ROLE = "interpretar prompts e gerar/editar imagens dentro do AImaginator"

    def __init__(
        self,
        *,
        provider: ImageProvider,
        prompt_guard: PromptInjectionGuard,
        scope_guardrail: ScopeGuardrail | None = None,
    ) -> None:
        self._provider = provider
        self._guard = prompt_guard
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()
        self._scope_system_prompt = build_scope_system_prompt(self._SYSTEM_ROLE)
        self._graph = self._try_build_langgraph()

    # ---- nos do grafo (cada um com responsabilidade unica — SOLID) ----

    async def _interpret_prompt(self, state: _PipelineState) -> _PipelineState:
        """PromptInterpreterAgent: normaliza intencao + preset de estilo."""
        generation = state["generation"]
        style_hint = (
            f" | style_preset={generation.style_preset.value}"
            if generation.style_preset.value != "none"
            else ""
        )
        # Delimitadores estruturados: o prompt do usuario e DADO, nunca instrucao.
        state["interpreted_prompt"] = (
            f"{_SYSTEM_DELIMITER}{generation.prompt}{_SYSTEM_DELIMITER.replace('BEGIN', 'END')}"
            f"{style_hint}"
        )
        state["scope_system_prompt"] = self._scope_system_prompt
        state["progress"] = 20
        return state

    async def _safety_check(self, state: _PipelineState) -> _PipelineState:
        """SafetyReviewerAgent: revalidacao independente antes de gerar."""
        self._guard.validate(state["generation"].prompt)
        state["progress"] = 30
        return state

    async def _scope_check(self, state: _PipelineState) -> _PipelineState:
        """ScopeGuardrail (Camada 2): recusa conteudo sem instrucao de imagem.

        Redundante de proposito: mesmo que o PromptTopicGuard (Camada 1) tenha
        falhado ou sido contornado, o agente recusa de forma deterministica
        retornando OUT_OF_SCOPE (via OutOfScopeError) em vez de gerar texto
        livre ou adivinhar uma intencao alternativa.
        """
        self._scope_guardrail.check(state["generation"].prompt)
        state["progress"] = 40
        return state

    async def _generate_or_edit(self, state: _PipelineState) -> _PipelineState:
        """ImageGeneratorAgent/ImageEditorAgent: chama o provedor."""
        generation = state["generation"]
        kind = "edicao" if generation.kind.value == "edit" else "geracao"
        logger.info("Iniciando %s de imagem (id=%s)", kind, generation.id)

        async def noop_progress(_: int) -> None:
            state["progress"] = 60

        state["result_url"] = await self._provider.generate(generation, noop_progress)
        state["progress"] = 85
        return state

    async def _post_process(self, state: _PipelineState) -> _PipelineState:
        """Valida o output do agente antes de devolver (schema check)."""
        url = state.get("result_url", "")
        if not url.startswith(("https://", "http://")):
            raise DomainError("Output do agente nao e uma URL de imagem valida.")
        state["progress"] = 100
        return state

    # ---- wiring LangGraph (lazy) ----

    def _try_build_langgraph(self) -> Any | None:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None

        graph = StateGraph(_PipelineState)
        graph.add_node("interpret_prompt", self._interpret_prompt)
        graph.add_node("safety_check", self._safety_check)
        graph.add_node("scope_check", self._scope_check)
        graph.add_node("generate_or_edit", self._generate_or_edit)
        graph.add_node("post_process", self._post_process)
        graph.add_edge(START, "interpret_prompt")
        graph.add_edge("interpret_prompt", "safety_check")
        graph.add_edge("safety_check", "scope_check")
        graph.add_edge("scope_check", "generate_or_edit")
        graph.add_edge("generate_or_edit", "post_process")
        graph.add_edge("post_process", END)
        return graph.compile()

    # ---- porta ----

    async def run_generation(
        self, generation: Generation, on_progress: ProgressCallback
    ) -> str:
        initial: _PipelineState = {"generation": generation, "progress": 0}
        if self._graph is not None:
            final = await self._graph.ainvoke(initial)
        else:
            final = await self._run_sequential(initial)
        await on_progress(95)
        return str(final["result_url"])

    async def _run_sequential(self, state: _PipelineState) -> _PipelineState:
        """Fallback sem langgraph: mesma ordem, mesmos nos."""
        for node in (
            self._interpret_prompt,
            self._safety_check,
            self._scope_check,
            self._generate_or_edit,
            self._post_process,
        ):
            state = await node(state)
        return state
