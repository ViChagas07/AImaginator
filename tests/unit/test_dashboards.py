"""Valida JSON dos dashboards e regras de alerta versionadas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DASHBOARDS = Path("infra/docker/grafana/dashboards")
ALERTS = Path("infra/docker/prometheus/alerts.yml")


@pytest.mark.unit
def test_dashboards_sao_json_valido_e_usam_metricas_reais() -> None:
    files = sorted(DASHBOARDS.glob("*.json"))
    assert files
    known = {
        "aimaginator_http_requests_total",
        "aimaginator_generation_duration_seconds_bucket",
        "aimaginator_generations_total",
        "aimaginator_stage_duration_seconds_bucket",
        "aimaginator_refusals_total",
        "aimaginator_engine_failures_total",
        "aimaginator_llm_latency_seconds_bucket",
        "aimaginator_celery_queue_size",
        "aimaginator_ram_free_bytes",
        "aimaginator_engine_peak_ram_bytes_bucket",
        "aimaginator_credits_refunded_total",
        "aimaginator_penalties_total",
        "aimaginator_upscale_limit_hits_total",
        "aimaginator_upload_failures_total",
        "aimaginator_rate_limit_rejections_total",
    }
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["title"]
        assert payload["panels"]
        for panel in payload["panels"]:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                assert any(metric in expr for metric in known), (path, expr)


@pytest.mark.unit
def test_alertas_cobrem_pipeline_e_nao_vazam_prompt() -> None:
    text = ALERTS.read_text(encoding="utf-8")
    for metric in (
        "aimaginator_engine_failures_total",
        "aimaginator_celery_queue_size",
        "aimaginator_refusals_total",
        "aimaginator_llm_requests_total",
        "aimaginator_upload_failures_total",
    ):
        assert metric in text
    assert "prompt" not in text.lower()
    assert "generation_id" not in text
