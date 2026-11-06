"""Configuracao publica consumida pelo frontend (sem segredos)."""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import SettingsDep

router = APIRouter(prefix="/api/v1", tags=["config"])


@router.get("/config", include_in_schema=False)
async def public_config(settings: SettingsDep) -> dict:
    return {
        "image_generation_enabled": settings.image_generation_enabled,
        "upload_max_bytes": settings.edit_upload_max_bytes,
        "upload_max_dimension": settings.edit_upload_max_dimension,
        "upload_max_pixels": settings.edit_upload_max_pixels,
        "upscale_daily_limit": settings.upscale_daily_limit,
    }
