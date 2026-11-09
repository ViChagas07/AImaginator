"""Corrida cancelamento x conclusao, ownership anonimo e seed uint32."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import BigInteger

from modules.image_generation.adapters.repositories.models import GenerationModel
from modules.image_generation.application.use_cases.cancel_generation import (
    CancelGeneration,
)
from modules.image_generation.application.use_cases.process_generation import (
    ProcessGeneration,
)
from modules.image_generation.application.use_cases.read_generations import (
    GetGeneration,
)
from modules.image_generation.domain.entities import (
    Generation,
    GenerationKind,
    GenerationStatus,
)
from shared_kernel.errors import ForbiddenError
from tests.conftest import InMemoryGenerationRepository


class _CasRepo:
    """Repo de teste com compare-and-set atomico como o SQLAlchemy."""

    def __init__(self, generation: Generation) -> None:
        self.generation = generation
        self._lock = asyncio.Lock()

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
        async with self._lock:
            if self.generation.status not in from_statuses:
                return False
            for key, value in values.items():
                if hasattr(self.generation, key):
                    setattr(self.generation, key, value)
            # Como no SQLAlchemy: o CAS altera a linha, mas a entidade
            # carregada so muda quando o caso de uso chama transition_to.
            return True

    async def touch_processing(self, generation_id, *, updated_at) -> bool:
        async with self._lock:
            if self.generation.status is not GenerationStatus.PROCESSING:
                return False
            self.generation.updated_at = updated_at
            return True


class _Events:
    def __init__(self) -> None:
        self.events = []

    async def publish_progress(self, event) -> None:
        self.events.append(event)


class _Redis:
    def __init__(self) -> None:
        self.keys: dict[str, tuple[int, str]] = {}

    async def setex(self, key, ttl, value) -> None:
        self.keys[key] = (ttl, value)


class _Quota:
    def __init__(self) -> None:
        self.refunds: list[str] = []

    async def refund(self, principal: str) -> bool:
        self.refunds.append(principal)
        return True


class _Storage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete_object(self, key) -> None:
        self.deleted.append(key)


class _Agent:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run_generation(self, generation: Generation, on_progress) -> str:
        generation.original_object_key = f"generations/{generation.id}/original.png"
        generation.result_object_key = f"generations/{generation.id}/result.png"
        generation.seed = 1
        self.started.set()
        await self.release.wait()
        await on_progress(50)
        return "https://cdn.example/result.png"


def _anonymous_generation(session: str = "session-a") -> Generation:
    return Generation(
        user_id=None,
        anonymous_session_id=session,
        kind=GenerationKind.GENERATE,
        prompt="cabana",
    )


def _user_generation() -> Generation:
    return Generation(
        user_id=uuid4(),
        kind=GenerationKind.GENERATE,
        prompt="cabana",
    )


@pytest.mark.unit
@pytest.mark.parametrize("presented_user", [None, uuid4()])
async def test_anonimo_nao_pode_cancelar_geracao_de_outra_sessao_ou_usuario(
    presented_user,
) -> None:
    generation = _anonymous_generation("session-a")
    use_case = CancelGeneration(
        generations=_CasRepo(generation),
        events=_Events(),
        redis=_Redis(),
        quota_refund=_Quota(),
    )
    with pytest.raises(ForbiddenError):
        await use_case.execute(
            user_id=presented_user,
            anonymous_session_id="session-b" if presented_user is None else None,
            generation_id=generation.id,
        )


@pytest.mark.unit
async def test_anonimo_nao_pode_ler_geracao_de_outra_sessao() -> None:
    generation = _anonymous_generation("session-a")
    generation.transition_to(GenerationStatus.PROCESSING)
    generation.attach_result("https://cdn.example/result.png")
    repo = InMemoryGenerationRepository()
    await repo.save(generation)
    use_case = GetGeneration(repo)

    with pytest.raises(ForbiddenError):
        await use_case.execute(
            user_id=None,
            anonymous_session_id="session-b",
            generation_id=generation.id,
        )
    with pytest.raises(ForbiddenError):
        await use_case.execute(
            user_id=uuid4(),
            anonymous_session_id=None,
            generation_id=generation.id,
        )
    output = await use_case.execute(
        user_id=None,
        anonymous_session_id="session-a",
        generation_id=generation.id,
    )
    assert output.id == generation.id


@pytest.mark.unit
async def test_cancelar_anonimo_na_fila_refunda_uma_vez() -> None:
    generation = _anonymous_generation()
    quota = _Quota()
    result = await CancelGeneration(
        generations=_CasRepo(generation),
        events=_Events(),
        redis=_Redis(),
        quota_refund=quota,
    ).execute(
        user_id=None,
        anonymous_session_id="session-a",
        generation_id=generation.id,
    )

    assert result["status"] == "canceled"
    assert generation.status is GenerationStatus.CANCELED
    assert quota.refunds == ["anon:session-a"]


@pytest.mark.unit
async def test_cancelar_depois_de_done_nao_refunda_nem_publica() -> None:
    generation = _anonymous_generation()
    generation.transition_to(GenerationStatus.PROCESSING)
    generation.attach_result("https://cdn.example/result.png")
    events = _Events()
    quota = _Quota()
    result = await CancelGeneration(
        generations=_CasRepo(generation),
        events=events,
        redis=_Redis(),
        quota_refund=quota,
    ).execute(
        user_id=None,
        anonymous_session_id="session-a",
        generation_id=generation.id,
    )

    assert result["already_finished"] is True
    assert result["status"] == "done"
    assert quota.refunds == []
    assert events.events == []
    assert generation.status is GenerationStatus.DONE


@pytest.mark.unit
async def test_cancelamento_que_vence_antes_da_conclusao_nao_entrega_imagem() -> None:
    generation = _anonymous_generation()
    repo = _CasRepo(generation)
    events = _Events()
    quota = _Quota()
    storage = _Storage()
    agent = _Agent()
    canceled = False

    async def cancel_check() -> bool:
        return canceled

    process = ProcessGeneration(
        generations=repo,
        image_agent=agent,
        events=events,
        storage=storage,
        quota_refund=quota,
        cancel_check=cancel_check,
    )
    process_task = asyncio.create_task(
        process.execute(generation.id, raise_on_failure=False)
    )
    await asyncio.wait_for(agent.started.wait(), timeout=2)

    cancel_result = await CancelGeneration(
        generations=repo,
        events=events,
        redis=_Redis(),
        quota_refund=quota,
    ).execute(
        user_id=None,
        anonymous_session_id="session-a",
        generation_id=generation.id,
    )
    assert cancel_result["status"] == "cancel_requested"
    assert quota.refunds == []

    canceled = True
    agent.release.set()
    await asyncio.wait_for(process_task, timeout=2)

    assert generation.status is GenerationStatus.CANCELED
    assert generation.result_object_key is None
    assert generation.result_image_url is None
    assert quota.refunds == ["anon:session-a"]
    assert storage.deleted == [
        f"generations/{generation.id}/result.png",
        f"generations/{generation.id}/original.png",
    ]
    assert events.events[-1].status is GenerationStatus.CANCELED


@pytest.mark.unit
def test_seed_e_bigint_para_uint32_do_sdcli() -> None:
    assert isinstance(GenerationModel.__table__.c.seed.type, BigInteger)
