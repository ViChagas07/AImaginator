"""Console administrativo: moderacao, creditos, workers e manutencao."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    AdminServiceDep,
    AdminUserDep,
    EngineAvailabilityDep,
    RedisDep,
    SettingsDep,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class BlockUserInput(BaseModel):
    minutes: int = Field(default=60, ge=1, le=60 * 24 * 30)


class CreditsInput(BaseModel):
    delta: int = Field(ge=-10_000, le=10_000)
    reason: str = Field(min_length=1, max_length=80)


class MaintenanceInput(BaseModel):
    enabled: bool


@router.get("/users/flagged")
async def flagged_users(admin: AdminUserDep, service: AdminServiceDep) -> list[dict]:
    return await service.list_flagged_users()


@router.get("/moderation/stats")
async def moderation_stats(
    admin: AdminUserDep, service: AdminServiceDep, days: int = 7
) -> list[dict]:
    return await service.moderation_stats(days=days)


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: UUID,
    data: BlockUserInput,
    admin: AdminUserDep,
    service: AdminServiceDep,
) -> dict:
    return await service.block_user(actor=admin, user_id=user_id, minutes=data.minutes)


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: UUID, admin: AdminUserDep, service: AdminServiceDep) -> dict:
    return await service.unblock_user(actor=admin, user_id=user_id)


@router.post("/users/{user_id}/credits")
async def adjust_credits(
    user_id: UUID,
    data: CreditsInput,
    admin: AdminUserDep,
    service: AdminServiceDep,
) -> dict:
    return await service.adjust_credits(
        actor=admin, user_id=user_id, delta=data.delta, reason=data.reason
    )


@router.get("/audit")
async def audit_log(admin: AdminUserDep, service: AdminServiceDep, days: int = 7) -> list[dict]:
    return await service.list_audit(days=days)


@router.get("/workers")
async def workers(admin: AdminUserDep, availability: EngineAvailabilityDep) -> list[dict]:
    result = []
    for worker in await availability.workers():
        result.append(
            {
                "id": worker.get("id"),
                "capabilities": worker.get("capabilities", []),
                "engine": worker.get("engine"),
                "state": worker.get("state"),
                "last_seen": worker.get("last_seen"),
            }
        )
    return result


@router.post("/maintenance")
async def maintenance(
    data: MaintenanceInput,
    admin: AdminUserDep,
    service: AdminServiceDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> dict:
    await redis.set(settings.maintenance_redis_key, "1" if data.enabled else "0")
    await service.record(
        actor=admin,
        action="maintenance.toggle",
        target_type="system",
        target_id="maintenance",
        result="ok",
        detail={"enabled": data.enabled},
    )
    return {"maintenance": data.enabled}


@router.get("/reports")
async def reports_queue(admin: AdminUserDep, service: AdminServiceDep) -> list[dict]:
    return await service.reports_queue()
