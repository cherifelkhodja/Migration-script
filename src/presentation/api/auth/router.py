"""
Auth Router - Endpoints d'authentification.

Responsabilite unique:
----------------------
Exposer les endpoints login, refresh, me, forgot-password, reset-password.

Endpoints:
----------
- POST /auth/login: Authentification
- POST /auth/refresh: Rafraichir le token
- GET /auth/me: Profil utilisateur
- POST /auth/forgot-password: Demander un reset de mot de passe
- POST /auth/reset-password: Executer le reset de mot de passe
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request

from src.presentation.api.auth.schemas import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
    ErrorResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from src.presentation.api.auth.jwt_service import JWTService
from src.presentation.api.dependencies import (
    get_jwt_service,
    get_user_repository,
    get_audit_repository,
    get_current_user,
    get_state_storage,
    get_email_service,
)
from src.application.use_cases.auth.login import (
    LoginUseCase,
    LoginRequest as UseCaseLoginRequest,
)
from src.application.use_cases.auth.request_password_reset import (
    RequestPasswordResetUseCase,
    RequestPasswordResetRequest,
)
from src.application.use_cases.auth.reset_password import (
    ResetPasswordUseCase,
    ResetPasswordRequest as UseCaseResetPasswordRequest,
)
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from src.domain.entities.user import User
from src.domain.ports.state_storage import StateStorage
from src.infrastructure.email.service import EmailService


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Authentification",
    description="Retourne un access token et refresh token.",
)
def login(
    data: LoginRequest,
    request: Request,
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """
    Authentifie un utilisateur.

    Returns:
        TokenResponse avec access et refresh tokens.

    Raises:
        HTTPException 401 si credentials invalides.
    """
    # Extraire IP client
    client_ip = request.client.host if request.client else None

    # Executer le use case
    use_case = LoginUseCase(user_repo, audit_repo)
    response = use_case.execute(
        UseCaseLoginRequest(
            username=data.username,
            password=data.password,
            ip_address=client_ip,
        )
    )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_translate_error(response.error),
        )

    # Generer les tokens
    return jwt_service.create_tokens(
        user_id=response.user.id,
        role=response.user.role.name,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Rafraichir le token",
    description="Genere un nouveau access token depuis le refresh token.",
)
def refresh(
    data: RefreshRequest,
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """
    Rafraichit l'access token.

    Returns:
        Nouveaux tokens.

    Raises:
        HTTPException 401 si refresh token invalide.
    """
    # Verifier le refresh token
    payload = jwt_service.verify_refresh_token(data.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expire",
        )

    # Verifier que l'utilisateur existe toujours
    user = user_repo.get_by_id(payload.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur inactif",
        )

    # Generer de nouveaux tokens
    return jwt_service.create_tokens(
        user_id=user.id,
        role=user.role.name,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil utilisateur",
    description="Retourne le profil de l'utilisateur authentifie.",
)
def get_me(user: User = Depends(get_current_user)):
    """
    Retourne le profil de l'utilisateur courant.

    Returns:
        UserResponse avec les infos utilisateur.
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


def _translate_error(code: str) -> str:
    """Traduit les codes d'erreur en messages."""
    translations = {
        "invalid_credentials": "Identifiants incorrects",
        "account_inactive": "Compte desactive",
        "account_locked": "Compte verrouille (trop de tentatives)",
    }
    return translations.get(code, code)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Demander un reset de mot de passe",
    description="Envoie un email avec un lien de reset (si l'email existe).",
)
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repository),
    state_storage: StateStorage = Depends(get_state_storage),
    email_service: EmailService = Depends(get_email_service),
):
    """
    Demande un reset de mot de passe.

    Envoie un email avec un lien de reset si l'email existe.
    Retourne toujours succes pour eviter l'enumeration d'emails.
    """
    # Construire l'URL de base pour le reset
    base_url = str(request.base_url).rstrip("/")
    reset_base_url = f"{base_url}/reset-password"

    use_case = RequestPasswordResetUseCase(
        user_repo, state_storage, email_service, audit_repo
    )
    response = use_case.execute(
        RequestPasswordResetRequest(
            email=data.email,
            reset_url_base=reset_base_url,
        )
    )

    return ForgotPasswordResponse(message=response.message)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Executer le reset de mot de passe",
    description="Change le mot de passe avec le token recu par email.",
)
def reset_password(
    data: ResetPasswordRequest,
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repository),
    state_storage: StateStorage = Depends(get_state_storage),
):
    """
    Execute le reset de mot de passe.

    Valide le token et change le mot de passe.
    """
    use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)
    response = use_case.execute(
        UseCaseResetPasswordRequest(
            token=data.token,
            new_password=data.new_password,
        )
    )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_reset_error(response.error),
        )

    return ResetPasswordResponse(message="Mot de passe modifie avec succes")


def _translate_reset_error(code: str) -> str:
    """Traduit les codes d'erreur de reset en messages."""
    translations = {
        "password_too_short": "Mot de passe trop court (minimum 8 caracteres)",
        "password_too_weak": "Mot de passe trop faible (lettres et chiffres requis)",
        "invalid_or_expired_token": "Lien de reset invalide ou expire",
        "invalid_token_data": "Token invalide",
        "user_not_found": "Utilisateur non trouve",
        "account_inactive": "Compte desactive",
    }
    return translations.get(code, code)
