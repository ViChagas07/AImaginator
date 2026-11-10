"""Persistencia real das transicoes terminais contra Postgres migrado.

Os testes criam um schema temporario no banco apontado por DATABASE_URL,
rodam `alembic upgrade head` nesse schema e usam o repositorio SQLAlchemy
real. Nao exigem CREATEDB nem tocam no schema `public`/dados de dev.

Para rodar:
    RUN_DB_TESTS=1 DATABASE_URL=postgresql+asyncpg://... \
        pytest tests/integration/test_generation_status_persistence.py -q

Sem RUN_DB_TESTS=1 o modulo inteiro e pulado (comportamento intencional,
documentado no README).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import modules.users.adapters.models  # noqa: F401  (registra users no metadata)
from modules.image_generation.domain.entities import GenerationKind, GenerationStatus

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requer Postgres real; defina RUN_DB_TESTS=1",
    ),
]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_async(coro):
    return asyncio.run(coro)


async def _create_schema(base_url: str, schema: str) -> None:
    engine = create_async_engine(base_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        await engine.dispose()


async def _drop_schema(base_url: str, schema: str) -> None:
    engine = create_async_engine(base_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def migrated_schema() -> tuple[str, str]:
    base_url = os.environ["DATABASE_URL"]
    schema = f"test_gen_{uuid4().hex[:12]}"
    _run_async(_create_schema(base_url, schema))
    try:
        target = os.environ.get("ALEMBIC_TARGET_REVISION", "head")
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            cwd=_REPO_ROOT,
            env={
                **os.environ,
                "DATABASE_URL": base_url,
                "ALEMBIC_SEARCH_PATH": schema,
            },
            check=True,
        )
        yield base_url, schema
    finally:
        _run_async(_drop_schema(base_url, schema))


@pytest.fixture
async def session_factory(migrated_schema: tuple[str, str]):
    base_url, schema = migrated_schema
    engine = create_async_engine(
        base_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _insert_generation(
    session,
    *,
    status: str,
    kind: str = "generate",
) -> tuple:
    from modules.image_generation.adapters.repositories.models import GenerationModel

    anon = f"test-{uuid4().hex}"
    model = GenerationModel(
        id=uuid4(),
        user_id=None,
        anonymous_session_id=anon,
        kind=kind,
        status=status,
        prompt="teste de persistencia terminal",
        credits_cost=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(model)
    await session.commit()
    return model.id, anon


async def _row(session, generation_id):
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )

    return await SQLAlchemyGenerationRepository(session).get_by_id(generation_id)


class _QuotaRefund:
    def __init__(self) -> None:
        self.principals: list[str] = []

    async def refund(self, principal: str) -> bool:
        self.principals.append(principal)
        return True


class _CancelAgent:
    async def run_generation(self, generation, on_progress):
        from shared_kernel.security_errors import GenerationCanceledError

        raise GenerationCanceledError("Geracao cancelada.")


class _DoneAgent:
    async def run_generation(self, generation, on_progress):
        await on_progress(50)
        return "https://example.test/result.png"


@pytest.mark.integration
async def test_queued_to_canceled_against_postgres(session_factory) -> None:
    from fakeredis.aioredis import FakeRedis

    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.application.use_cases.cancel_generation import (
        CancelGeneration,
    )
    from tests.conftest import SpyEventPublisher

    async with session_factory() as session:
        gen_id, anon = await _insert_generation(session, status="queued")
        quota = _QuotaRefund()
        events = SpyEventPublisher()
        result = await CancelGeneration(
            generations=SQLAlchemyGenerationRepository(session),
            events=events,
            redis=FakeRedis(decode_responses=True),
            quota_refund=quota,
        ).execute(user_id=None, anonymous_session_id=anon, generation_id=gen_id)
        await session.commit()

        assert result["status"] == "canceled"
        assert (await _row(session, gen_id)).status is GenerationStatus.CANCELED
        assert quota.principals == [f"anon:{anon}"]
        assert events.events[-1].status is GenerationStatus.CANCELED


@pytest.mark.integration
async def test_processing_to_canceled_against_postgres(session_factory) -> None:
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.application.use_cases.process_generation import (
        ProcessGeneration,
    )
    from tests.conftest import SpyEventPublisher

    async def _true() -> bool:
        return True

    async with session_factory() as session:
        gen_id, anon = await _insert_generation(session, status="processing")
        quota = _QuotaRefund()
        events = SpyEventPublisher()
        use_case = ProcessGeneration(
            generations=SQLAlchemyGenerationRepository(session),
            image_agent=_CancelAgent(),
            events=events,
            quota_refund=quota,
            commit=session.commit,
            cancel_check=_true,
        )
        await use_case.execute(gen_id, raise_on_failure=False)
        await session.commit()

        assert (await _row(session, gen_id)).status is GenerationStatus.CANCELED
        assert quota.principals == [f"anon:{anon}"]
        assert events.events[-1].status is GenerationStatus.CANCELED


@pytest.mark.integration
async def test_processing_to_done_against_postgres(session_factory) -> None:
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )
    from modules.image_generation.application.use_cases.process_generation import (
        ProcessGeneration,
    )
    from tests.conftest import SpyEventPublisher

    async with session_factory() as session:
        gen_id, _ = await _insert_generation(session, status="processing")
        use_case = ProcessGeneration(
            generations=SQLAlchemyGenerationRepository(session),
            image_agent=_DoneAgent(),
            events=SpyEventPublisher(),
            commit=session.commit,
        )
        await use_case.execute(gen_id, raise_on_failure=False)
        await session.commit()

        row = await _row(session, gen_id)
        assert row.status is GenerationStatus.DONE
        assert row.result_image_url == "https://example.test/result.png"


@pytest.mark.integration
async def test_cancel_done_race_against_postgres(session_factory) -> None:
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )

    async with session_factory() as session:
        gen_id, _ = await _insert_generation(session, status="processing")

    async def transition(to_status):
        async with session_factory() as session:
            repo = SQLAlchemyGenerationRepository(session)
            changed = await repo.transition_if_status(
                gen_id,
                from_statuses=(GenerationStatus.PROCESSING,),
                to_status=to_status,
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await session.commit()
            return changed

    results = await asyncio.gather(
        transition(GenerationStatus.CANCELED),
        transition(GenerationStatus.DONE),
    )
    assert sorted(results) == [False, True]

    async with session_factory() as session:
        row = await _row(session, gen_id)
        assert row.status in (GenerationStatus.CANCELED, GenerationStatus.DONE)


@pytest.mark.integration
@pytest.mark.parametrize("status", list(GenerationStatus), ids=lambda item: item.value)
async def test_status_value_is_accepted_by_schema(session_factory, status) -> None:
    async with session_factory() as session:
        gen_id, _ = await _insert_generation(session, status=status.value)
        assert (await _row(session, gen_id)).status is status


@pytest.mark.integration
@pytest.mark.parametrize("kind", list(GenerationKind), ids=lambda item: item.value)
async def test_kind_value_is_accepted_by_schema(session_factory, kind) -> None:
    async with session_factory() as session:
        gen_id, _ = await _insert_generation(
            session, status=GenerationStatus.QUEUED.value, kind=kind.value
        )
        assert (await _row(session, gen_id)).kind is kind
