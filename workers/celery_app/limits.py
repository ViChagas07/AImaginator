"""Politica de limites de tempo da fila por tipo de geracao (Fase 2, Bloco 4)."""

from __future__ import annotations

import math
from typing import Protocol

# Margem para o soft limit: o worker recebe o aviso antes do hard kill.
SOFT_LIMIT_MARGIN_SECONDS = 30
# Margem para pos-processamento/upload quando o assistente LLM roda no job.
ASSISTANT_TASK_OVERHEAD_SECONDS = 30


class TimeoutSettings(Protocol):
    generation_timeout_seconds: int
    edit_timeout_seconds: int
    llm_timeout_seconds: float


def task_time_limits(kind: str, settings: TimeoutSettings) -> tuple[int, int]:
    """Devolve (soft_time_limit, time_limit) cobrindo LLM + motor.

    O assistente roda antes do FLUX no mesmo job; por isso o limite da task e
    o timeout do motor mais o timeout maximo do LLM (primeira chamada carrega
    o modelo).
    """
    if kind == "upscale":
        upscale_timeout = int(
            getattr(settings, "upscale_timeout_seconds", 300) or 300
        )
        return upscale_timeout, upscale_timeout + SOFT_LIMIT_MARGIN_SECONDS
    engine_timeout = (
        settings.edit_timeout_seconds
        if kind == "edit"
        else settings.generation_timeout_seconds
    )
    llm_timeout = float(getattr(settings, "llm_timeout_seconds", 0) or 0)
    overhead = math.ceil(llm_timeout)
    if overhead > 0:
        overhead += ASSISTANT_TASK_OVERHEAD_SECONDS
    timeout = engine_timeout + overhead
    soft = max(1, timeout - SOFT_LIMIT_MARGIN_SECONDS)
    return soft, timeout
