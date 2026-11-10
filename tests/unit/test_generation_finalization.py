"""Finalizacao terminal: fallback, refund unico e politica de retry."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.image_generation.application.use_cases.process_generation import (
    ProcessGeneration,
)
from modules.image_generation.domain.engine_errors import EngineFailedError
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from shared_kernel.errors import GenerationFinalizationError
from shared_kernel.security_errors import AssistantUnavailableError


class _Repo:
    def __init__(self, generation: Generation, *, fail_terminal: bool = False) -> None:
        self.generation = generation
        self.fail_terminal = fail_terminal

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
        if self.fail_terminal and to_status in (
            GenerationStatus.FAILED,
            GenerationStatus.CANCELED,
        ):
            raise RuntimeError("db indisponivel")
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


class _FailingAfterEngineAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run_generation(self, generation, on_progress) -> str:
        self.calls += 1
        await on_progress(50)
        raise EngineFailedError()


class _TransientBeforeEngineAgent:
    async def run_generation(self, generation, on_progress) -> str:
        raise AssistantUnavailableError("assistente indisponivel")


class _NeverCalledAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run_generation(self, generation, on_progress) -> str:
        self.calls += 1
        return "https://example.test/result.png"


def _generation() -> Generation:
    return Generation(
        user_id=None,
        anonymous_session_id="session-a",
        kind=GenerationKind.GENERATE,
        prompt="cabana",
    )


@pytest.mark.unit
async def test_falha_apos_motor_nao_reexecuta_agente() -> None:
    generation = _generation()
    agent = _FailingAfterEngineAgent()
    events = _Events()
    quota = _Quota()
    process = ProcessGeneration(
        generations=_Repo(generation),
        image_agent=agent,
        events=events,
        quota_refund=quota,
        cancel_check=None,
    )

    await process.execute(generation.id, raise_on_failure=True)

    assert agent.calls == 1
    assert generation.status is GenerationStatus.FAILED
    assert generation.error_code == "engine_failed"
    assert quota.refunds == ["anon:session-a"]
    assert events.events[-1].status is GenerationStatus.FAILED


@pytest.mark.unit
async def test_falha_transitoria_antes_do_motor_propaga_para_retry() -> None:
    generation = _generation()
    events = _Events()
    quota = _Quota()
    process = ProcessGeneration(
        generations=_Repo(generation),
        image_agent=_TransientBeforeEngineAgent(),
        events=events,
        quota_refund=quota,
        cancel_check=None,
    )

    with pytest.raises(AssistantUnavailableError):
        await process.execute(generation.id, raise_on_failure=False)

    assert generation.status is GenerationStatus.PROCESSING
    assert quota.refunds == []
    assert all(event.status is not GenerationStatus.FAILED for event in events.events)


@pytest.mark.unit
async def test_finalizacao_sem_estado_terminal_levanta_erro() -> None:
    generation = _generation()
    agent = _FailingAfterEngineAgent()
    process = ProcessGeneration(
        generations=_Repo(generation, fail_terminal=True),
        image_agent=agent,
        events=_Events(),
        quota_refund=_Quota(),
        cancel_check=None,
    )

    with pytest.raises(GenerationFinalizationError):
        await process.execute(generation.id, raise_on_failure=False)

    assert agent.calls == 1


@pytest.mark.unit
async def test_cancel_flag_no_inicio_nao_chama_agente() -> None:
    generation = _generation()
    agent = _NeverCalledAgent()
    events = _Events()
    quota = _Quota()

    async def cancel_check() -> bool:
        return True

    process = ProcessGeneration(
        generations=_Repo(generation),
        image_agent=agent,
        events=events,
        quota_refund=quota,
        cancel_check=cancel_check,
    )

    await process.execute(generation.id, raise_on_failure=True)

    assert agent.calls == 0
    assert generation.status is GenerationStatus.CANCELED
    assert generation.error_code == "canceled"
    assert quota.refunds == ["anon:session-a"]
    assert events.events[-1].status is GenerationStatus.CANCELED


@pytest.mark.unit
def test_task_no_limite_de_retries_nao_termina_com_sucesso(monkeypatch) -> None:
    from workers.celery_app import tasks as tasks_module

    calls = {"ensure": 0, "dlq": 0}

    def _ensure(generation_id: str, error_code: str) -> bool:
        calls["ensure"] += 1
        return True

    def _dlq(generation_id: str, error_code: str) -> None:
        calls["dlq"] += 1

    async def _boom(generation_id: str, kind: str = "generate") -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks_module, "_process_generation_async", _boom)
    monkeypatch.setattr(tasks_module, "_MAX_RETRIES", 0)
    monkeypatch.setattr(tasks_module, "ensure_failed_after_retries_sync", _ensure)
    monkeypatch.setattr(tasks_module, "_send_to_dlq", _dlq)

    with pytest.raises(RuntimeError):
        tasks_module.process_generation_task.run(str(uuid4()))

    assert calls == {"ensure": 1, "dlq": 1}
