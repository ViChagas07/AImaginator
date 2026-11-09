"""Servicos admin: autorizacao, auditoria e ausencia de dados sensiveis."""

from __future__ import annotations

import pytest

from modules.admin.application.service import AdminService, ensure_admin
from modules.users.application.credits import CreditLedgerService
from modules.users.domain.entities import CreditLedgerEntry, User
from shared_kernel.errors import ForbiddenError


class _Audit:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def add(self, **kwargs):
        self.rows.append(kwargs)

    async def list_since(self, since, *, limit=100):
        return self.rows[-limit:]


class _Moderation:
    async def aggregate_since(self, *, since):
        return [{"day": "2026-01-01", "category": "nsfw", "layer": "text", "count": 2}]


class _Ledger:
    def __init__(self) -> None:
        self.entries: list[CreditLedgerEntry] = []

    async def get_by_idempotency_key(self, key):
        return next((e for e in self.entries if e.idempotency_key == key), None)

    async def add(self, entry):
        self.entries.append(entry)
        return entry


class _Users:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_by_id(self, user_id):
        return self.user

    async def get_by_id_for_update(self, user_id):
        return self.user

    async def save(self, user):
        self.user = user
        return user

    async def list_flagged(self, *, limit=100):
        return [self.user] if self.user.moderation_flag else []


def _service(user: User):
    users = _Users(user)
    ledger = _Ledger()
    credits = CreditLedgerService(users=users, ledger=ledger, monthly_credits=lambda plan: 50)
    audit = _Audit()
    return (
        AdminService(users=users, audit=audit, moderation=_Moderation(), credits=credits),
        audit,
        ledger,
    )


@pytest.mark.unit
async def test_usuario_comum_nao_e_admin() -> None:
    with pytest.raises(ForbiddenError):
        ensure_admin(User(email="a@example.com", name="A", role="user"))
    ensure_admin(User(email="a@example.com", name="A", role="admin"))


@pytest.mark.unit
async def test_lista_sinalizados_nao_expoe_email() -> None:
    user = User(email="segredo@example.com", name="A", moderation_flag=True)
    service, _, _ = _service(user)
    rows = await service.list_flagged_users()
    assert rows[0]["id"] == str(user.id)
    assert "email" not in rows[0]
    assert "segredo" not in str(rows)


@pytest.mark.unit
async def test_block_e_unblock_auditam() -> None:
    user = User(email="a@example.com", name="A")
    admin = User(email="admin@example.com", name="Admin", role="admin")
    service, audit, _ = _service(user)
    blocked = await service.block_user(actor=admin, user_id=user.id, minutes=30)
    assert blocked["blocked_until"]
    assert user.moderation_flag is True
    await service.unblock_user(actor=admin, user_id=user.id)
    assert user.moderation_flag is False
    assert [row["action"] for row in audit.rows] == ["user.block", "user.unblock"]


@pytest.mark.unit
async def test_ajuste_de_creditos_usa_ledger_e_auditoria() -> None:
    user = User(email="a@example.com", name="A", generation_credits=10)
    admin = User(email="admin@example.com", name="Admin", role="admin")
    service, audit, ledger = _service(user)
    result = await service.adjust_credits(actor=admin, user_id=user.id, delta=5, reason="suporte")
    assert result["generation_credits"] == 15
    assert ledger.entries[0].reason == "admin_adjust"
    assert audit.rows[-1]["action"] == "credits.adjust"
