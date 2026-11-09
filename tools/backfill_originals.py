"""Backfill manual de originais privados.

Uso:
    poetry run python tools/backfill_originals.py --dry-run
    poetry run python tools/backfill_originals.py --apply --limit 200
"""

from __future__ import annotations

import argparse
import asyncio

from infra.database import session_scope
from infra.settings import get_settings
from modules.image_generation.adapters.repositories.generation_repository import (
    SQLAlchemyGenerationRepository,
)
from modules.image_generation.application.services.backfill import (
    BackfillOriginalsService,
)
from modules.image_generation.infra.wiring import build_object_storage_required


async def _run(*, apply: bool, limit: int) -> dict:
    settings = get_settings()
    storage = build_object_storage_required(settings)
    async with session_scope() as session:
        service = BackfillOriginalsService(
            generations=SQLAlchemyGenerationRepository(session),
            storage=storage,
            apply=apply,
        )
        return await service.run(limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    apply = bool(args.apply and not args.dry_run)
    report = asyncio.run(_run(apply=apply, limit=max(1, args.limit)))
    print(
        f"dry_run={report['dry_run']} copied={report['copied']} "
        f"unavailable={report['unavailable']} skipped={report['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
