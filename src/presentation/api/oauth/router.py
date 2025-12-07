"""
OAuth Router - Endpoints OAuth2.

Responsabilite unique:
----------------------
Exposer les endpoints OAuth (Google, GitHub).

Endpoints:
----------
- GET /oauth/google: Initie le flux Google
- GET /oauth/google/callback: Callback Google
- GET /oauth/github: Initie le flux GitHub
- GET /oauth/github/callback: Callback GitHub
"""

import secrets
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import RedirectResponse

from src.presentation.api.oauth.config import get_oauth_settings, OAuthSettings
from src.presentation.api.oauth.providers import GoogleOAuth, GitHubOAuth
from src.presentation.api.auth.jwt_service import JWTService
from src.presentation.api.config import get_settings, APISettings
from src.presentation.api.dependencies import get_user_repository
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.domain.entities.user import User
from src.domain.value_objects.role import Role
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth"])

# State storage (en production, utiliser Redis)
_oauth_states: dict[str, str] = {}


def get_jwt_service(
    settings: APISettings = Depends(get_settings)
) -> JWTService:
    """Retourne le JWTService."""
    return JWTService(settings)


# ============ Google ============

@router.get(
    "/google",
    summary="Login Google",
    description="Redirige vers la page de login Google.",
)
def google_login(
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
):
    """Initie le flux OAuth Google."""
    if not oauth_settings.google_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth non configure",
        )

    # Generer state anti-CSRF
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "google"

    provider = GoogleOAuth(oauth_settings)
    auth_url = provider.get_authorization_url(state)

    return RedirectResponse(url=auth_url)


@router.get(
    "/google/callback",
    summary="Callback Google",
    description="Callback apres authentification Google.",
)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """Traite le callback Google."""
    # Verifier state
    if state not in _oauth_states or _oauth_states[state] != "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State invalide",
        )
    del _oauth_states[state]

    # Recuperer les infos utilisateur
    provider = GoogleOAuth(oauth_settings)
    user_info = await provider.get_user_info(code)

    if not user_info or not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de recuperer les informations Google",
        )

    # Trouver ou creer l'utilisateur
    user = await _find_or_create_oauth_user(user_repo, user_info)

    # Generer les tokens
    tokens = jwt_service.create_tokens(user.id, user.role.name)

    logger.info(
        "oauth_login_success",
        provider="google",
        user_id=str(user.id),
        email=user_info.email,
    )

    # Rediriger vers le frontend avec le token
    # En production, rediriger vers une page qui stocke le token
    return {
        "message": "Authentification reussie",
        "provider": "google",
        "email": user_info.email,
        **tokens,
    }


# ============ GitHub ============

@router.get(
    "/github",
    summary="Login GitHub",
    description="Redirige vers la page de login GitHub.",
)
def github_login(
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
):
    """Initie le flux OAuth GitHub."""
    if not oauth_settings.github_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth non configure",
        )

    # Generer state anti-CSRF
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = "github"

    provider = GitHubOAuth(oauth_settings)
    auth_url = provider.get_authorization_url(state)

    return RedirectResponse(url=auth_url)


@router.get(
    "/github/callback",
    summary="Callback GitHub",
    description="Callback apres authentification GitHub.",
)
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """Traite le callback GitHub."""
    # Verifier state
    if state not in _oauth_states or _oauth_states[state] != "github":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State invalide",
        )
    del _oauth_states[state]

    # Recuperer les infos utilisateur
    provider = GitHubOAuth(oauth_settings)
    user_info = await provider.get_user_info(code)

    if not user_info or not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de recuperer les informations GitHub",
        )

    # Trouver ou creer l'utilisateur
    user = await _find_or_create_oauth_user(user_repo, user_info)

    # Generer les tokens
    tokens = jwt_service.create_tokens(user.id, user.role.name)

    logger.info(
        "oauth_login_success",
        provider="github",
        user_id=str(user.id),
        email=user_info.email,
    )

    return {
        "message": "Authentification reussie",
        "provider": "github",
        "email": user_info.email,
        **tokens,
    }


# ============ Helpers ============

async def _find_or_create_oauth_user(
    user_repo: SqlAlchemyUserRepository,
    user_info,
) -> User:
    """
    Trouve ou cree un utilisateur OAuth.

    Args:
        user_repo: Repository utilisateurs.
        user_info: Infos du provider OAuth.

    Returns:
        Utilisateur trouve ou cree.
    """
    # Chercher par email
    existing = user_repo.get_by_email(user_info.email)

    if existing:
        return existing

    # Creer un nouvel utilisateur
    username = user_info.email.split("@")[0]
    base_username = username

    # S'assurer que le username est unique
    counter = 1
    while user_repo.get_by_username(username):
        username = f"{base_username}{counter}"
        counter += 1

    # Creer sans mot de passe (OAuth only)
    new_user = User(
        id=uuid4(),
        username=username,
        email=user_info.email,
        password_hash="",  # Pas de password pour OAuth
        role=Role.viewer(),
    )

    return user_repo.save(new_user)
