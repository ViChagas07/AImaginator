"""Logs estruturados nao vazam o texto do prompt, mesmo em falhas."""

from __future__ import annotations

from uuid import uuid4

import pytest
import structlog

from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.providers import make_png_bytes
from modules.image_generation.application.ports import EngineImage
from modules.image_generation.domain.entities import Generation, GenerationKind
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from tests.conftest import InMemoryObjectStorage

SECRET = "PROMPT_SECRETO_QUE_NAO_PODE_IR_PARA_LOG"


class _Moderator:
    async def moderate(self, image_bytes):
        from modules.image_generation.application.ports.image_moderation import (
            ImageModerationResult,
            ImageModerationScores,
        )

        return ImageModerationResult(scores=ImageModerationScores())


class _Generator:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def generate(self, *, prompt, width, height, seed, on_progress):
        if self.fail:
            raise RuntimeError(SECRET)
        await on_progress(90)
        return EngineImage(
            image_bytes=make_png_bytes(width, height),
            width=width,
            height=height,
            seed=1,
            duration_seconds=0.1,
        )


class _Editor(_Generator):
    async def edit(self, *, prompt, source_image, width, height, seed, on_progress):
        return await self.generate(
            prompt=prompt, width=width, height=height, seed=seed, on_progress=on_progress
        )


def _agent(*, fail: bool = False) -> LangGraphImageAgent:
    return LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=_Generator(fail=fail),
        editor=_Editor(fail=fail),
        storage=InMemoryObjectStorage(),
        image_moderator=_Moderator(),
        image_moderation_enabled=True,
    )


@pytest.mark.unit
async def test_logs_de_sucesso_nao_contem_prompt() -> None:
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt=SECRET
    )
    with structlog.testing.capture_logs() as logs:
        await _agent().run_generation(generation, _noop)
    assert SECRET not in repr(logs)


@pytest.mark.unit
async def test_logs_de_falha_nao_contem_prompt_nem_mensagem_bruta() -> None:
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt=SECRET
    )
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(RuntimeError):
            await _agent(fail=True).run_generation(generation, _noop)
    serialized = repr(logs)
    assert SECRET not in serialized
    assert "RuntimeError" in serialized


async def _noop(_: int) -> None:
    return None
