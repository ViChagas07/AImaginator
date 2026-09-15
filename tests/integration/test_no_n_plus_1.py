"""Teste de regressao anti N+1 (spec secao 9.2).

Conta os statements emitidos por list_by_user. Se alguem introduzir
acesso lazy por item (padrao N+1), a contagem explode e o CI falha.

Roda em dois niveis:
- com sessao-espiao (sempre): prova que o repositorio emite 1 query;
- contra Postgres real (CI, service container): mesma assertiva fim a fim.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest


class _ScalarResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class SpySession:
    """Espiona chamadas de execute/get para contar queries."""

    def __init__(self, rows=()) -> None:
        self.execute_calls = 0
        self._rows = rows

    async def execute(self, _stmt):
        self.execute_calls += 1
        return _ScalarResult(self._rows)

    async def get(self, _model, _pk):
        self.execute_calls += 1
        return None


@pytest.mark.unit
async def test_list_by_user_emite_uma_unica_query() -> None:
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )

    session = SpySession(rows=[])
    repo = SQLAlchemyGenerationRepository(session)  # type: ignore[arg-type]
    await repo.list_by_user(uuid4(), cursor=None, limit=21)
    assert session.execute_calls == 1  # sem lazy por item


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Requer Postgres real (CI usa service container; defina RUN_DB_TESTS=1)",
)
async def test_list_by_user_sem_n_plus_1_contra_postgres() -> None:
    from sqlalchemy import event

    from infra.database import Base, get_engine, get_session_factory

    # Registra os modelos na metadata (imports de efeito colateral) e cria as
    # tabelas — o teste e autocontido, sem depender de alembic no CI.
    import modules.image_generation.adapters.repositories.models  # noqa: F401
    import modules.users.adapters.models  # noqa: F401
    from modules.image_generation.adapters.repositories.generation_repository import (
        SQLAlchemyGenerationRepository,
    )

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def count_sql(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    factory = get_session_factory()
    async with factory() as session:
        repo = SQLAlchemyGenerationRepository(session)
        await repo.list_by_user(uuid4(), cursor=None, limit=21)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1, f"N+1 detectado: {len(selects)} SELECTs"
