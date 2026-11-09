"""Verifica o manifesto C2PA de uma imagem (manual; nao roda em CI)."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        from c2pa import Reader
    except ImportError:
        print("c2pa-python ausente; instale o grupo 'provenance'.")
        return 2
    if not args.image.is_file():
        print("arquivo nao encontrado")
        return 2
    with args.image.open("rb") as handle, Reader(handle) as reader:
        manifest = reader.get_active_manifest()
        if not manifest:
            print("sem manifesto C2PA")
            return 1
        print(f"claim_generator={manifest.get('claim_generator')}")
        print(f"format={manifest.get('format')}")
        print(f"assertions={len(manifest.get('assertions') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
