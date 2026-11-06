"""Executavel FALSO que imita o sd-cli (nunca carrega modelo real).

Escreve um PNG pequeno valido na saida -o e imprime barras de progresso no
formato do stable-diffusion.cpp. Comportamentos especiais via prompt:
  - "timeout": dorme 30 s (para testar kill da arvore)
  - "oom": imprime erro de alocacao e sai com codigo 1
  - "fail": imprime erro e sai com codigo 2
  - "no-output": sai com 0 sem criar arquivo
"""

from __future__ import annotations

import struct
import sys
import time
import zlib
from pathlib import Path


def _png(width: int, height: int) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height, level=1))
        + chunk(b"IEND", b"")
    )


def _arg(name: str, default: str | None = None) -> str | None:
    if name not in sys.argv:
        return default
    return sys.argv[sys.argv.index(name) + 1]


def _read_png_size(path: str) -> tuple[int, int]:
    data = Path(path).read_bytes()
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit(f"input nao e PNG: {path}")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def main() -> int:
    import json
    import os

    args_log = os.environ.get("FAKE_SDCLI_ARGS_PATH")
    if args_log:
        Path(args_log).write_text(
            json.dumps(sys.argv[1:], ensure_ascii=False), encoding="utf-8"
        )

    if "--upscale-model" in sys.argv:
        model = _arg("--upscale-model", "") or ""
        if "timeout" in model:
            print("upscaling...", flush=True)
            time.sleep(30)
            return 0
        input_path = _arg("-i")
        output = _arg("-o")
        if not input_path or not output:
            print("missing -i/-o", flush=True)
            return 2
        width, height = _read_png_size(input_path)
        Path(output).write_bytes(_png(width * 2, height * 2))
        return 0

    prompt = _arg("-p", "") or ""
    output = _arg("-o")
    width = int(_arg("-W", "512") or 512)
    height = int(_arg("-H", "512") or 512)
    steps = int(_arg("--steps", "8") or 8)

    if prompt == "timeout":
        print("| 1/8 - 19.5s/it", flush=True)
        time.sleep(30)
        return 0
    if prompt == "oom":
        print("ggml_backend_alloc: failed to allocate buffer", flush=True)
        return 1
    if prompt == "fail":
        print("error: something went wrong", flush=True)
        return 2
    if prompt == "no-output":
        return 0

    for step in range(1, steps + 1):
        seconds = 25.0 if step == 1 else 19.5
        print(f"| {step}/{steps} - {seconds:.1f}s/it", flush=True)
        print(f"  |=====> | {step}/{steps} - {seconds:.1f}s/it", flush=True)
    if output is not None:
        Path(output).write_bytes(_png(width, height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
