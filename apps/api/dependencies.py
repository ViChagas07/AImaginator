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
from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database import get_session_factory
from infra.redis_client import get_redis
from infra.settings import Settings, get_settings
from modules.auth.application.anonymous_identity import (
    generate_anonymous_id,
    sign_anonymous_id,
    unsign_anonymous_id,
)
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
from modules.prompt_quota.adapters.redis_quota_store import RedisPromptQuotaStore
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
        redirect_uri=settings.google_oauth_redirect_uri
        or f"{settings.api_base_url.rstrip('/')}/api/v1/auth/google/callback",
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


async def get_optional_current_user(
    request: Request, jwt: JWTDep, users: UserRepoDep
) -> User | None:
    """Resolve o usuario se autenticado; devolve None para anonimos."""
    try:
        return await authenticate_user(request, jwt, users)
    except UnauthorizedError:
        return None


OptionalCurrentUserDep = Annotated[User | None, Depends(get_optional_current_user)]


def resolve_anonymous_session(request: Request, settings: Settings) -> tuple[str, str | None]:
    """Resolve (ou cria) a sessao anonima assinada.

    Devolve (anonymous_id, token_a_definir). Se o token existir e for
    valido, token_a_definir e None; caso contrario um novo id e criado e
    o token deve ser gravado no cliente (cookie + corpo da resposta).
    """
    token = request.headers.get("X-Anonymous-Session") or request.cookies.get(
        settings.anonymous_session_cookie_name
    )
    if token:
        max_age = settings.anonymous_session_max_age_days * 86400
        existing = unsign_anonymous_id(token, secret_key=settings.secret_key, max_age=max_age)
        if existing is not None:
            return existing, None

    anonymous_id = generate_anonymous_id()
    new_token = sign_anonymous_id(anonymous_id, secret_key=settings.secret_key)
    return anonymous_id, new_token


def set_anonymous_session_cookie(
    response: Response, settings: Settings, token: str | None
) -> None:
    """Grava a sessao anonima assinada no cliente (cookie httpOnly)."""
    if token is None:
        return
    response.set_cookie(
        key=settings.anonymous_session_cookie_name,
        value=token,
        max_age=settings.anonymous_session_max_age_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )


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


# ---- prompt quota (Bloco 1) ----


def get_prompt_quota_store(redis: RedisDep) -> RedisPromptQuotaStore:
    return RedisPromptQuotaStore(redis)


PromptQuotaStoreDep = Annotated[RedisPromptQuotaStore, Depends(get_prompt_quota_store)]


def get_prompt_quota_rate_limiter(settings: SettingsDep, redis: RedisDep) -> TokenBucket:
    return TokenBucket(
        redis, capacity=settings.rate_limit_prompt_quota_per_minute, window_seconds=60
    )
