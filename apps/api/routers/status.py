"""Status publico da plataforma (sem detalhes internos)."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import EngineAvailabilityDep

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status")
async def get_status(availability: EngineAvailabilityDep) -> dict:
    return await availability.status()
