"""Erros de dominio do storage de imagens."""

from __future__ import annotations

from shared_kernel.errors import DomainError


class StorageUnavailableError(DomainError):
    code = "storage_unavailable"
    http_status = 503

    def __init__(
        self, message: str = "Storage de imagens indisponivel no momento."
    ) -> None:
        super().__init__(message)
