"""Adapter stable-diffusion.cpp (sd-cli) — geracao e edicao por subprocesso.

Nenhum teste executa o modelo real: o binario e sempre um executavel falso.
A montagem do comando e uma funcao pura e o parser de progresso e testado
isoladamente com linhas reais do sd-cli.
"""

from __future__ import annotations

from modules.image_generation.adapters.sdcpp.engine import (
    SdCppImageEditor,
    SdCppImageGenerator,
)
from modules.image_generation.adapters.sdcpp.progress import (
    StepProgress,
    parse_progress_line,
    progress_for_step,
)

__all__ = [
    "SdCppImageEditor",
    "SdCppImageGenerator",
    "StepProgress",
    "parse_progress_line",
    "progress_for_step",
]
