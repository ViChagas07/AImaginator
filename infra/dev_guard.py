"""Guarda de infraestrutura local em desenvolvimento.

Em APP_ENV=development, broker/cache/DB/storage remotos sao quase sempre um
acidente (ex.: .env de producao carregado no lugar do .env.development).
Falhamos cedo, sem nunca imprimir credenciais.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from modules.observability.logging_config import get_logger

logger = get_logger(__name__)

LOCAL_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
        # nomes de servico do docker-compose de dev
        "postgres",
        "redis",
        "rabbitmq",
        "minio",
        "api",
        "worker",
    }
)

_URL_SETTINGS = (
    ("database", "database_url"),
    ("redis", "redis_url"),
    ("rabbitmq", "rabbitmq_url"),
    ("celery_broker", "celery_broker_url"),
    ("celery_result_backend", "celery_result_backend"),
    ("s3_endpoint", "s3_endpoint_url"),
)


@dataclass(frozen=True, slots=True)
class RemoteInfra:
    component: str
    host: str


def find_remote_infra(settings) -> list[RemoteInfra]:
    """Lista componentes cujo host nao e local. Nunca inclui credenciais."""
    remote: list[RemoteInfra] = []
    for component, field_name in _URL_SETTINGS:
        value = getattr(settings, field_name, "") or ""
        if not value.strip():
            continue
        host = (urlsplit(value).hostname or "").lower()
        if not host or host in LOCAL_HOSTS:
            continue
        remote.append(RemoteInfra(component=component, host=host))
    return remote


def enforce_local_infra(settings) -> None:
    """Falha o startup em dev se algum componente apontar para fora.

    ALLOW_REMOTE_INFRA_IN_DEV=true e a escape hatch consciente.
    """
    if not settings.is_development or settings.allow_remote_infra_in_dev:
        return
    remote = find_remote_infra(settings)
    if not remote:
        configured = [
            component
            for component, field_name in _URL_SETTINGS
            if (getattr(settings, field_name, "") or "").strip()
        ]
        logger.info("dev_infra_local", components=configured)
        return
    logger.error(
        "dev_remote_infra_detected",
        components=[{"component": r.component, "host": r.host} for r in remote],
    )
    names = ", ".join(f"{r.component}={r.host}" for r in remote)
    msg = (
        "Infraestrutura remota detectada em APP_ENV=development: "
        f"{names}. Use .env.development (localhost/compose) ou defina "
        "ALLOW_REMOTE_INFRA_IN_DEV=true conscientemente."
    )
    raise RuntimeError(msg)
