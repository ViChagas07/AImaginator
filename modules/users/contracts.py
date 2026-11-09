"""Contrato publico do modulo users.

UNICA porta de entrada para outros modulos: ninguem importa de
users.domain/users.adapters diretamente — apenas daqui (regra de
acoplamento do monolito modular, spec secao 3.2).
"""

from __future__ import annotations

from modules.users.application.credits import CreditLedgerService
from modules.users.application.ports import (
    CreditLedgerRepositoryPort,
    UserRepositoryPort,
)
from modules.users.domain.entities import CreditLedgerEntry, User, UserSettings

__all__ = [
    "CreditLedgerEntry",
    "CreditLedgerRepositoryPort",
    "CreditLedgerService",
    "User",
    "UserSettings",
    "UserRepositoryPort",
]
