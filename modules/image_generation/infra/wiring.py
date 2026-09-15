"""Wiring de dependencias do modulo image_generation (camada infra do modulo).

Monta o grafo de objetos do modulo a partir das implementacoes
concretas, mantendo apps/api livre de detalhes de construcao.
"""

from __future__ import annotations

from typing import Any

import httpx

from infra.settings import Settings
from modules.image_generation.adapters.ai_agents.orchestrator import LangGraphImageAgent
from modules.image_generation.adapters.ai_agents.providers import (
    HttpImageProvider,
    ImageProvider,
    StubImageProvider,
)
from modules.image_generation.domain.prompt_guard import PromptInjectionGuard
from modules.image_generation.domain.url_policy import UrlPolicy
from modules.rate_limiting.bulkhead import bulkhead_registry
from modules.rate_limiting.circuit_breaker import CircuitBreaker


def build_prompt_guard() -> PromptInjectionGuard:
    return PromptInjectionGuard()


def build_url_policy(settings: Settings) -> UrlPolicy:
    return UrlPolicy(settings.allowed_image_domains)


def build_image_provider(
    settings: Settings, *, redis_client: Any, http_client: httpx.AsyncClient
) -> ImageProvider:
    if settings.ai_image_provider == "stub":
        return StubImageProvider(storage_base_url=settings.storage_bucket_url or "https://picsum.photos")
    circuit = CircuitBreaker(
        redis_client,
        name="ai_image_provider",
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_seconds=settings.circuit_breaker_recovery_seconds,
    )
    bulkhead = bulkhead_registry.get_or_create("ai_image_provider", max_concurrent=8, max_queued=50)
    return HttpImageProvider(
        http_client=http_client,
        circuit_breaker=circuit,
        bulkhead=bulkhead,
        api_base_url=settings.ai_image_api_base_url,
        api_key=settings.ai_image_api_key,
    )


def build_image_agent(provider: ImageProvider, guard: PromptInjectionGuard) -> LangGraphImageAgent:
    return LangGraphImageAgent(provider=provider, prompt_guard=guard)
