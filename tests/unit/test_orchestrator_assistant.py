"""Integracao do assistente no orquestrador (LLM falso, sem modelo real)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.application.localization import message_for
from modules.image_generation.application.ports import EngineImage
from modules.image_generation.domain.entities import (
    AspectRatio,
    Generation,
    GenerationKind,
)
from modules.image_generation.domain.prompt_assistant import (
    AssistantResult,
    BlockedCategory,
    ModerationFlags,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from shared_kernel.security_errors import ContentBlockedError, OutOfScopeError
from tests.conftest import InMemoryObjectStorage


class FakeAssistant:
    def __init__(self, result: AssistantResult) -> None:
        self.result = result
        self.calls = []

    async def analyze(self, data):
        self.calls.append(data)
        return self.result


class FakeGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, *, prompt, width, height, seed, on_progress):
        self.prompts.append(prompt)
        await on_progress(10)
        await on_progress(90)
        return EngineImage(
            image_bytes=make_png_bytes(width, height),
            width=width,
            height=height,
            seed=7,
            duration_seconds=1.0,
        )


class FakeEditor(FakeGenerator):
    async def edit(self, *, prompt, source_image, width, height, seed, on_progress):
        self.prompts.append(prompt)
        await on_progress(10)
        await on_progress(90)
        return EngineImage(
            image_bytes=make_png_bytes(width, height),
            width=width,
            height=height,
            seed=7,
            duration_seconds=1.0,
        )


def _result(**overrides) -> AssistantResult:
    values = {
        "detected_language": "pt",
        "is_image_request": True,
        "in_scope": True,
        "moderation": ModerationFlags(),
        "blocked_category": None,
        "confidence": 0.95,
        "image_part_extracted": None,
        "corrected_text": "um castelo",
        "flux_prompt": "a castle in the clouds, cinematic",
        "kontext_instruction": (
            "Change only the sky to aurora. Keep everything else exactly the same."
        ),
        "suggested_aspect_ratio": AspectRatio.SQUARE,
    }
    values.update(overrides)
    return AssistantResult(**values)


def _agent(assistant, *, generator=None, editor=None, storage=None):
    return LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=generator or FakeGenerator(),
        editor=editor or FakeEditor(),
        storage=storage or InMemoryObjectStorage(),
        prompt_assistant=assistant,
    )


@pytest.mark.unit
async def test_flux_prompt_reescrito_e_enviado_ao_motor() -> None:
    assistant = FakeAssistant(_result())
    generator = FakeGenerator()
    agent = _agent(assistant, generator=generator)
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo", locale="pt-BR"
    )
    await agent.run_generation(generation, _noop)

    assert generator.prompts == ["a castle in the clouds, cinematic"]
    assert assistant.calls[0].text == "um castelo"


@pytest.mark.unit
async def test_kontext_instruction_e_enviada_na_edicao() -> None:
    assistant = FakeAssistant(_result(flux_prompt=None))
    editor = FakeEditor()
    storage = InMemoryObjectStorage()
    await storage.put_object("sources/1/source.png", make_png_bytes(32, 32))
    agent = _agent(assistant, editor=editor, storage=storage)
    generation = Generation(
        user_id=uuid4(),
        kind=GenerationKind.EDIT,
        prompt="troque o ceu",
        locale="pt-BR",
        source_object_key="sources/1/source.png",
    )
    await agent.run_generation(generation, _noop)

    assert editor.prompts[0].startswith("Change only")


@pytest.mark.unit
async def test_moderacao_levanta_content_blocked_com_categoria() -> None:
    assistant = FakeAssistant(
        _result(
            moderation=ModerationFlags(gore=True),
            blocked_category=BlockedCategory.GORE,
        )
    )
    agent = _agent(assistant)
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="gore", locale="en"
    )

    with pytest.raises(ContentBlockedError) as exc:
        await agent.run_generation(generation, _noop)
    assert exc.value.code == "content_blocked_gore"
    assert exc.value.category == "gore"
    assert exc.value.message == message_for("content_blocked_gore", "en")


@pytest.mark.unit
async def test_fora_de_escopo_levanta_erro_localizado() -> None:
    assistant = FakeAssistant(_result(is_image_request=False, in_scope=False))
    agent = _agent(assistant)
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="explique", locale="es"
    )

    with pytest.raises(OutOfScopeError) as exc:
        await agent.run_generation(generation, _noop)
    assert exc.value.message == message_for("out_of_scope", "es")


@pytest.mark.unit
async def test_progresso_do_assistente_acontece_antes_do_motor() -> None:
    assistant = FakeAssistant(_result())
    progress: list[int] = []

    async def collect(percent: int) -> None:
        progress.append(percent)

    agent = _agent(assistant)
    generation = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo")
    await agent.run_generation(generation, collect)

    assert progress[:2] == [7, 10]
    assert 10 in progress


@pytest.mark.unit
async def test_unload_acontece_antes_do_motor() -> None:
    order: list[str] = []

    class _Unloader:
        async def unload_all(self) -> bool:
            order.append("unload")
            return True

    class _RecordingGenerator(FakeGenerator):
        async def generate(self, *, prompt, width, height, seed, on_progress):
            order.append("generate")
            return await super().generate(
                prompt=prompt,
                width=width,
                height=height,
                seed=seed,
                on_progress=on_progress,
            )

    agent = LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=_RecordingGenerator(),
        editor=FakeEditor(),
        storage=InMemoryObjectStorage(),
        prompt_assistant=FakeAssistant(_result()),
        llm_unloader=_Unloader(),
    )
    generation = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo")
    await agent.run_generation(generation, _noop)

    assert order == ["unload", "generate"]


@pytest.mark.unit
async def test_falha_do_unload_nao_derruba_o_job() -> None:
    class _FailingUnloader:
        async def unload_all(self) -> bool:
            raise RuntimeError("lms quebrou")

    agent = LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=FakeGenerator(),
        editor=FakeEditor(),
        storage=InMemoryObjectStorage(),
        prompt_assistant=FakeAssistant(_result()),
        llm_unloader=_FailingUnloader(),
    )
    generation = Generation(user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo")
    result = await agent.run_generation(generation, _noop)
    assert result


async def _noop(_: int) -> None:
    return None
