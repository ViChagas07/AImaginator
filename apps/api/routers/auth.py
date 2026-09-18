"""Rotas de autenticacao SSO (Google OIDC) — spec secao 15.

- /auth/google/login: redireciona para o Google (Authorization Code + PKCE).
- /auth/google/callback: troca o code, provisiona o usuario, emite os tokens
  da SESSAO PROPRIA e os devolve ao frontend no fragmento da URL (hash).
  Nenhum token do Google sai do backend.
- /auth/refresh, /auth/logout, /auth/me.

Sessao por token: o frontend guarda access/refresh em localStorage e envia
o access em `Authorization: Bearer` (sem cookies httpOnly cross-domain).
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from apps.api.dependencies import (
    CurrentUserDep,
    JWTDep,
    OIDCDep,
    SettingsDep,
    UserRepoDep,
    get_auth_rate_limiter,
)
from modules.auth.application.use_cases import (
    CompleteGoogleLogin,
    RefreshSession,
    StartGoogleLogin,
)
from modules.auth.contracts import LoginWithEmail, SignUpWithEmail
from modules.rate_limiting.token_bucket import TokenBucket

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RefreshInput(BaseModel):
    refresh_token: str


class SignupInput(BaseModel):
    name: str
    email: str
    password: str


class LoginInput(BaseModel):
    email: str
    password: str


def _tokens_dict(tokens) -> dict:
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "access_expires_at": int(tokens.access_expires_at.timestamp()),
        "refresh_expires_at": int(tokens.refresh_expires_at.timestamp()),
    }


@router.post("/signup")
async def signup(
    payload: SignupInput,
    users: UserRepoDep,
    jwt: JWTDep,
    limiter: TokenBucket = Depends(get_auth_rate_limiter),
) -> dict:
    await limiter.consume("auth:signup")
    tokens, user = await SignUpWithEmail(
        user_repository=users, jwt_service=jwt
    ).execute(name=payload.name, email=payload.email, password=payload.password)
    return {
        **_tokens_dict(tokens),
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
    }


@router.post("/login")
async def login(
    payload: LoginInput,
    users: UserRepoDep,
    jwt: JWTDep,
    limiter: TokenBucket = Depends(get_auth_rate_limiter),
) -> dict:
    await limiter.consume("auth:login:password")
    tokens, user = await LoginWithEmail(
        user_repository=users, jwt_service=jwt
    ).execute(email=payload.email, password=payload.password)
    return {
        **_tokens_dict(tokens),
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
    }


@router.get("/google/login", include_in_schema=False)
async def google_login(
    oidc: OIDCDep,
    limiter: TokenBucket = Depends(get_auth_rate_limiter),
) -> RedirectResponse:
    await limiter.consume("auth:login")
    url = await StartGoogleLogin(oidc).execute()
    return RedirectResponse(url, status_code=302)


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    oidc: OIDCDep,
    jwt: JWTDep,
    users: UserRepoDep,
    settings: SettingsDep,
    code: str = Query(...),
    state: str = Query(...),
    limiter: TokenBucket = Depends(get_auth_rate_limiter),
) -> RedirectResponse:
    await limiter.consume("auth:callback")
    tokens, _user = await CompleteGoogleLogin(
        oidc=oidc, jwt_service=jwt, user_repository=users
    ).execute(code=code, state=state)

    # Sessao por token: devolve access/refresh no fragmento da URL (o hash
    # nao vai ao servidor nem a logs). O frontend os persiste em localStorage
    # e os envia em `Authorization: Bearer`.
    fragment = urlencode(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "access_expires_at": int(tokens.access_expires_at.timestamp()),
            "refresh_expires_at": int(tokens.refresh_expires_at.timestamp()),
        }
    )
    return RedirectResponse(
        f"{settings.frontend_base_url}/pt-BR/auth/callback#{fragment}",
        status_code=302,
    )


@router.post("/refresh", include_in_schema=False)
async def refresh_session(payload: RefreshInput, jwt: JWTDep) -> dict:
    access, access_exp = await RefreshSession(jwt).execute(payload.refresh_token)
    return {"access_token": access, "access_expires_at": access_exp}


@router.post("/logout", include_in_schema=False)
async def logout() -> Response:
    # Sessao stateless por token: logout e apenas descartar os tokens no
    # cliente (o backend nao mantem estado de sessao).
    return Response(status_code=204)


@router.get("/me")
async def me(current_user: CurrentUserDep) -> dict:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "generation_credits": current_user.generation_credits,
    }
