"""Configura o ambiente Prometheus antes de importar metricas."""

from __future__ import annotations

from infra.settings import get_settings
from modules.observability.prometheus_env import configure_prometheus_env

configure_prometheus_env(get_settings().prometheus_multiproc_dir)
