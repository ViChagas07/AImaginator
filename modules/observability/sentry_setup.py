"""Inicializacao do Sentry com scrubbing de dados sensiveis (spec secao 18).

NUNCA enviar ao Sentry: tokens, prompts de usuarios, cookies, headers
de autorizacao, corpos de request. Apenas contexto tecnico.
"""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "prompt", "token", "refresh_token"}
)


def _scrub_event(event: dict[str, Any], _hint: Any) -> dict[str, Any] | None:
    """Remove dados sensiveis do evento antes do envio."""
    request = event.get("request", {})
    if "headers" in request:
        request["headers"] = {
            k: ("[Filtered]" if k.lower() in SENSITIVE_KEYS else v)
            for k, v in request["headers"].items()
        }
    request.pop("data", None)  # corpo do request nunca sai daqui
    request.pop("cookies", None)

    for value in event.get("exception", {}).get("values", []):
        for frame in value.get("stacktrace", {}).get("frames", []):
            vars_ = frame.get("vars", {})
            for key in list(vars_):
                if any(s in key.lower() for s in SENSITIVE_KEYS):
                    vars_[key] = "[Filtered]"
    return event


def init_sentry(*, dsn: str, environment: str, traces_sample_rate: float = 0.1) -> None:
    if not dsn:
        return  # observabilidade desligada sem DSN (dev local)
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        before_send=_scrub_event,
        integrations=[FastApiIntegration(), CeleryIntegration(), SqlalchemyIntegration()],
    )
