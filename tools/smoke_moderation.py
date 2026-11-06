"""Smoke test MANUAL da moderacao de imagem local. NAO rode em CI.

Uso:
    python tools/smoke_moderation.py --folder C:/imagens

O usuario fornece as imagens; o script NAO gera, baixa ou executa modelos de
imagem. Ele carrega NSFW + CLIP locais, classifica uma imagem por vez e mostra
scores, tempo e RAM.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402

from infra.settings import get_settings  # noqa: E402
from modules.image_generation.adapters.image_moderation.local import (  # noqa: E402
    LocalImageModerator,
)
from modules.image_generation.application.ports.image_moderation import (  # noqa: E402
    ImageModerationThresholds,
)

_SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}


def _warning() -> None:
    print("=" * 72)
    print("SMOKE TEST MANUAL DA MODERACAO DE IMAGEM (modelos locais reais)")
    print("Feche programas pesados e monitore RAM/temperatura.")
    print("Uma imagem por vez; nenhuma imagem e gerada ou baixada.")
    print("=" * 72)


async def _run(folder: Path, limit: int) -> int:
    settings = get_settings()
    if settings.image_moderator != "local":
        print("Configure IMAGE_MODERATOR=local e os caminhos dos modelos.")
        return 2
    moderator = LocalImageModerator(
        nsfw_model_path=settings.image_nsfw_model_path,
        clip_model_path=settings.image_clip_model_path,
        thresholds=ImageModerationThresholds(
            sexual=settings.image_nsfw_threshold,
            gore=settings.image_gore_threshold,
            hate=settings.image_hate_threshold,
            self_harm=settings.image_self_harm_threshold,
        ),
    )
    images = sorted(
        path for path in folder.iterdir() if path.suffix.lower() in _SUPPORTED
    )[:limit]
    if not images:
        print(f"Nenhuma imagem suportada em {folder}.")
        return 1
    for index, path in enumerate(images, start=1):
        before = psutil.virtual_memory()
        started = time.perf_counter()
        result = await moderator.moderate(path.read_bytes())
        elapsed = time.perf_counter() - started
        after = psutil.virtual_memory()
        scores = result.scores
        print(
            f"[{index:02d}] {path.name} {elapsed:.2f}s "
            f"RAM_antes={before.available / (1024**2):.0f}MB "
            f"RAM_depois={after.available / (1024**2):.0f}MB"
        )
        print(
            f"     sexual={scores.sexual:.3f} gore={scores.gore:.3f} "
            f"hate={scores.hate:.3f} self_harm={scores.self_harm:.3f} "
            f"bloqueio={result.blocked_category.value if result.blocked_category else 'pass'}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke manual da moderacao visual")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    _warning()
    return asyncio.run(_run(Path(args.folder), max(1, args.limit)))


if __name__ == "__main__":
    raise SystemExit(main())
