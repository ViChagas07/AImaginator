"""Parser do progresso impresso pelo sd-cli.

Formato observado no spike: `| 3/8 - 19.5s/it` (a primeira linha costuma ser
mais lenta e a barra final repete o total). O parser ignora qualquer outra
linha e devolve apenas passos validos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STEP_RE = re.compile(
    r"\|\s*(\d+)\s*/\s*(\d+)"
    r"(?:\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*s/it\b|\s*(?=\||$))",
    re.IGNORECASE,
)

PROGRESS_START = 10
PROGRESS_END = 90


@dataclass(frozen=True, slots=True)
class StepProgress:
    current: int
    total: int
    seconds_per_step: float | None = None


def parse_progress_line(line: str) -> StepProgress | None:
    match = _STEP_RE.search(line)
    if match is None:
        return None
    current = int(match.group(1))
    total = int(match.group(2))
    if total <= 0 or current < 0 or current > total:
        return None
    seconds = float(match.group(3)) if match.group(3) is not None else None
    return StepProgress(current=current, total=total, seconds_per_step=seconds)


def progress_for_step(step: StepProgress) -> int:
    """Mapeia o passo para a faixa 10..90 reservada ao runtime."""
    if step.total <= 0:
        return PROGRESS_START
    ratio = min(max(step.current / step.total, 0.0), 1.0)
    return PROGRESS_START + round((PROGRESS_END - PROGRESS_START) * ratio)
