"""Metricas: definicoes, labels seguros, multiprocesso e cronometro de etapa."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import structlog
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest
from prometheus_client.multiprocess import MultiProcessCollector

from modules.observability import metrics
from modules.observability.prometheus_env import (
    clean_multiproc_dir,
    configure_prometheus_env,
)
from modules.observability.timing import stage_timer

FORBIDDEN_LABELS = {
    "prompt",
    "email",
    "e-mail",
    "ip",
    "user_id",
    "generation_id",
    "url",
    "signed_url",
    "object_key",
    "seed",
    "source",
    "result",
}


def _count(name: str, labels: dict[str, str]) -> float:
    metric = REGISTRY.get_sample_value(name, labels)
    return float(metric or 0)


@pytest.mark.unit
def test_metricas_do_pipeline_tem_tipo_e_labels_baixa_cardinalidade() -> None:
    counters = {
        metrics.GENERATIONS_TOTAL: ("kind", "status"),
        metrics.REFUSALS_TOTAL: ("code",),
        metrics.LLM_REQUESTS_TOTAL: ("outcome",),
        metrics.ENGINE_FAILURES_TOTAL: ("kind", "reason"),
        metrics.CREDITS_REFUNDED_TOTAL: ("reason",),
        metrics.PENALTIES_TOTAL: ("level",),
        metrics.IMAGE_MODERATION_BLOCKS_TOTAL: ("category", "layer"),
        metrics.UPLOAD_FAILURES_TOTAL: ("stage",),
    }
    for metric, labels in counters.items():
        assert metric._labelnames == tuple(labels)
    histograms = {
        metrics.GENERATION_DURATION: ("kind",),
        metrics.STAGE_DURATION: ("stage",),
        metrics.LLM_LATENCY: (),
        metrics.ENGINE_PEAK_RAM_BYTES: ("kind",),
        metrics.SSE_STREAM_DURATION: (),
    }
    for metric, labels in histograms.items():
        assert metric._labelnames == tuple(labels)


@pytest.mark.unit
def test_nenhum_label_proibido_no_registry() -> None:
    for family in REGISTRY.collect():
        for sample in family.samples:
            for label in sample.labels:
                assert label.lower() not in FORBIDDEN_LABELS, family.name


@pytest.mark.unit
def test_stage_timer_mede_e_loga_sem_prompt() -> None:
    values = iter([10.0, 12.5])

    def fake_clock() -> float:
        return next(values)

    stage = "unit_stage_timer"
    before = _count("aimaginator_stage_duration_seconds_count", {"stage": stage})
    with structlog.testing.capture_logs() as logs:
        with stage_timer(
            stage, correlation_id="corr-1", clock=fake_clock
        ):
            pass
    after = _count("aimaginator_stage_duration_seconds_count", {"stage": stage})
    assert after == before + 1
    assert logs[-1]["event"] == "stage_completed"
    assert logs[-1]["correlation_id"] == "corr-1"
    assert logs[-1]["duration_seconds"] == 2.5
    assert "prompt" not in logs[-1]


@pytest.mark.unit
def test_stage_timer_loga_falha_sem_payload() -> None:
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(RuntimeError):
            with stage_timer("unit_stage_fail", correlation_id="corr-2"):
                raise RuntimeError("segredo do usuario")
    event = logs[-1]
    assert event["event"] == "stage_failed"
    assert event["error_type"] == "RuntimeError"
    assert event["correlation_id"] == "corr-2"
    assert "segredo do usuario" not in str(event)


@pytest.mark.unit
def test_gauge_de_fila_e_baixa_cardinalidade(monkeypatch) -> None:
    from workers.celery_app import worker_metrics

    monkeypatch.setattr(worker_metrics, "_queue_size", lambda queue: 7)
    worker_metrics.collect_queue_sizes(("test-queue",))
    assert (
        REGISTRY.get_sample_value(
            "aimaginator_celery_queue_size", {"queue": "test-queue"}
        )
        == 7
    )


@pytest.mark.unit
def test_configura_e_limpa_diretorio_multiprocesso(tmp_path) -> None:
    directory = configure_prometheus_env(str(tmp_path / "prom"))
    assert directory is not None
    assert Path(directory).is_dir()
    (Path(directory) / "x.db").write_bytes(b"old")
    clean_multiproc_dir(directory)
    assert list(Path(directory).iterdir()) == []
    os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)


@pytest.mark.unit
def test_filho_encerrado_aparece_no_endpoint_agregado(tmp_path) -> None:
    directory = tmp_path / "multiproc"
    directory.mkdir()
    code = (
        "from prometheus_client import Counter\n"
        "c = Counter('aimaginator_test_child_total', '', ['kind'])\n"
        "c.labels(kind='generate').inc()\n"
    )
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(directory)}
    subprocess.run(  # noqa: S603
            [sys.executable, "-c", code], check=True, env=env
        )

    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(directory)
    try:
        registry = CollectorRegistry()
        MultiProcessCollector(registry, path=str(directory))
        text = generate_latest(registry).decode()
    finally:
        os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
    assert 'aimaginator_test_child_total{kind="generate"} 1.0' in text


@pytest.mark.unit
def test_render_metrics_usa_multiprocesso_quando_configurado(tmp_path) -> None:
    directory = tmp_path / "multiproc"
    directory.mkdir()
    code = (
        "from prometheus_client import Counter\n"
        "c = Counter('aimaginator_test_render_total', '')\n"
        "c.inc()\n"
    )
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(directory)}
    subprocess.run(  # noqa: S603
            [sys.executable, "-c", code], check=True, env=env
        )

    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(directory)
    try:
        assert b"aimaginator_test_render_total 1.0" in metrics.render_metrics()
    finally:
        os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
