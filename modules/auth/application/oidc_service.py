"""Servico OIDC do Google: Authorization Code + PKCE.

Decisoes de seguranca:
- state + code_verifier ficam no Redis (TTL 10 min), nunca em cookie
  legivel — vincula o callback ao login que o iniciou (anti-CSRF).
- id_token validado contra o JWKS oficial do Google (assinatura, iss,
  aud, exp) antes de qualquer dado ser confiado.
- Chamadas externas passam pelo Circuit Breaker (dependencia instavel).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError

from modules.auth.application.pkce import code_challenge_s256, generate_code_verifier, generate_state
from modules.auth.domain.entities import GoogleProfile
from shared_kernel.errors import UnauthorizedError

_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_STATE_TTL_SECONDS = 600


class GoogleOIDCService:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        redis_client: Any,
        http_client: httpx.AsyncClient,
        circuit_breaker: Any,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._redis = redis_client
        self._http = http_client
        self._cb = circuit_breaker

    async def build_authorization_url(self) -> str:
        """Monta a URL de login do Google e persiste state+verifier."""
        state = generate_state()
        verifier = generate_code_verifier()
        await self._redis.set(f"oidc:state:{state}", verifier, ex=_STATE_TTL_SECONDS)
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge_s256(verifier),
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return f"{_AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange_code(self, *, code: str, state: str) -> GoogleProfile:
        """Troca o code por tokens, valida o id_token e devolve o perfil."""
        verifier = await self._redis.getdel(f"oidc:state:{state}")
        if not verifier:
            raise UnauthorizedError("State de login invalido ou expirado.")

        token_payload = await self._cb.call(
            lambda: self._post_token(code=code, verifier=verifier)
        )
        id_token = token_payload.get("id_token")
        if not id_token:
            raise UnauthorizedError("Resposta do Google sem id_token.")
        return await self._validate_id_token(id_token)

    async def _post_token(self, *, code: str, verifier: str) -> dict[str, Any]:
        response = await self._http.post(
            _TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code_verifier": verifier,
            },
            timeout=10,
        )
        if response.status_code != 200:
            raise UnauthorizedError("Falha na troca do codigo de autorizacao.")
        return response.json()

    async def _validate_id_token(self, id_token: str) -> GoogleProfile:
        jwks = await self._cb.call(self._fetch_jwks)
        try:
            key_set = JsonWebKey.import_key_set(jwks)
            claims = JsonWebToken(["RS256"]).decode(id_token, key_set)
            claims.validate()
        except JoseError as exc:
            raise UnauthorizedError("id_token do Google invalido.") from exc
        if claims.get("iss") not in _GOOGLE_ISSUERS:
            raise UnauthorizedError("Issuer inesperado no id_token.")
        if claims.get("aud") != self._client_id:
            raise UnauthorizedError("Audience inesperada no id_token.")
        if not claims.get("email"):
            raise UnauthorizedError("Perfil do Google sem e-mail verificado.")
        return GoogleProfile(
            sub=str(claims["sub"]),
            email=str(claims["email"]),
            name=str(claims.get("name") or claims["email"]),
            picture=claims.get("picture"),
        )

    async def _fetch_jwks(self) -> dict:
        cache_key = "oidc:google:jwks"
        cached = await self._redis.get(cache_key)
        if cached:
            return json.loads(cached)
        response = await self._http.get(_JWKS_URI, timeout=10)
        response.raise_for_status()
        jwks = response.json()
        await self._redis.set(cache_key, json.dumps(jwks), ex=3600)
        return jwks
