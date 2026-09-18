"""Contrato publico do modulo auth."""

from __future__ import annotations

from modules.auth.application.jwt_service import JWTService
from modules.auth.application.oidc_service import GoogleOIDCService
from modules.auth.application.password_use_cases import LoginWithEmail, SignUpWithEmail
from modules.auth.application.use_cases import (
    CompleteGoogleLogin,
    GetAuthenticatedUser,
    RefreshSession,
    StartGoogleLogin,
)
from modules.auth.domain.entities import AuthenticatedUser, GoogleProfile, SessionTokens

__all__ = [
    "AuthenticatedUser",
    "CompleteGoogleLogin",
    "GetAuthenticatedUser",
    "GoogleOIDCService",
    "GoogleProfile",
    "JWTService",
    "LoginWithEmail",
    "RefreshSession",
    "SessionTokens",
    "SignUpWithEmail",
    "StartGoogleLogin",
]
