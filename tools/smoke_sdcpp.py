"""Smoke test MANUAL do sd-cli com FLUX/Kontext reais.

NUNCA execute este script em CI/testes: ele carrega o modelo real e pode
estressar a GPU. Rode manualmente, com o PC ventilado e monitorando
temperatura/energia (o PC de desenvolvimento ja desligou sob carga).

Exemplos:
    python tools/smoke_sdcpp.py
    python tools/smoke_sdcpp.py --edit --source entrada.png
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
from modules.image_generation.adapters.ai_agents.providers import (  # noqa: E402
    make_png_bytes,
)
from modules.image_generation.adapters.sdcpp import (  # noqa: E402
    SdCppImageEditor,
    SdCppImageGenerator,
)


def _print_ram(stage: str) -> None:
    memory = psutil.virtual_memory()
    print(
        f"[{stage}] RAM livre: {memory.available / (1024**2):.0f} MB "
        f"({memory.percent:.0f}% em uso)"
    )


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.image_engine != "sdcpp":
        print("IMAGE_ENGINE nao e 'sdcpp'. Configure o .env antes do smoke test.")
        return 2

    print("=" * 64)
    print("SMOKE TEST MANUAL - sd-cli real")
    print("Monitore a temperatura/energia. Interrompa em caso de throttle,")
    print("ruido anormal ou desligamento. Este teste NAO roda em CI.")
    print("=" * 64)
    stage_started = time.monotonic()
    _print_ram("etapa 1 - RAM antes")
    print(f"  etapa 1 concluida em {time.monotonic() - stage_started:.2f}s")

    width, height = 512, 512
    started = time.monotonic()

    async def on_progress(percent: int) -> None:
        print(f"  progresso: {percent:3d}%  (t={time.monotonic() - started:.1f}s)")

    try:
        if args.edit:
            if args.source:
                source = Path(args.source).read_bytes()
                print(f"Origem: {args.source} ({len(source)} bytes)")
            else:
                source = make_png_bytes(width, height)
                print("Origem: PNG 512x512 gerado pelo proprio script")
            editor = SdCppImageEditor(settings)
            engine_started = time.monotonic()
            result = await editor.edit(
                prompt=args.prompt,
                source_image=source,
                width=width,
                height=height,
                seed=args.seed,
                on_progress=on_progress,
            )
        else:
            generator = SdCppImageGenerator(settings)
            engine_started = time.monotonic()
            result = await generator.generate(
                prompt=args.prompt,
                width=width,
                height=height,
                seed=args.seed,
                on_progress=on_progress,
            )
        engine_seconds = time.monotonic() - engine_started
    except Exception as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        return 1

    write_started = time.monotonic()
    output = Path(args.output)
    output.write_bytes(result.image_bytes)
    write_seconds = time.monotonic() - write_started
    total_seconds = time.monotonic() - started
    print("-" * 64)
    print(f"Etapa 2 - sd-cli: {engine_seconds:.1f}s")
    print(f"Etapa 3 - escrita do arquivo: {write_seconds:.2f}s")
    print(f"Total: {total_seconds:.1f}s")
    print(f"Seed: {result.seed}")
    print(f"Dimensoes: {result.width}x{result.height}")
    print(f"Arquivo: {output.resolve()}")
    _print_ram("depois")
    print("Verifique a temperatura da CPU/GPU antes de repetir o teste.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test manual do sd-cli real")
    parser.add_argument(
        "--prompt",
        default="a cozy wooden cabin in a snowy forest at dusk, warm light in the windows",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--edit", action="store_true", help="testa o Kontext")
    parser.add_argument("--source", default=None, help="imagem de origem para --edit")
    parser.add_argument("--output", default="smoke-output.png")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
