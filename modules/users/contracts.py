"""Contrato publico do modulo users.

UNICA porta de entrada para outros modulos: ninguem importa de
users.domain/users.adapters diretamente — apenas daqui (regra de
acoplamento do monolito modular, spec secao 3.2).
"""

from __future__ import annotations

from modules.users.application.ports import UserRepositoryPort
from modules.users.domain.entities import User, UserSettings

__all__ = ["User", "UserSettings", "UserRepositoryPort"]
