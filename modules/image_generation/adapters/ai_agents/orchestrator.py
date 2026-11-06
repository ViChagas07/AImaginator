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

import asyncio
import logging
from collections.abc import Sequence
from typing import Any, TypedDict

from modules.image_generation.adapters.ai_agents.guardrails import (
    build_scope_system_prompt,
)
from modules.image_generation.adapters.ai_agents.providers import ImageProvider
from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports.image_agent_port import (
    ImageAgentPort,
    ProgressCallback,
)
from modules.image_generation.application.ports.image_engine import (
    EngineImage,
    ImageEditorPort,
    ImageGeneratorPort,
    ImagePostProcessor,
)
from modules.image_generation.application.ports.image_moderation import (
    ImageModeratorPort,
)
from modules.image_generation.application.ports.image_processing import (
    AiMetadataWriterPort,
    C2PASignerPort,
    ImageWatermarkerPort,
)
from modules.image_generation.application.ports.object_storage import ObjectStoragePort
from modules.image_generation.application.ports.prompt_assistant import (
    PromptAssistantPort,
)
from modules.image_generation.domain.entities import (
    ASPECT_RATIO_DIMENSIONS,
    Generation,
    GenerationKind,
)
from modules.image_generation.domain.image_bytes import validate_image_bytes
from modules.image_generation.domain.prompt_assistant import AssistantInput
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.scope_guard import ScopeGuardrail
from modules.observability.metrics import UPLOAD_FAILURES_TOTAL
from modules.observability.timing import stage_timer
from shared_kernel.errors import DomainError
from shared_kernel.security_errors import (
    ContentBlockedError,
    ImageBlockedError,
    ImageModerationUnavailableError,
    OutOfScopeError,
    PromptInjectionDetectedError,
)

logger = logging.getLogger(__name__)

_SYSTEM_DELIMITER = "<<<USER_PROMPT_BEGIN>>>"


class _PipelineState(TypedDict, total=False):
    generation: Generation
    interpreted_prompt: str
    scope_system_prompt: str
    progress: int
    result_url: str
    result_object_key: str
    image_bytes: bytes
    image_metadata: EngineImage
    source_image_bytes: bytes
    original_object_key: str
    public_object_key: str
    on_progress_callback: ProgressCallback
    engine_prompt: str
    error: str


