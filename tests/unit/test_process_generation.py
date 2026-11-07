"""Testes do ProcessGeneration: erros estaveis, progresso e URL assinada."""

from __future__ import annotations

from uuid import uuid4

import pytest
from prometheus_client import REGISTRY

from modules.image_generation.application.use_cases.process_generation import (
    ProcessGeneration,
)
from modules.image_generation.domain.engine_errors import EngineTimeoutError
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from modules.image_generation.domain.moderation import (
    ModerationCategory,
    ModerationLayer,
    PenaltyOutcome,
)
from shared_kernel.security_errors import (
    AssistantUnavailableError,
    ContentBlockedError,
    ImageBlockedError,
    OutOfScopeError,
)
from tests.conftest import (
    InMemoryGenerationRepository,
    InMemoryObjectStorage,
    SpyEventPublisher,
)


class _FailingAgent:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def run_generation(self, generation, on_progress):
        await on_progress(50)
        raise self._exc


class _SuccessfulAgent:
    async def run_generation(self, generation, on_progress):
        for percent in (10, 50, 90):
            await on_progress(percent)
        generation.result_object_key = f"generations/{generation.id}/result.png"
        return "https://old-presigned.example/result.png"


class FakeModerationService:
    def __init__(self) -> None:
        self.calls = []

    async def record_moderation(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs.get("apply_penalty", True):
            return PenaltyOutcome(level=0, warning_level=None, warning_message=None)
        return PenaltyOutcome(
            level=1, warning_level=1, warning_message="warning localized"
        )


class FakeQuotaRefund:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def refund(self, principal: str) -> bool:
        self.calls.append(principal)
        return True


async def _execute(
    agent,
    *,
    storage=None,
    moderation=None,
    quota_refund=None,
    locale="pt-BR",
    user_id=None,
    users_repo=None,
):
    repo = InMemoryGenerationRepository()
    generation = Generation(
        user_id=user_id,
        kind=GenerationKind.GENERATE,
        prompt="um castelo",
        locale=locale,
    )
    if user_id is None:
        generation.anonymous_session_id = "anon-1"
    await repo.save(generation)
    events = SpyEventPublisher()
    use_case = ProcessGeneration(
        generations=repo,
        image_agent=agent,
        events=events,
        storage=storage,
        moderation=moderation,
        quota_refund=quota_refund,
        users=users_repo,
    )
    try:
        await use_case.execute(generation.id)
    except Exception:  # noqa: S110 - estado final e inspecionado abaixo
        pass
    saved = await repo.get_by_id(generation.id)
    return saved, events


@pytest.mark.unit
async def test_modo_worker_nao_levanta_depois_de_persistir_falha() -> None:
    repo = InMemoryGenerationRepository()
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )
    await repo.save(generation)
    use_case = ProcessGeneration(
        generations=repo,
        image_agent=_FailingAgent(EngineTimeoutError()),
        events=SpyEventPublisher(),
    )
    await use_case.execute(generation.id, raise_on_failure=False)
    saved = await repo.get_by_id(generation.id)
    assert saved is not None
    assert saved.status == GenerationStatus.FAILED
    assert saved.error_code == "engine_timeout"


@pytest.mark.unit
async def test_timeout_incrementa_metricas_de_motor_e_geracao() -> None:
    before_engine = REGISTRY.get_sample_value(
        "aimaginator_engine_failures_total",
        {"kind": "generate", "reason": "timeout"},
    ) or 0
    before_failed = REGISTRY.get_sample_value(
        "aimaginator_generations_total",
        {"kind": "generate", "status": "failed"},
    ) or 0
    await _execute(_FailingAgent(EngineTimeoutError()))
    after_engine = REGISTRY.get_sample_value(
        "aimaginator_engine_failures_total",
        {"kind": "generate", "reason": "timeout"},
    ) or 0
    after_failed = REGISTRY.get_sample_value(
        "aimaginator_generations_total",
        {"kind": "generate", "status": "failed"},
    ) or 0
    assert after_engine == before_engine + 1
    assert after_failed == before_failed + 1


@pytest.mark.unit
async def test_timeout_vira_failed_com_codigo_estavel() -> None:
    saved, events = await _execute(_FailingAgent(EngineTimeoutError()))

    assert saved is not None
    assert saved.status == GenerationStatus.FAILED
    assert saved.error_code == "engine_timeout"
    assert saved.error_message == "O processamento excedeu o tempo limite."
    assert events.events[-1].error_code == "engine_timeout"
    assert "C:" not in (events.events[-1].error or "")


@pytest.mark.unit
async def test_erro_desconhecido_nao_vaza_detalhes() -> None:
    saved, events = await _execute(
        _FailingAgent(RuntimeError("falhou em C:\\caminho\\secreto"))
    )

    assert saved is not None
    assert saved.error_code == "engine_failed"
    assert saved.error_message == "Falha no processamento."
    assert "C:\\" not in (events.events[-1].error or "")


@pytest.mark.unit
async def test_done_usa_url_assinada_do_storage() -> None:
    storage = InMemoryObjectStorage()
    repo_agent = _SuccessfulAgent()

    repo = InMemoryGenerationRepository()
    generation = Generation(
        user_id=uuid4(), kind=GenerationKind.GENERATE, prompt="um castelo"
    )
    object_key = f"generations/{generation.id}/result.png"
    await storage.put_object(object_key, b"png")
    await repo.save(generation)
    events = SpyEventPublisher()
    await ProcessGeneration(
        generations=repo, image_agent=repo_agent, events=events, storage=storage
    ).execute(generation.id)

    saved = await repo.get_by_id(generation.id)
    assert saved is not None
    assert saved.status == GenerationStatus.DONE
    assert saved.result_image_url is not None
    assert "signature=test" in saved.result_image_url
    assert events.events[-1].result_image_url == saved.result_image_url


