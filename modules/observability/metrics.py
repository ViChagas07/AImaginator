"""Metricas Prometheus da aplicacao (spec secao 18)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "aimaginator_http_requests_total",
    "Requisicoes HTTP por endpoint/metodo/status",
    ["method", "endpoint", "status"],
)
HTTP_REQUEST_LATENCY = Histogram(
    "aimaginator_http_request_latency_seconds",
    "Latencia por endpoint",
    ["method", "endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
GENERATIONS_TOTAL = Counter(
    "aimaginator_generations_total",
    "Geracoes por tipo/status final",
    ["kind", "status"],
)
GENERATION_DURATION = Histogram(
    "aimaginator_generation_duration_seconds",
    "Latencia ponta a ponta de uma geracao de imagem",
    ["kind"],
    buckets=(1, 5, 10, 30, 60, 120, 300),
)
CACHE_OPERATIONS = Counter(
    "aimaginator_cache_operations_total",
    "Operacoes de cache SWR",
    ["operation"],  # hit_fresh | hit_stale | miss | revalidate
)
CIRCUIT_BREAKER_STATE = Gauge(
    "aimaginator_circuit_breaker_open",
    "Circuit breaker aberto (1) ou fechado (0) por dependencia",
    ["dependency"],
)
CELERY_QUEUE_SIZE = Gauge(
    "aimaginator_celery_queue_size",
    "Tamanho das filas Celery (aproximado, via broker)",
    ["queue"],
)
RATE_LIMIT_REJECTIONS = Counter(
    "aimaginator_rate_limit_rejections_total",
    "Requisicoes rejeitadas por rate limit",
    ["scope"],
)


def render_metrics() -> bytes:
    return generate_latest()
