"""Cancelamento efetivo durante a chamada ao assistente LLM."""

from __future__ import annotations

import asyncio
import time

import pytest

from modules.image_generation.adapters.ai_agents.orchestrator import (
    LangGraphImageAgent,
)
from modules.image_generation.application.use_cases.process_generation import (
    ProcessGeneration,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard


class _Repo:
    def __init__(self, generation: Generation) -> None:
        self.generation = generation

    async def get_by_id(self, generation_id):
        return self.generation

    async def save(self, generation):
        self.generation = generation

    async def transition_if_status(
        self,
        generation_id,
        *,
        from_statuses,
        to_status,
        **values,
    ) -> bool:
        if self.generation.status not in from_statuses:
            return False
        for key, value in values.items():
            if hasattr(self.generation, key):
                setattr(self.generation, key, value)
        return True

    async def touch_processing(self, generation_id, *, updated_at) -> bool:
        if self.generation.status is not GenerationStatus.PROCESSING:
            return False
        self.generation.updated_at = updated_at
        return True


class _Events:
    def __init__(self) -> None:
        self.events = []

    async def publish_progress(self, event) -> None:
        self.events.append(event)


class _Quota:
    def __init__(self) -> None:
        self.refunds: list[str] = []

    async def refund(self, principal: str) -> bool:
        self.refunds.append(principal)
        return True


class _SlowAssistant:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def analyze(self, data):
        self.started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("assistente lento nao deveria concluir")


class _NeverGenerator:
    async def generate(self, **kwargs):
        raise AssertionError("motor nao deveria rodar")


class _NeverEditor:
    async def edit(self, **kwargs):
        raise AssertionError("motor nao deveria rodar")


@pytest.mark.unit
async def test_cancelamento_aborta_assistente_em_aproximadamente_1s() -> None:
    generation = Generation(
        user_id=None,
        anonymous_session_id="session-a",
        kind=GenerationKind.GENERATE,
        prompt="cabana",
    )
    repo = _Repo(generation)
    events = _Events()
    quota = _Quota()
    assistant = _SlowAssistant()
    canceled = False

    async def cancel_check() -> bool:
        return canceled

    agent = LangGraphImageAgent(
        prompt_guard=PromptInjectionGuard(),
        generator=_NeverGenerator(),
        editor=_NeverEditor(),
        prompt_assistant=assistant,
        cancel_check=cancel_check,
    )
    process = ProcessGeneration(
        generations=repo,
        image_agent=agent,
        events=events,
        quota_refund=quota,
        cancel_check=cancel_check,
    )

    started = time.monotonic()
    task = asyncio.create_task(
        process.execute(generation.id, raise_on_failure=False)
    )
    await asyncio.wait_for(assistant.started.wait(), timeout=2)
    await asyncio.sleep(0.1)
    canceled = True
    await asyncio.wait_for(task, timeout=3)
    elapsed = time.monotonic() - started

    assert assistant.cancelled is True
    assert elapsed < 2.5
    assert generation.status is GenerationStatus.CANCELED
    assert quota.refunds == ["anon:session-a"]
    assert events.events[-1].status is GenerationStatus.CANCELED
