"""Servico de emissao/verificacao de JWT proprios da aplicacao.

Os tokens da sessao sao JWT HS256 assinados com a SECRET_KEY da app.
Nada de token do Google no frontend: o access/refresh da aplicacao
viajam em cookies httpOnly, Secure, SameSite=Lax (spec secao 15).
"""

from __future__ import annotations

import time
from uuid import UUID

from authlib.jose import JsonWebToken
from authlib.jose.errors import JoseError

from shared_kernel.errors import UnauthorizedError


class JWTService:
    def __init__(self, *, secret_key: str, algorithm: str, access_ttl: int, refresh_ttl: int) -> None:
        self._jwt = JsonWebToken([algorithm])
        self._secret = secret_key
        self._algorithm = algorithm
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def issue_access_token(self, user_id: UUID) -> tuple[str, int]:
        return self._issue(user_id, self._access_ttl, token_type="access")

    def issue_refresh_token(self, user_id: UUID) -> tuple[str, int]:
        return self._issue(user_id, self._refresh_ttl, token_type="refresh")

    def verify_access_token(self, token: str) -> UUID:
        return self._verify(token, expected_type="access")

    def verify_refresh_token(self, token: str) -> UUID:
        return self._verify(token, expected_type="refresh")

    def _issue(self, user_id: UUID, ttl: int, *, token_type: str) -> tuple[str, int]:
        now = int(time.time())
        exp = now + ttl
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": exp,
            "typ": token_type,
        }
        token = self._jwt.encode({"alg": self._algorithm}, payload, self._secret)
        return token.decode("ascii"), exp

    def _verify(self, token: str, *, expected_type: str) -> UUID:
        try:
            claims = self._jwt.decode(token, self._secret)
            claims.validate()
        except JoseError as exc:
            raise UnauthorizedError("Token invalido ou expirado.") from exc
        if claims.get("typ") != expected_type:
            raise UnauthorizedError("Tipo de token inesperado.")
        try:
            return UUID(claims["sub"])
        except (KeyError, ValueError) as exc:
            raise UnauthorizedError("Token malformado.") from exc
