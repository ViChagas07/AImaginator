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
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("ENV_FILE", ".env"),
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
    # Origens extras permitidas no CORS, separadas por virgula.
    # frontend_base_url e sempre incluida; este campo adiciona origens.
    frontend_origins: str = ""
    # Aplica migrations pendentes (alembic upgrade head) no boot da API.
    # Desative em ambientes de teste/CI (AUTO_MIGRATE=false).
    auto_migrate: bool = True
    # Protecao da producao: desligado por padrao quando APP_ENV=production.
    # None significa "derivar do ambiente".
    feature_image_generation_enabled: bool | None = None

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
    # Se vazio, a redirect_uri e derivada de api_base_url
    # (f"{api_base_url}/api/v1/auth/google/callback").
    google_oauth_redirect_uri: str = ""

    # ---- JWT ----
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_seconds: int = 900
    jwt_refresh_token_ttl_seconds: int = 2_592_000

    # ---- Provedor de IA ----
    # IMAGE_ENGINE e o switch do runtime local (stub | sdcpp).
    # AI_IMAGE_PROVIDER permanece como legado do provedor HTTP externo.
    image_engine: Literal["stub", "sdcpp"] = "stub"
    sdcpp_binary_path: str = ""
    sdcpp_vae_path: str = ""
    sdcpp_clip_l_path: str = ""
    sdcpp_t5xxl_path: str = ""
    sdcpp_gen_model_path: str = ""
    sdcpp_edit_model_path: str = ""

    ai_image_provider: str = "stub"
    ai_image_api_key: str = ""
    ai_image_api_base_url: str = ""

    # ---- Parametros medidos do FLUX (Fase 1) ----
    gen_width: int = Field(default=512, ge=64, le=4096)
    gen_height: int = Field(default=512, ge=64, le=4096)
    gen_steps: int = Field(default=8, ge=1, le=150)
    gen_guidance: float = Field(default=3.5, ge=0.0, le=30.0)
    edit_width: int = Field(default=512, ge=64, le=4096)
    edit_height: int = Field(default=512, ge=64, le=4096)
    edit_steps: int = Field(default=8, ge=1, le=150)
    edit_guidance: float = Field(default=3.5, ge=0.0, le=30.0)

    # ---- Timeouts, recursos e upload de edicao ----
    generation_timeout_seconds: int = Field(default=300, gt=0)
    edit_timeout_seconds: int = Field(default=600, gt=0)
    edit_upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    edit_upload_max_dimension: int = Field(default=8192, gt=0)
    edit_upload_max_pixels: int = Field(default=40_000_000, gt=0)
    # Guarda de recursos antes de iniciar o sd-cli.
    min_free_ram_mb: int = Field(default=6000, ge=0)
    # Pausa apos cada job de imagem (protecao termica/energia); 0 desativa.
    cooldown_seconds_between_jobs: float = Field(default=0.0, ge=0.0)

    # ---- Storage S3/MinIO ----
    # Credenciais AWS padrao aceitas como fallback das S3_*.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_endpoint_url: str = ""
    # Endpoint usado nas URLs assinadas (ex.: localhost:9002); vazio usa o interno.
    s3_public_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    s3_presign_expires_seconds: int = Field(default=900, gt=0)
    s3_source_retention_hours: int = Field(default=24, ge=1)

    # ---- Assistente de prompts (LLM local, OpenAI-compatible) ----
    prompt_max_chars: int = Field(default=1000, ge=1, le=2000)
    llm_base_url: str = "http://localhost:1235/v1"
    llm_model: str = "qwen/qwen3.5-9b"
    llm_api_key: str = Field(default="lm-studio", min_length=1)
    llm_timeout_seconds: float = Field(default=90.0, gt=0)
    llm_max_output_tokens: int = Field(default=400, gt=0)
    llm_ttl_seconds: int = Field(default=60, ge=0)
    # Confianca minima para aceitar uma categoria moderada como bloqueio.
    llm_block_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # ---- Classificador de topico legado (nao usado no fluxo principal) ----
    # "stub" (default, sem LLM) | "http" (OpenAI Chat Completions) | "gemini" (API nativa do Gemini)
    topic_classifier_provider: str = "stub"
    topic_classifier_api_key: str = ""
    topic_classifier_api_base_url: str = ""
    topic_classifier_model: str = "gemini-1.5-flash"
    topic_classifier_timeout_seconds: float = 4.0

    # ---- Moderacao e penalidades ----
    moderation_store_prompt_text: bool = False
    mod_warn_at: int = Field(default=3, ge=1)
    mod_block_at: int = Field(default=5, ge=1)
    mod_block_minutes: int = Field(default=60, ge=1)
    mod_review_at: int = Field(default=10, ge=1)
    mod_review_block_hours: int = Field(default=24, ge=1)
    moderation_window_hours: int = Field(default=24, ge=1)

    # ---- Moderacao de imagem (saida gerada e origem de edicao) ----
    image_moderation_enabled: bool = True
    image_moderator: Literal["fake", "local"] = "fake"
    image_nsfw_model_path: str = ""
    image_clip_model_path: str = ""
    image_nsfw_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    image_gore_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    image_hate_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    image_self_harm_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # ---- Marca d'agua ----
    watermark_logo_path: str = (
        "modules/image_generation/assets/AImaginator_pic_transparent.png"
    )
    watermark_width_ratio: float = Field(default=0.20, gt=0.0, lt=1.0)
    watermark_min_width_px: int = Field(default=96, ge=1)
    watermark_margin_ratio: float = Field(default=0.025, ge=0.0, lt=0.5)
    watermark_opacity: float = Field(default=0.9, gt=0.0, le=1.0)
    watermark_shadow: bool = True

    # ---- Metadados de IA / C2PA opcional ----
    c2pa_enabled: bool = False
    c2pa_cert_path: str = ""
    c2pa_key_path: str = ""

    # ---- Upscale ----
    upscale_engine: Literal["lanczos", "esrgan"] = "lanczos"
    sdcpp_upscale_model_path: str = ""
    upscale_timeout_seconds: int = Field(default=300, gt=0)
    upscale_daily_limit: int = Field(default=5, ge=1)

    # ---- Observabilidade ----
    sentry_dsn_backend: str = ""
    sentry_environment: str = "development"
    # Modo multiprocesso do prometheus_client (worker recicla a cada task).
    prometheus_multiproc_dir: str = ""
    worker_metrics_port: int = Field(default=9100, ge=1, le=65535)
    worker_metrics_interval_seconds: float = Field(default=10.0, gt=0)
    stream_ticket_ttl_seconds: int = Field(default=60, ge=1, le=300)

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

    @field_validator("api_base_url", "frontend_base_url")
    @classmethod
    def _normalize_public_url(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @property
    def image_generation_enabled(self) -> bool:
        return self.feature_image_generation_enabled is True

    @model_validator(mode="after")
    def _resolve_feature_flag(self) -> Settings:
        if self.feature_image_generation_enabled is None:
            self.feature_image_generation_enabled = self.app_env != "production"
        return self

    @model_validator(mode="after")
    def _validate_moderation_thresholds(self) -> Settings:
        if not (self.mod_warn_at <= self.mod_block_at <= self.mod_review_at):
            msg = "MOD_WARN_AT <= MOD_BLOCK_AT <= MOD_REVIEW_AT e obrigatorio."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_watermark_asset(self) -> Settings:
        if not self.image_generation_enabled:
            return self
        import struct
        from pathlib import Path

        path = Path(self.watermark_logo_path)
        if not path.is_file():
            msg = f"WATERMARK_LOGO_PATH nao existe: {self.watermark_logo_path}."
            raise ValueError(msg)
        data = path.read_bytes()[:33]
        if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            msg = "WATERMARK_LOGO_PATH deve ser um PNG valido."
            raise ValueError(msg)
        width, height = struct.unpack(">II", data[16:24])
        color_type = data[25]
        if width < 1 or height < 1 or color_type not in (4, 6):
            msg = "WATERMARK_LOGO_PATH deve ser PNG com canal alfa."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_image_moderation_paths(self) -> Settings:
        if not self.image_generation_enabled:
            return self
        if self.image_moderation_enabled and self.image_moderator == "local":
            missing = [
                name
                for name, value in {
                    "IMAGE_NSFW_MODEL_PATH": self.image_nsfw_model_path,
                    "IMAGE_CLIP_MODEL_PATH": self.image_clip_model_path,
                }.items()
                if not value.strip()
            ]
            if missing:
                msg = f"IMAGE_MODERATOR=local exige: {', '.join(missing)}."
                raise ValueError(msg)
        if self.upscale_engine == "esrgan" and not self.sdcpp_upscale_model_path.strip():
            msg = "UPSCALE_ENGINE=esrgan exige SDCPP_UPSCALE_MODEL_PATH."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_sdcpp_paths(self) -> Settings:
        if not self.image_generation_enabled or self.image_engine != "sdcpp":
            return self
        required = {
            "SDCPP_BINARY_PATH": self.sdcpp_binary_path,
            "SDCPP_VAE_PATH": self.sdcpp_vae_path,
            "SDCPP_CLIP_L_PATH": self.sdcpp_clip_l_path,
            "SDCPP_T5XXL_PATH": self.sdcpp_t5xxl_path,
            "SDCPP_GEN_MODEL_PATH": self.sdcpp_gen_model_path,
            "SDCPP_EDIT_MODEL_PATH": self.sdcpp_edit_model_path,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            msg = f"IMAGE_ENGINE=sdcpp exige os caminhos: {', '.join(missing)}."
            raise ValueError(msg)

        access_key = self.s3_access_key.strip() or self.aws_access_key_id.strip()
        secret_key = self.s3_secret_key.strip() or self.aws_secret_access_key.strip()
        # S3_ENDPOINT_URL e opcional: vazio usa o endpoint padrao da AWS.
        missing_storage = [
            name
            for name, value in {
                "S3_BUCKET": self.s3_bucket,
                "S3_ACCESS_KEY (ou AWS_ACCESS_KEY_ID)": access_key,
                "S3_SECRET_KEY (ou AWS_SECRET_ACCESS_KEY)": secret_key,
            }.items()
            if not value.strip()
        ]
        if missing_storage:
            msg = (
                "IMAGE_ENGINE=sdcpp exige o storage S3: "
                f"{', '.join(missing_storage)}."
            )
            raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def allowed_image_domains(self) -> frozenset[str]:
        """Allowlist de dominios para fetch de imagens por URL (anti-SSRF)."""
        return frozenset(
            d.strip().lower() for d in self.allowed_image_url_domains.split(",") if d.strip()
        )

    @property
    def allowed_frontend_origins(self) -> list[str]:
        """Origens de CORS: FRONTEND_BASE_URL + extras de FRONTEND_ORIGINS."""
        raw = ",".join(filter(None, (self.frontend_base_url, self.frontend_origins)))
        origins: list[str] = []
        for item in raw.split(","):
            origin = item.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins


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
