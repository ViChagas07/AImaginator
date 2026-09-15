"""Rotas de autenticacao SSO (Google OIDC) — spec secao 15.

- /auth/google/login: redireciona para o Google (Authorization Code + PKCE).
- /auth/google/callback: troca o code, provisiona o usuario, grava os
  tokens da SESSAO PROPRIA em cookies httpOnly/Secure/SameSite=Lax e
  redireciona para o frontend. Nenhum token do Google sai do backend.
- /auth/refresh, /auth/logout, /auth/me.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from apps.api.dependencies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    CurrentUserDep,
    JWTDep,
    OIDCDep,
    SettingsDep,
    UserRepoDep,
    get_auth_rate_limiter,
)
from modules.auth.application.use_cases import (
    CompleteGoogleLogin,
    GetAuthenticatedUser,
    RefreshSession,
    StartGoogleLogin,
)
from modules.rate_limiting.token_bucket import TokenBucket
from modules.users.contracts import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _cookie_params(settings) -> dict:
    return {
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
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
    response: Response,
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

    redirect = RedirectResponse(f"{settings.frontend_base_url}/pt-BR/studio", status_code=302)
    redirect.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.jwt_access_token_ttl_seconds,
        **_cookie_params(settings),
    )
    redirect.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.jwt_refresh_token_ttl_seconds,
        **_cookie_params(settings),
    )
    return redirect


@router.post("/refresh", include_in_schema=False)
async def refresh_session(
    request: Request, response: Response, jwt: JWTDep, settings: SettingsDep
) -> Response:
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    access, _exp = await RefreshSession(jwt).execute(refresh_token)
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.jwt_access_token_ttl_seconds,
        **_cookie_params(settings),
    )
    response.status_code = 204
    return response


@router.post("/logout", include_in_schema=False)
async def logout(settings: SettingsDep) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return response


@router.get("/me")
async def me(current_user: CurrentUserDep) -> dict:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "generation_credits": current_user.generation_credits,
    }
