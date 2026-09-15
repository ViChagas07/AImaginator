"""Infra de banco de dados: engine e sessoes SQLAlchemy 2.x assincronas.

Decisoes:
- asyncpg como driver (obrigatorio para async real).
- expire_on_commit=False: evita lazy-load implicito pos-commit, que em
  contexto async explode em MissingGreenlet (spec secao 9.2).
- Relacionamentos SEMPRE com selectinload/joinedload explicitos nos
  repositorios (anti N+1) — nunca depender de lazy loading.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from infra.settings import get_settings


class Base(DeclarativeBase):
    """Base declarativa unica. Cada modulo declara seus modelos a partir dela."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # descarta conexoes mortas antes de usar
            pool_recycle=1800,
            echo=settings.app_env == "development" and False,  # nunca logar SQL em prod
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Contexto de sessao com commit/rollback automatico (uso em workers/use cases)."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Fecha o pool (shutdown da app / teardown de testes)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
