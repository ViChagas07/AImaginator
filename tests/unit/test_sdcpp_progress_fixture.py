"""Progresso real do sd-cli: carga de tensor nao e passo de sampling."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.image_generation.adapters.sdcpp.progress import (
    parse_progress_line,
    progress_for_step,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sdcpp_stdout_real.txt"


@pytest.mark.unit
def test_carga_de_tensores_nao_vira_passo_de_sampling() -> None:
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()

    tensor_lines = [line for line in lines if "MB/s" in line]
    assert tensor_lines
    assert all(parse_progress_line(line) is None for line in tensor_lines)

    sampling_lines = [
        parse_progress_line(line) for line in lines if "s/it" in line
    ]
    steps = [step for step in sampling_lines if step is not None]
    assert [step.current for step in steps] == [1, 2, 3]
    assert [progress_for_step(step) for step in steps] == [20, 30, 40]


@pytest.mark.unit
def test_linha_de_passo_sem_segundos_continua_aceita() -> None:
    parsed = parse_progress_line("| 4/8")
    assert parsed is not None
    assert parsed.current == 4
    assert parsed.total == 8
    assert parsed.seconds_per_step is None
