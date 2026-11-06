"""Porta de storage de objetos (imagens geradas e origens de edicao)."""

from __future__ import annotations

from typing import Protocol


class ObjectStoragePort(Protocol):
    async def put_object(
        self, key: str, data: bytes, *, content_type: str = "image/png"
    ) -> None: ...

    async def get_object(self, key: str) -> bytes: ...

    async def presigned_get_url(
        self, key: str, *, expires_seconds: int | None = None
    ) -> str:
        """URL temporaria de leitura. Nunca devolve credenciais."""
        ...

    async def delete_object(self, key: str) -> None: ...

    async def ensure_bucket(self) -> None:
        """Cria o bucket quando o ambiente permite (desenvolvimento)."""
        ...

    async def delete_objects_older_than(self, prefix: str, *, hours: int) -> int:
        """Remove objetos com LastModified mais antigo que a retencao."""
        ...
