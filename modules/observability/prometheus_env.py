"""Configuracao do modo multiprocesso do prometheus_client.

Deve ser importado ANTES de qualquer modulo que crie Metric objects.
O diretorio vem de settings (PROMETHEUS_MULTIPROC_DIR). No worker, o
diretorio e limpo no signal worker_init (processo principal).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def configure_prometheus_env(multiproc_dir: str | None = None) -> str | None:
    """Exporta PROMETHEUS_MULTIPROC_DIR e garante que o diretorio existe."""
    path = (multiproc_dir or "").strip()
    if not path:
        return None
    Path(path).mkdir(parents=True, exist_ok=True)
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = path
    return path


def clean_multiproc_dir(path: str) -> None:
    """Remove arquivos de metricas antigas no startup do worker."""
    directory = Path(path)
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return
    for child in directory.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink()
        except OSError:
            logger.warning("prometheus_cleanup_failed", exc_info=True)
