"""Tipos primitivos transversais (manter minimo)."""

from __future__ import annotations

from typing import NewType
from uuid import UUID

UserId = NewType("UserId", UUID)
GenerationId = NewType("GenerationId", UUID)
