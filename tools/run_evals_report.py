"""Roda as evals reais do assistente e gera docs/agent/EVALS_REPORT.md.

Uso (manual, com LM Studio/Qwen carregado):
    python tools/run_evals_report.py

Equivale a:
    RUN_LLM_EVALS=1 pytest specs/evals -m eval -k prompt_assistant -s
com EVALS_REPORT_PATH configurado.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "agent" / "EVALS_REPORT.md"


def main() -> int:
    print("=" * 72)
    print("EVALS REAIS DO ASSISTENTE (LLM local)")
    print("Feche programas pesados, monitore RAM/temperatura e rode uma vez.")
    print("=" * 72)
    env = {
        **os.environ,
        "RUN_LLM_EVALS": "1",
        "EVALS_REPORT_PATH": str(REPORT),
    }
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "specs/evals",
            "-m",
            "eval",
            "-k",
            "prompt_assistant",
            "-s",
        ],
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    if result.returncode == 0:
        print(f"Relatorio gerado em {REPORT}")
    else:
        print("As evals falharam; veja a saida acima.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
