"""Inicializacao do Sentry com scrubbing de dados sensiveis (spec secao 18).

NUNCA enviar ao Sentry: tokens, prompts de usuarios, cookies, headers
de autorizacao, corpos de request. Apenas contexto tecnico.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "prompt",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "email",
        "e-mail",
        "ip",
        "ip_address",
        "client_ip",
        "remote_ip",
        "request_ip",
        "user_id",
        "generation_id",
        "object_key",
        "source_image_url",
        "result_image_url",
        "url",
        "signed_url",
        "query_string",
    }
)

_SENSITIVE_FRAGMENTS = (
    "prompt",
    "token",
    "secret",
    "password",
    "email",
    "object_key",
    "signed_url",
    "url",
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in SENSITIVE_KEYS or any(
        fragment in lowered for fragment in _SENSITIVE_FRAGMENTS
    )


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SIGNED_URL_RE = re.compile(r"(X-Amz-Signature=|sig=)[^&\s]+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(prompt|seed|email|e-mail|ip|token|object_key|url)\s*[:=]\s*[^\s,&;]+"
)


def scrub_text(value: str) -> str:
    """Remove e-mail, IP, tokens e URLs assinadas de texto livre."""
    text = _EMAIL_RE.sub("[Filtered]", value)
    text = _IPV4_RE.sub("[Filtered]", text)
    text = _SIGNED_URL_RE.sub(r"\1[Filtered]", text)
    text = _BEARER_RE.sub("Bearer [Filtered]", text)
    text = _JWT_RE.sub("[Filtered]", text)
    return _KEY_VALUE_RE.sub(r"\1=[Filtered]", text)


def _scrub_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[Filtered]"
                if _is_sensitive_key(str(key))
                else _scrub_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def _scrub_event(event: dict[str, Any], _hint: Any) -> dict[str, Any] | None:
    """Remove dados sensiveis de request, mensagens, breadcrumbs e contexto."""
    event.pop("user", None)
    request = event.get("request", {})
    if isinstance(request, dict):
        if "headers" in request:
            request["headers"] = {
                k: ("[Filtered]" if _is_sensitive_key(str(k)) else scrub_text(str(v)))
                for k, v in request["headers"].items()
            }
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("env", None)
        if "query_string" in request:
            request["query_string"] = "[Filtered]"
        if "url" in request:
            request["url"] = scrub_text(str(request["url"]))

    for value in event.get("exception", {}).get("values", []):
        if isinstance(value, dict):
            if "value" in value:
                value["value"] = scrub_text(str(value["value"]))
            for frame in value.get("stacktrace", {}).get("frames", []):
                vars_ = frame.get("vars", {})
                if isinstance(vars_, dict):
                    for key in list(vars_):
                        if _is_sensitive_key(str(key)):
                            vars_[key] = "[Filtered]"

    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        if isinstance(breadcrumb, dict):
            if "message" in breadcrumb:
                breadcrumb["message"] = scrub_text(str(breadcrumb["message"]))
            if "data" in breadcrumb:
                breadcrumb["data"] = _scrub_value(breadcrumb["data"])

    event["extra"] = _scrub_value(event.get("extra", {}))
    event["contexts"] = _scrub_value(event.get("contexts", {}))
    event["tags"] = _scrub_value(event.get("tags", {}))
    if "message" in event:
        event["message"] = scrub_text(str(event["message"]))
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
