"""Configuracao centralizada do AImaginator.

REGRA DE OURO (spec secao 8):
- Este e o UNICO modulo do projeto autorizado a ler variaveis de ambiente.
- Nenhum outro arquivo chama os.getenv() diretamente; todos importam daqui.
- pydantic-settings le o .env e valida tipos na subida da aplicacao
  (fail-fast: se faltar variavel obrigatoria, a app nem sobe).
- NUNCA logar valores de campos marcados como sensiveis.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    app_env: str = "development"
    app_name: str = "AImaginator"
    secret_key: str = Field(min_length=32)
    api_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"

    # ---- PostgreSQL ----
    postgres_user: str = "aimaginator"
    postgres_password: str = "aimaginator"
    postgres_db: str = "aimaginator"
    database_url: str

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- RabbitMQ / Celery ----
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672//"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ---- Google OAuth 2.0 / OIDC ----
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ---- JWT ----
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_seconds: int = 900
    jwt_refresh_token_ttl_seconds: int = 2_592_000

    # ---- Provedor de IA ----
    ai_image_provider: str = "stub"
    ai_image_api_key: str = ""
    ai_image_api_base_url: str = ""

    # ---- Observabilidade ----
    sentry_dsn_backend: str = ""
    sentry_environment: str = "development"

    # ---- Cota de prompts (janela deslizante de 24h, spec Bloco 1) ----
    anonymous_prompt_chances_per_day: int = 1
    authenticated_prompt_chances_per_day: int = 3
    anonymous_session_cookie_name: str = "aimaginator_anon"
    anonymous_session_max_age_days: int = 7

    # ---- Rate limiting / resiliencia ----
    rate_limit_generation_per_minute: int = 10
    rate_limit_auth_per_minute: int = 5
    rate_limit_prompt_quota_per_minute: int = 20
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: int = 30

    # ---- SSRF / storage ----
    allowed_image_url_domains: str = ""
    storage_bucket_url: str = ""

    @field_validator("secret_key")
    @classmethod
    def _secret_key_not_default(cls, v: str) -> str:
        if v.startswith("CHANGE_ME"):
            msg = "SECRET_KEY nao configurada. Defina no .env (ver .env.example)."
            raise ValueError(msg)
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def allowed_image_domains(self) -> frozenset[str]:
        """Allowlist de dominios para fetch de imagens por URL (anti-SSRF)."""
        return frozenset(
            d.strip().lower() for d in self.allowed_image_url_domains.split(",") if d.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Singleton de settings (cacheado). Unica funcao que le o ambiente."""
    return Settings()  # type: ignore[call-arg]  # pydantic-settings le do ambiente


def get_secret(name: str, default: str = "") -> str:
    """Acesso pontual a um segredo pelo nome — uso restrito a wiring de DI.

    Existe para casos dinamicos que nao cabem no schema estatico do Settings.
    NUNCA logar o retorno desta funcao.
    """
    return os.getenv(name, default)
