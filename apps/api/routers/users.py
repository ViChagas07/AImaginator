"""Rotas de perfil e configuracoes do usuario."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from apps.api.dependencies import CurrentUserDep, UserRepoDep
from modules.users.contracts import User, UserRepositoryPort, UserSettings

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ===== Schemas =====


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None
    bio: str | None
    handle: str | None
    generation_credits: int
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, user: User) -> UserProfileResponse:
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            bio=user.bio,
            handle=user.handle,
            generation_credits=user.generation_credits,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )


class UpdateProfileInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = Field(default=None, max_length=160)
    handle: str | None = Field(
        default=None, min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )

    @field_validator("handle")
    @classmethod
    def handle_lowercase(cls, v: str | None) -> str | None:
        return v.lower() if v else None


class UserSettingsResponse(BaseModel):
    user_id: str
    # Aparência
    theme: str
    bold_text: bool
    font_size: str
    element_spacing: str
    # Idioma e Região
    locale: str
    timezone: str
    # Acessibilidade
    high_contrast: bool
    screen_reader_optimized: bool
    keyboard_navigation: bool
    focus_indicator: bool
    dyslexia_font: bool
    reduced_motion: bool
    # Notificações
    email_notifications: bool
    push_notifications: bool
    desktop_notifications: bool
    sound_notifications: bool
    summary_frequency: str
    notification_email: str | None
    # Privacidade
    privacy_policy_version: str | None
    terms_version: str | None
    consented_at: str | None
    # Avançado
    developer_mode: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, settings: UserSettings) -> UserSettingsResponse:
        return cls(
            user_id=str(settings.user_id),
            theme=settings.theme,
            bold_text=settings.bold_text,
            font_size=settings.font_size,
            element_spacing=settings.element_spacing,
            locale=settings.locale,
            timezone=settings.timezone,
            high_contrast=settings.high_contrast,
            screen_reader_optimized=settings.screen_reader_optimized,
            keyboard_navigation=settings.keyboard_navigation,
            focus_indicator=settings.focus_indicator,
            dyslexia_font=settings.dyslexia_font,
            reduced_motion=settings.reduced_motion,
            email_notifications=settings.email_notifications,
            push_notifications=settings.push_notifications,
            desktop_notifications=settings.desktop_notifications,
            sound_notifications=settings.sound_notifications,
            summary_frequency=settings.summary_frequency,
            notification_email=settings.notification_email,
            privacy_policy_version=settings.privacy_policy_version,
            terms_version=settings.terms_version,
            consented_at=settings.consented_at.isoformat() if settings.consented_at else None,
            developer_mode=settings.developer_mode,
            created_at=settings.created_at.isoformat(),
            updated_at=settings.updated_at.isoformat(),
        )


class UpdateSettingsInput(BaseModel):
    # Aparência
    theme: str | None = Field(default=None, pattern=r"^(dark|light|system)$")
    bold_text: bool | None = None
    font_size: str | None = Field(default=None, pattern=r"^(small|medium|large|xl)$")
    element_spacing: str | None = Field(default=None, pattern=r"^(compact|comfortable|spacious)$")
    # Idioma e Região
    locale: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    # Acessibilidade
    high_contrast: bool | None = None
    screen_reader_optimized: bool | None = None
    keyboard_navigation: bool | None = None
    focus_indicator: bool | None = None
    dyslexia_font: bool | None = None
    reduced_motion: bool | None = None
    # Notificações
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    desktop_notifications: bool | None = None
    sound_notifications: bool | None = None
    summary_frequency: str | None = Field(default=None, pattern=r"^(daily|weekly|never)$")
    notification_email: str | None = None
    # Privacidade
    privacy_policy_version: str | None = None
    terms_version: str | None = None
    consented_at: str | None = None
    # Avançado
    developer_mode: bool | None = None


class AvatarUploadResponse(BaseModel):
    avatar_url: str


class StatsResponse(BaseModel):
    account_created_at: str
    total_generations: int
    total_saved_arts: int
    current_tier: str
    credits_used_this_period: int
    credits_limit: int


class ConnectedProvider(BaseModel):
    name: str
    connected: bool
    email: str | None = None


class ConnectedProvidersResponse(BaseModel):
    providers: list[ConnectedProvider]


class ExportRequestResponse(BaseModel):
    message: str


class DeleteRequestResponse(BaseModel):
    message: str
    grace_period_days: int


# ===== Helpers =====


async def _get_or_create_settings(user_id: UUID, users: UserRepositoryPort) -> UserSettings:
    settings = await users.get_settings(user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        settings = await users.save_settings(settings)
    return settings


# ===== Routes =====


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: CurrentUserDep) -> UserProfileResponse:
    """Obtem o perfil do usuario autenticado."""
    return UserProfileResponse.from_entity(current_user)


@router.put("/me", response_model=UserProfileResponse)
async def update_profile(
    payload: UpdateProfileInput,
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> UserProfileResponse:
    """Atualiza o perfil do usuario autenticado."""
    user = current_user

    if payload.name is not None:
        user.name = payload.name
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.handle is not None:
        existing = await users.get_by_handle(payload.handle)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=409, detail="Handle ja esta em uso")
        user.handle = payload.handle

    user.updated_at = datetime.now(UTC)
    await users.save(user)
    return UserProfileResponse.from_entity(user)


@router.post("/me/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    current_user: CurrentUserDep,
    users: UserRepoDep,
    file: UploadFile = File(...),
) -> AvatarUploadResponse:
    """Upload do avatar do usuario (valida tipo e tamanho)."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Formato invalido. Use JPG, PNG ou WebP")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Maximo 5MB")

    # TODO: upload para storage S3-compatível e obter URL
    # Por enquanto, simula com data URL (em produção usar storage real)
    import base64
    b64 = base64.b64encode(content).decode()
    avatar_url = f"data:{file.content_type};base64,{b64}"

    current_user.avatar_url = avatar_url
    current_user.updated_at = datetime.now(UTC)
    await users.save(current_user)

    return AvatarUploadResponse(avatar_url=avatar_url)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def remove_avatar(
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> Response:
    """Remove o avatar do usuario (volta para avatar padrão)."""
    current_user.avatar_url = None
    current_user.updated_at = datetime.now(UTC)
    await users.save(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/stats", response_model=StatsResponse)
async def get_stats(
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> StatsResponse:
    """Obtem estatisticas da conta."""
    # TODO: consultar contagens reais de generations e gallery
    return StatsResponse(
        account_created_at=current_user.created_at.isoformat(),
        total_generations=0,  # TODO: query real
        total_saved_arts=0,  # TODO: query real
        current_tier="Free",
        credits_used_this_period=50 - current_user.generation_credits,
        credits_limit=50,
    )


@router.get("/me/providers", response_model=ConnectedProvidersResponse)
async def get_connected_providers(
    current_user: CurrentUserDep,
) -> ConnectedProvidersResponse:
    """Lista provedores OAuth conectados."""
    providers = []
    if current_user.google_sub:
        providers.append(ConnectedProvider(name="Google", connected=True, email=current_user.email))
    # TODO: adicionar outros provedores quando implementados
    return ConnectedProvidersResponse(providers=providers)


@router.delete("/me/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: str,
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> None:
    """Desconecta um provedor OAuth (bloqueia se for o único método de login)."""
    if provider != "google":
        raise HTTPException(status_code=400, detail="Provedor invalido")

    if not current_user.google_sub:
        raise HTTPException(status_code=400, detail="Provedor nao conectado")

    if not current_user.has_alternative_login():
        raise HTTPException(
            status_code=400,
            detail="Nao e possivel desconectar o unico metodo de login. "
                   "Defina uma senha primeiro nas configuracoes de seguranca.",
        )

    current_user.google_sub = None
    current_user.updated_at = datetime.now(UTC)
    await users.save(current_user)


@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_settings(
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> UserSettingsResponse:
    """Obtem as configuracoes do usuario."""
    settings = await _get_or_create_settings(current_user.id, users)
    return UserSettingsResponse.from_entity(settings)


@router.put("/me/settings", response_model=UserSettingsResponse)
async def update_settings(
    payload: UpdateSettingsInput,
    current_user: CurrentUserDep,
    users: UserRepoDep,
) -> UserSettingsResponse:
    """Atualiza as configuracoes do usuario."""
    settings = await _get_or_create_settings(current_user.id, users)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if hasattr(settings, key):
            if key == "consented_at" and value:
                value = datetime.fromisoformat(value)
            setattr(settings, key, value)

    settings.updated_at = datetime.now(UTC)
    await users.save_settings(settings)
    return UserSettingsResponse.from_entity(settings)


@router.post("/me/export", response_model=ExportRequestResponse)
async def request_data_export(
    current_user: CurrentUserDep,
) -> ExportRequestResponse:
    """Solicita exportacao de dados (LGPD Art. 18, V)."""
    # TODO: enfileirar job Celery para processar exportacao
    return ExportRequestResponse(
        message=(
            "Exportacao solicitada. Voce recebera um e-mail com o link "
            "para download quando estiver pronto."
        )
    )


@router.post("/me/delete-request", response_model=DeleteRequestResponse)
async def request_account_deletion(
    current_user: CurrentUserDep,
) -> DeleteRequestResponse:
    """Solicita exclusao da conta (LGPD Art. 18, VI) — soft delete."""
    # TODO: marcar usuario para exclusao, agendar job para exclusao definitiva apos 30 dias
    return DeleteRequestResponse(
        message=(
            "Solicitacao de exclusao recebida. Sua conta sera excluida "
            "definitivamente em 30 dias. Para cancelar, faca login "
            "novamente dentro desse periodo."
        ),
        grace_period_days=30,
    )