class LangGraphImageAgent(ImageAgentPort):
    _SYSTEM_ROLE = "interpretar prompts e gerar/editar imagens dentro do AImaginator"

    def __init__(
        self,
        *,
        prompt_guard: PromptInjectionGuard,
        provider: ImageProvider | None = None,
        generator: ImageGeneratorPort | None = None,
        editor: ImageEditorPort | None = None,
        storage: ObjectStoragePort | None = None,
        post_processors: Sequence[ImagePostProcessor] | None = None,
        scope_guardrail: ScopeGuardrail | None = None,
        prompt_assistant: PromptAssistantPort | None = None,
        block_confidence: float = 0.5,
        image_moderator: ImageModeratorPort | None = None,
        image_moderation_enabled: bool = True,
        watermarker: ImageWatermarkerPort | None = None,
        metadata_writer: AiMetadataWriterPort | None = None,
        c2pa_signer: C2PASignerPort | None = None,
    ) -> None:
        if provider is None and (generator is None or editor is None):
            msg = "Informe provider legado ou generator + editor."
            raise ValueError(msg)
        self._provider = provider
        self._generator = generator
        self._editor = editor
        self._storage = storage
        self._post_processors = list(post_processors or ())
        self._guard = prompt_guard
        self._prompt_assistant = prompt_assistant
        self._block_confidence = block_confidence
        self._image_moderator = image_moderator
        self._image_moderation_enabled = image_moderation_enabled
        self._watermarker = watermarker
        self._metadata_writer = metadata_writer
        self._c2pa_signer = c2pa_signer
        self._scope_guardrail = scope_guardrail or ScopeGuardrail()
        self._scope_system_prompt = build_scope_system_prompt(self._SYSTEM_ROLE)
        self._graph = self._try_build_langgraph()

    # ---- nos do grafo (cada um com responsabilidade unica — SOLID) ----

    async def _assistant(self, state: _PipelineState) -> _PipelineState:
        """Camada semantica final: classificacao, moderacao e reescrita.

        Roda NO WORKER, antes de qualquer chamada ao motor de imagem. No modo
        legado (provider) o assistente nao e usado.
        """
        generation = state["generation"]
        if self._prompt_assistant is None or self._provider is not None:
            state["engine_prompt"] = generation.prompt
            return state

        async def noop(_: int) -> None:
            return

        progress_callback = state.get("on_progress_callback") or noop
        await progress_callback(7)
        with stage_timer("assistant_llm", correlation_id=str(generation.id)):
            result = await self._prompt_assistant.analyze(
                AssistantInput(
                    text=generation.prompt,
                    kind=generation.kind,
                    locale=generation.locale,
                )
            )
        refusal = result.refusal_code(block_confidence=self._block_confidence)
        if refusal is not None:
            if refusal == "out_of_scope":
                raise OutOfScopeError(message_for("out_of_scope", generation.locale))
            category = result.moderation_category(
                block_confidence=self._block_confidence
            )
            raise ContentBlockedError(
                code=refusal,
                message=message_for(refusal, generation.locale),
                category=category.value if category is not None else None,
                layer="llm",
                confidence=result.confidence,
            )
        state["engine_prompt"] = result.engine_prompt(generation.kind)
        await progress_callback(10)
        return state

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
        generation = state["generation"]
        try:
            with stage_timer("input_guard", correlation_id=str(generation.id)):
                self._guard.validate(generation.prompt)
        except PromptInjectionDetectedError as exc:
            raise PromptInjectionDetectedError(
                message_for("prompt_rejected", generation.locale)
            ) from exc
        state["progress"] = 30
        return state

    async def _scope_check(self, state: _PipelineState) -> _PipelineState:
        """ScopeGuardrail (Camada 2): recusa conteudo sem instrucao de imagem.

        Redundante de proposito: mesmo que o PromptTopicGuard (Camada 1) tenha
        falhado ou sido contornado, o agente recusa de forma deterministica
        retornando OUT_OF_SCOPE (via OutOfScopeError) em vez de gerar texto
        livre ou adivinhar uma intencao alternativa.
        """
        generation = state["generation"]
        try:
            self._scope_guardrail.check(generation.prompt)
        except OutOfScopeError as exc:
            raise OutOfScopeError(
                message_for("out_of_scope", generation.locale)
            ) from exc
        state["progress"] = 40
        return state

    async def _moderate_source(self, state: _PipelineState) -> _PipelineState:
        """Modera a origem enviada pelo usuario antes de qualquer motor.

        Refinos usam o original gerado (ja moderado) e nao passam por aqui.
        """
        generation = state["generation"]
        source_key = generation.source_object_key
        if (
            generation.kind is not GenerationKind.EDIT
            or not source_key
            or not source_key.startswith("sources/")
            or not self._image_moderation_enabled
            or self._image_moderator is None
            or self._storage is None
        ):
            return state
        source = await self._storage.get_object(source_key)
        try:
            with stage_timer(
                "input_image_moderation", correlation_id=str(generation.id)
            ):
                moderation = await self._image_moderator.moderate(source)
        except ImageModerationUnavailableError as exc:
            raise ImageModerationUnavailableError(
                message_for("image_moderation_unavailable", generation.locale)
            ) from exc
        if moderation.blocked and moderation.blocked_category is not None:
            await self._storage.delete_object(source_key)
            category = moderation.blocked_category.value
            code = f"source_image_blocked_{category}"
            raise ImageBlockedError(
                code=code,
                message=message_for(code, generation.locale),
                category=category,
                layer="image_input",
                confidence=max(
                    moderation.scores.sexual,
                    moderation.scores.gore,
                    moderation.scores.hate,
                    moderation.scores.self_harm,
                ),
            )
        state["source_image_bytes"] = source
        return state

    async def _generate_or_edit(self, state: _PipelineState) -> _PipelineState:
        """ImageGeneratorAgent/ImageEditorAgent: chama a porta correta por kind."""
        generation = state["generation"]
        kind = "edicao" if generation.kind.value == "edit" else "geracao"
        logger.info("Iniciando %s de imagem (id=%s)", kind, generation.id)

        if self._provider is not None:
            async def noop_progress(_: int) -> None:
                state["progress"] = 60

            state["result_url"] = await self._provider.generate(generation, noop_progress)
            state["progress"] = 85
            return state

        width, height = ASPECT_RATIO_DIMENSIONS[generation.aspect_ratio]
        engine_prompt = state.get("engine_prompt") or generation.prompt

        async def noop(_: int) -> None:
            return

        progress_callback = state.get("on_progress_callback") or noop

        async def on_progress(percent: int) -> None:
            state["progress"] = min(max(percent, 5), 95)
            await progress_callback(percent)

        if generation.kind is GenerationKind.EDIT:
            if self._editor is None:
                raise DomainError("Editor de imagem nao configurado.")
            if not generation.source_object_key or self._storage is None:
                raise DomainError("Imagem de origem indisponivel para edicao.")
            source_image = state.get("source_image_bytes")
            if source_image is None:
                source_image = await self._storage.get_object(generation.source_object_key)
            with stage_timer("engine", correlation_id=str(generation.id)):
                result = await self._editor.edit(
                    prompt=engine_prompt,
                source_image=source_image,
                width=width,
                height=height,
                seed=generation.seed,
                    on_progress=on_progress,
                )
        else:
            if self._generator is None:
                raise DomainError("Gerador de imagem nao configurado.")
            with stage_timer("engine", correlation_id=str(generation.id)):
                result = await self._generator.generate(
                    prompt=engine_prompt,
                width=width,
                height=height,
                    seed=generation.seed,
                    on_progress=on_progress,
                )

        generation.seed = result.seed
        state["image_bytes"] = result.image_bytes
        state["image_metadata"] = result
        state["progress"] = 90
        return state

    async def _post_process(self, state: _PipelineState) -> _PipelineState:
        """Valida, modera, grava original privado, marca d'agua e metadados."""
        if self._provider is not None:
            url = state.get("result_url", "")
            if not url.startswith(("https://", "http://")):
                raise DomainError("Output do agente nao e uma URL de imagem valida.")
            state["progress"] = 100
            return state

        generation = state["generation"]
        width, height = ASPECT_RATIO_DIMENSIONS[generation.aspect_ratio]
        metadata = state.get("image_metadata")
        image_bytes = state.get("image_bytes", b"")
        content_type = metadata.content_type if metadata is not None else "image/png"

        validate_image_bytes(
            image_bytes, expected_width=width, expected_height=height
        )
        image = metadata or EngineImage(
            image_bytes=image_bytes,
            width=width,
            height=height,
            seed=generation.seed or 0,
            duration_seconds=0.0,
            content_type=content_type,
        )
        if self._storage is None:
            raise DomainError("Storage de imagens nao configurado.")

        async def noop(_: int) -> None:
            return

        progress_callback = state.get("on_progress_callback") or noop
        await progress_callback(92)

        if self._image_moderation_enabled and self._image_moderator is not None:
            try:
                with stage_timer(
                    "output_image_moderation", correlation_id=str(generation.id)
                ):
                    moderation = await self._image_moderator.moderate(
                        image.image_bytes
                    )
            except ImageModerationUnavailableError as exc:
                raise ImageModerationUnavailableError(
                    message_for("image_moderation_unavailable", generation.locale)
                ) from exc
            if moderation.blocked and moderation.blocked_category is not None:
                category = moderation.blocked_category.value
                code = f"image_blocked_{category}"
                raise ImageBlockedError(
                    code=code,
                    message=message_for(code, generation.locale),
                    category=category,
                    layer="image_output",
                    confidence=max(
                        moderation.scores.sexual,
                        moderation.scores.gore,
                        moderation.scores.hate,
                        moderation.scores.self_harm,
                    ),
                )
        for processor in self._post_processors:
            image = processor.process(image, generation)
        validate_image_bytes(
            image.image_bytes, expected_width=width, expected_height=height
        )
        original_bytes = image.image_bytes
        await progress_callback(94)

        original_key = f"generations/{generation.id}/original.png"
        result_key = f"generations/{generation.id}/result.png"
        saved_original = False
        saved_result = False
        try:
            try:
                await self._storage.put_object(
                    original_key, original_bytes, content_type="image/png"
                )
            except Exception:
                UPLOAD_FAILURES_TOTAL.labels(stage="original").inc()
                raise
            saved_original = True
            generation.original_object_key = original_key
            await progress_callback(96)

            public_bytes = original_bytes
            with stage_timer("watermark_metadata", correlation_id=str(generation.id)):
                if self._watermarker is not None:
                    public_bytes = await asyncio.to_thread(
                        self._watermarker.apply, public_bytes
                    )
                if self._metadata_writer is not None:
                    public_bytes = await asyncio.to_thread(
                        self._metadata_writer.apply,
                        public_bytes,
                        model_name=_model_name(generation),
                    )
                if self._c2pa_signer is not None:
                    public_bytes = await asyncio.to_thread(
                        self._c2pa_signer.sign, public_bytes
                    )
            validate_image_bytes(public_bytes, expected_width=width, expected_height=height)
            await progress_callback(98)
            try:
                with stage_timer("upload", correlation_id=str(generation.id)):
                    await self._storage.put_object(
                        result_key, public_bytes, content_type="image/png"
                    )
            except Exception:
                UPLOAD_FAILURES_TOTAL.labels(stage="result").inc()
                raise
            saved_result = True
        except Exception:
            if saved_result:
                await _safe_delete(self._storage, result_key)
            if saved_original:
                await _safe_delete(self._storage, original_key)
                generation.original_object_key = None
            raise

        url = await self._storage.presigned_get_url(result_key)
        generation.result_object_key = result_key
        state["result_object_key"] = result_key
        state["result_url"] = url
        state["progress"] = 99
        return state

    # ---- wiring LangGraph (lazy) ----

    def _try_build_langgraph(self) -> Any | None:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None

        graph = StateGraph(_PipelineState)
        graph.add_node("assistant", self._assistant)
        graph.add_node("interpret_prompt", self._interpret_prompt)
        graph.add_node("safety_check", self._safety_check)
        graph.add_node("scope_check", self._scope_check)
        graph.add_node("moderate_source", self._moderate_source)
        graph.add_node("generate_or_edit", self._generate_or_edit)
        graph.add_node("post_process", self._post_process)
        graph.add_edge(START, "assistant")
        graph.add_edge("assistant", "interpret_prompt")
        graph.add_edge("interpret_prompt", "safety_check")
        graph.add_edge("safety_check", "scope_check")
        graph.add_edge("scope_check", "moderate_source")
        graph.add_edge("moderate_source", "generate_or_edit")
        graph.add_edge("generate_or_edit", "post_process")
        graph.add_edge("post_process", END)
        return graph.compile()

    # ---- porta ----

    async def run_generation(
        self, generation: Generation, on_progress: ProgressCallback
    ) -> str:
        initial: _PipelineState = {
            "generation": generation,
            "progress": 0,
            "on_progress_callback": on_progress,
        }
        if self._graph is not None:
            final = await self._graph.ainvoke(initial)
        else:
            final = await self._run_sequential(initial)
        await on_progress(99)
        return str(final["result_url"])

    async def _run_sequential(self, state: _PipelineState) -> _PipelineState:
        """Fallback sem langgraph: mesma ordem, mesmos nos."""
        for node in (
            self._assistant,
            self._interpret_prompt,
            self._safety_check,
            self._scope_check,
            self._moderate_source,
            self._generate_or_edit,
            self._post_process,
        ):
            state = await node(state)
        return state


def _model_name(generation: Generation) -> str:
    return "FLUX.1 Kontext" if generation.kind is GenerationKind.EDIT else "FLUX.1 Dev"


async def _safe_delete(storage: ObjectStoragePort, key: str) -> None:
    try:
        await storage.delete_object(key)
    except Exception:
        logger.warning("asset_cleanup_failed", extra={"key": key}, exc_info=True)
