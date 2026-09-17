"""Wiring de dependencias da API (DI container, spec secao 3.2).

FastAPI Depends aponta para ca: cada request recebe instancias prontas
das portas/casos de uso, e os testes substituem tudo via
app.dependency_overrides (DIP na pratica).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database import get_session_factory
from infra.redis_client import get_redis
from infra.settings import Settings, get_settings
from modules.auth.contracts import GoogleOIDCService, JWTService
from modules.image_generation.adapters.cache.swr import SWRCache
from modules.image_generation.adapters.celery_task_queue import CeleryTaskQueue
from modules.image_generation.adapters.redis_event_publisher import RedisEventPublisher
from modules.image_generation.adapters.repositories.generation_repository import (
    SQLAlchemyGenerationRepository,
)
from modules.image_generation.application.ports.task_queue import TaskQueuePort
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.url_policy import UrlPolicy
from modules.image_generation.infra import wiring as gen_wiring
from modules.rate_limiting.circuit_breaker import CircuitBreaker
from modules.rate_limiting.token_bucket import TokenBucket
from modules.users.adapters.repository import SQLAlchemyUserRepository
from modules.users.contracts import User
from shared_kernel.errors import UnauthorizedError

ACCESS_COOKIE = "aimaginator_access"
REFRESH_COOKIE = "aimaginator_refresh"

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db_session() -> AsyncIterator[AsyncSession]:
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


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

RedisDep = Annotated[object, Depends(get_redis)]


# ---- users / auth ----


def get_user_repository(session: SessionDep) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


UserRepoDep = Annotated[SQLAlchemyUserRepository, Depends(get_user_repository)]


def get_jwt_service(settings: SettingsDep) -> JWTService:
    return JWTService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        access_ttl=settings.jwt_access_token_ttl_seconds,
        refresh_ttl=settings.jwt_refresh_token_ttl_seconds,
    )


JWTDep = Annotated[JWTService, Depends(get_jwt_service)]


def get_oidc_service(
    settings: SettingsDep, redis: RedisDep, http: HttpClientDep
) -> GoogleOIDCService:
    circuit = CircuitBreaker(
        redis,
        name="google_oauth",
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_seconds=settings.circuit_breaker_recovery_seconds,
    )
    return GoogleOIDCService(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_oauth_redirect_uri,
        redis_client=redis,
        http_client=http,
        circuit_breaker=circuit,
    )


OIDCDep = Annotated[GoogleOIDCService, Depends(get_oidc_service)]


async def authenticate_user(
    request: Request,
    jwt: JWTDep,
    users: UserRepoDep,
    *,
    query_token: str | None = None,
) -> User:
    """Resolve o usuario autenticado.

    Precedencia: token de query (SSE, que nao suporta headers customizados),
    depois `Authorization: Bearer`, depois cookie httpOnly (retrocompatibilidade
    com o fluxo antigo em ambiente same-origin).
    """
    token = query_token
    if not token:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get(ACCESS_COOKIE, "")
    if not token:
        raise UnauthorizedError("Credenciais ausentes.")
    user_id: UUID = jwt.verify_access_token(token)
    user = await users.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("Usuario da sessao nao existe mais.")
    return user


async def get_current_user(
    request: Request, jwt: JWTDep, users: UserRepoDep
) -> User:
    return await authenticate_user(request, jwt, users)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ---- image_generation ----


def get_generation_repository(session: SessionDep) -> SQLAlchemyGenerationRepository:
    return SQLAlchemyGenerationRepository(session)


GenerationRepoDep = Annotated[SQLAlchemyGenerationRepository, Depends(get_generation_repository)]


def get_task_queue() -> TaskQueuePort:
    return CeleryTaskQueue()


TaskQueueDep = Annotated[TaskQueuePort, Depends(get_task_queue)]


def get_prompt_guard() -> PromptInjectionGuard:
    return gen_wiring.build_prompt_guard()


PromptGuardDep = Annotated[PromptInjectionGuard, Depends(get_prompt_guard)]


def get_url_policy(settings: SettingsDep) -> UrlPolicy:
    return gen_wiring.build_url_policy(settings)


UrlPolicyDep = Annotated[UrlPolicy, Depends(get_url_policy)]


def get_swr_cache(redis: RedisDep) -> SWRCache:
    return SWRCache(redis, namespace="showcase")


SWRCacheDep = Annotated[SWRCache, Depends(get_swr_cache)]


def get_event_publisher(redis: RedisDep) -> RedisEventPublisher:
    return RedisEventPublisher(redis)


EventPublisherDep = Annotated[RedisEventPublisher, Depends(get_event_publisher)]


# ---- rate limiting ----


def get_generation_rate_limiter(settings: SettingsDep, redis: RedisDep) -> TokenBucket:
    return TokenBucket(
        redis, capacity=settings.rate_limit_generation_per_minute, window_seconds=60
    )


def get_auth_rate_limiter(settings: SettingsDep, redis: RedisDep) -> TokenBucket:
    return TokenBucket(redis, capacity=settings.rate_limit_auth_per_minute, window_seconds=60)
