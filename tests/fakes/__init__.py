"""Helper do executavel falso do sd-cli (nunca executa modelo real)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_FAKE_SCRIPT = Path(__file__).with_name("fake_sd_cli.py")


def create_fake_sd_cli(directory: Path) -> Path:
    """Cria um executavel falso multiplataforma e devolve o caminho."""
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        wrapper = directory / "fake sd-cli.cmd"
        wrapper.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "{_FAKE_SCRIPT}" %*\r\n',
            encoding="utf-8",
        )
        return wrapper
    wrapper = directory / "fake sd-cli"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" "{_FAKE_SCRIPT}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper
