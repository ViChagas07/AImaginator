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
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 900, 1200),
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
    multiprocess_mode="max",
)
CELERY_QUEUE_SIZE = Gauge(
    "aimaginator_celery_queue_size",
    "Tamanho das filas Celery (aproximado, via broker)",
    ["queue"],
    multiprocess_mode="max",
)
RATE_LIMIT_REJECTIONS = Counter(
    "aimaginator_rate_limit_rejections_total",
    "Requisicoes rejeitadas por rate limit",
    ["scope"],
)
IMAGE_MODERATION_BLOCKS_TOTAL = Counter(
    "aimaginator_image_moderation_blocks_total",
    "Imagens bloqueadas pela moderacao visual",
    ["category", "layer"],
)
MODERATION_EVENTS_TOTAL = Counter(
    "aimaginator_moderation_events_total",
    "Eventos de moderacao por categoria e camada (sem texto de prompt)",
    ["category", "layer"],
)
REFUSALS_TOTAL = Counter(
    "aimaginator_refusals_total",
    "Recusas por codigo estavel (sem prompt)",
    ["code"],
)
STAGE_DURATION = Histogram(
    "aimaginator_stage_duration_seconds",
    "Duracao por etapa do pipeline",
    ["stage"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600, 1200),
)
LLM_REQUESTS_TOTAL = Counter(
    "aimaginator_llm_requests_total",
    "Chamadas ao LLM por resultado",
    ["outcome"],
)
LLM_LATENCY = Histogram(
    "aimaginator_llm_latency_seconds",
    "Latencia das chamadas ao LLM",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 90),
)
LLM_JSON_REPAIRS_TOTAL = Counter(
    "aimaginator_llm_json_repairs_total",
    "Tentativas de reparo de JSON do assistente",
)
LLM_CATEGORY_MISMATCH_TOTAL = Counter(
    "aimaginator_llm_category_mismatch_total",
    "Divergencia entre blocked_category declarado e booleanos de moderacao",
    ["declared", "derived"],
)
LLM_REWRITE_REPAIRS_TOTAL = Counter(
    "aimaginator_llm_rewrite_repairs_total",
    "Reparos deterministas de reescrita do assistente",
    ["outcome"],  # repaired | sanitized | invalid | unavailable
)
LLM_UNLOAD_TOTAL = Counter(
    "aimaginator_llm_unload_total",
    "Tentativas de descarregar o LLM via lms CLI",
    ["outcome"],  # success | failed | timeout | missing
)
QUEUE_RECONCILED_TOTAL = Counter(
    "aimaginator_queue_reconciled_total",
    "Geracoes orfas reconciliadas por codigo",
    ["code"],
)
ENGINE_FAILURES_TOTAL = Counter(
    "aimaginator_engine_failures_total",
    "Falhas do motor de imagem por motivo",
    ["kind", "reason"],
)
ENGINE_PEAK_RAM_BYTES = Histogram(
    "aimaginator_engine_peak_ram_bytes",
    "Pico de RAM do subprocesso do motor (amostrado)",
    ["kind"],
    buckets=tuple(
        value * 1024 for value in (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768)
    ),
)
RAM_FREE_BYTES = Gauge(
    "aimaginator_ram_free_bytes",
    "RAM livre antes do job",
    ["kind"],
    multiprocess_mode="max",
)
CREDITS_REFUNDED_TOTAL = Counter(
    "aimaginator_credits_refunded_total",
    "Creditos devolvidos por motivo",
    ["reason"],
)
QUOTA_REFUNDS_TOTAL = Counter(
    "aimaginator_quota_refunds_total",
    "Chances diarias devolvidas por motivo",
    ["reason"],
)
PENALTIES_TOTAL = Counter(
    "aimaginator_penalties_total",
    "Penalidades aplicadas por nivel",
    ["level"],
)
UPSCALE_LIMIT_HITS_TOTAL = Counter(
    "aimaginator_upscale_limit_hits_total",
    "Tentativas de upscale barradas pelo limite diario",
)
UPLOAD_FAILURES_TOTAL = Counter(
    "aimaginator_upload_failures_total",
    "Falhas de upload/persistencia de imagem",
    ["stage"],
)
SSE_CONNECTIONS_ACTIVE = Gauge(
    "aimaginator_sse_connections_active",
    "Streams SSE ativos",
    multiprocess_mode="livesum",
)
SSE_STREAM_DURATION = Histogram(
    "aimaginator_sse_stream_duration_seconds",
    "Duracao dos streams SSE",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1200),
)


def render_metrics() -> bytes:
    import os

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import CollectorRegistry
        from prometheus_client.multiprocess import MultiProcessCollector

        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()