@pytest.mark.unit
async def test_moderacao_registra_evento_e_publica_aviso() -> None:
    moderation = FakeModerationService()
    refund = FakeQuotaRefund()
    exc = ContentBlockedError(
        code="content_blocked_gore",
        message="bloqueado",
        category="gore",
        layer="llm",
        confidence=0.9,
    )
    saved, events = await _execute(
        _FailingAgent(exc),
        moderation=moderation,
        quota_refund=refund,
        locale="en",
    )

    assert len(moderation.calls) == 1
    assert moderation.calls[0]["category"] is ModerationCategory.GORE
    assert moderation.calls[0]["layer"] is ModerationLayer.LLM
    assert moderation.calls[0]["prompt_text"] == "um castelo"
    assert saved is not None and saved.status == GenerationStatus.FAILED
    assert saved.quota_refunded is True
    assert saved.warning_level == 1
    assert saved.warning_message == "warning localized"
    assert refund.calls == ["anon:anon-1"]
    assert events.events[-1].warning_level == 1
    assert events.events[-1].warning_message == "warning localized"


@pytest.mark.unit
async def test_fora_de_escopo_devolve_cota_sem_evento_de_moderacao() -> None:
    moderation = FakeModerationService()
    refund = FakeQuotaRefund()
    saved, events = await _execute(
        _FailingAgent(OutOfScopeError("fora")),
        moderation=moderation,
        quota_refund=refund,
    )

    assert moderation.calls == []
    assert refund.calls == ["anon:anon-1"]
    assert saved is not None and saved.quota_refunded is True
    assert events.events[-1].warning_level is None


@pytest.mark.unit
async def test_llm_indisponivel_devolve_cota() -> None:
    refund = FakeQuotaRefund()
    saved, _ = await _execute(
        _FailingAgent(AssistantUnavailableError("indisponivel")),
        quota_refund=refund,
    )
    assert saved is not None and saved.quota_refunded is True
    assert refund.calls == ["anon:anon-1"]


@pytest.mark.unit
async def test_refund_de_usuario_usa_principal_logado() -> None:
    user_id = uuid4()
    refund = FakeQuotaRefund()
    await _execute(
        _FailingAgent(AssistantUnavailableError("indisponivel")),
        quota_refund=refund,
        user_id=user_id,
    )
    assert refund.calls == [f"user:{user_id}"]


@pytest.mark.unit
async def test_bloqueio_de_entrada_conta_penalidade() -> None:
    moderation = FakeModerationService()
    exc = ImageBlockedError(
        code="source_image_blocked_gore",
        message="origem bloqueada",
        category="gore",
        layer="image_input",
        confidence=0.9,
    )
    saved, events = await _execute(
        _FailingAgent(exc), moderation=moderation
    )
    assert saved is not None and saved.error_code == "source_image_blocked_gore"
    assert moderation.calls[0]["apply_penalty"] is True
    assert events.events[-1].warning_level == 1


@pytest.mark.unit
async def test_bloqueio_de_saida_nao_conta_penalidade(sample_user) -> None:
    from tests.conftest import InMemoryUserRepository

    moderation = FakeModerationService()
    exc = ImageBlockedError(
        code="image_blocked_nsfw",
        message="saida bloqueada",
        category="nsfw",
        layer="image_output",
        confidence=0.9,
    )
    users = InMemoryUserRepository(sample_user)
    saved, events = await _execute(
        _FailingAgent(exc),
        moderation=moderation,
        users_repo=users,
        user_id=sample_user.id,
    )
    assert saved is not None and saved.error_code == "image_blocked_nsfw"
    assert moderation.calls[0]["apply_penalty"] is False
    assert events.events[-1].warning_level is None
    assert saved.credits_refunded is True


@pytest.mark.unit
async def test_falha_do_motor_devolve_credito_uma_vez(sample_user) -> None:
    from tests.conftest import InMemoryUserRepository

    users = InMemoryUserRepository(sample_user)
    saved, _ = await _execute(
        _FailingAgent(EngineTimeoutError()),
        user_id=sample_user.id,
        users_repo=users,
    )
    assert saved is not None
    assert saved.credits_refunded is True
    assert sample_user.generation_credits == 6

    use_case = ProcessGeneration(
        generations=InMemoryGenerationRepository(),
        image_agent=_FailingAgent(EngineTimeoutError()),
        events=SpyEventPublisher(),
        users=users,
    )
    await use_case._refund_credit(saved)
    assert sample_user.generation_credits == 6


@pytest.mark.unit
async def test_moderacao_tambem_devolve_credito(sample_user) -> None:
    from tests.conftest import InMemoryUserRepository

    exc = ContentBlockedError(
        code="content_blocked_nsfw",
        message="bloqueado",
        category="nsfw",
        layer="llm",
        confidence=0.9,
    )
    users = InMemoryUserRepository(sample_user)
    saved, _ = await _execute(
        _FailingAgent(exc), user_id=sample_user.id, users_repo=users
    )
    assert saved is not None
    assert saved.credits_refunded is True
    assert sample_user.generation_credits == 6


@pytest.mark.unit
async def test_progresso_do_motor_nao_e_reescalado() -> None:
    _, events = await _execute(_SuccessfulAgent())
    progress = [e.progress for e in events.events if e.status == GenerationStatus.PROCESSING]
    assert progress == [5, 10, 50, 90]
