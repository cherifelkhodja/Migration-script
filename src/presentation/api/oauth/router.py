"""
OAuth Router - Endpoints OAuth2.

Responsabilite unique:
----------------------
Exposer les endpoints OAuth (Google, GitHub).
Delegue la logique metier aux Use Cases.

Endpoints:
----------
- GET /oauth/google: Initie le flux Google
- GET /oauth/google/callback: Callback Google
- GET /oauth/github: Initie le flux GitHub
- GET /oauth/github/callback: Callback GitHub
"""

import secrets

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import RedirectResponse

from src.presentation.api.oauth.config import get_oauth_settings, OAuthSettings
from src.presentation.api.oauth.providers import GoogleOAuth, GitHubOAuth
from src.presentation.api.auth.jwt_service import JWTService
from src.presentation.api.config import get_settings, APISettings
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository
from src.domain.ports.state_storage import StateStorage
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from src.infrastructure.adapters.memory_state_storage import MemoryStateStorage
from src.infrastructure.persistence.database import DatabaseManager
from src.application.use_cases.auth.oauth_login import (
    OAuthLoginUseCase,
    OAuthLoginRequest,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth"])

# Singleton pour le state storage (en production, injecter Redis)
_state_storage = MemoryStateStorage()


# ============ Dependencies ============

def get_state_storage() -> StateStorage:
    """Retourne le StateStorage."""
    return _state_storage


def get_db() -> DatabaseManager:
    """Retourne le DatabaseManager."""
    return DatabaseManager()


def get_user_repository(db: DatabaseManager = Depends(get_db)) -> UserRepository:
    """Retourne le UserRepository (abstrait)."""
    return SqlAlchemyUserRepository(db)


def get_audit_repository(db: DatabaseManager = Depends(get_db)) -> AuditRepository:
    """Retourne l'AuditRepository (abstrait)."""
    return SqlAlchemyAuditRepository(db)


def get_jwt_service(
    settings: APISettings = Depends(get_settings)
) -> JWTService:
    """Retourne le JWTService."""
    return JWTService(settings)


def get_oauth_login_use_case(
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> OAuthLoginUseCase:
    """Retourne le OAuthLoginUseCase."""
    return OAuthLoginUseCase(user_repo, audit_repo)


# ============ Google ============

@router.get(
    "/google",
    summary="Login Google",
    description="Redirige vers la page de login Google.",
)
def google_login(
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    state_storage: StateStorage = Depends(get_state_storage),
):
    """Initie le flux OAuth Google."""
    if not oauth_settings.google_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth non configure",
        )

    state = secrets.token_urlsafe(32)
    state_storage.set(f"oauth:{state}", "google", ttl_seconds=600)

    provider = GoogleOAuth(oauth_settings)
    return RedirectResponse(url=provider.get_authorization_url(state))


@router.get(
    "/google/callback",
    summary="Callback Google",
    description="Callback apres authentification Google.",
)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    state_storage: StateStorage = Depends(get_state_storage),
    use_case: OAuthLoginUseCase = Depends(get_oauth_login_use_case),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """Traite le callback Google."""
    stored = state_storage.get(f"oauth:{state}")
    if stored != "google":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State invalide")
    state_storage.delete(f"oauth:{state}")

    provider = GoogleOAuth(oauth_settings)
    user_info = await provider.get_user_info(code)

    if not user_info or not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de recuperer les informations Google",
        )

    response = use_case.execute(OAuthLoginRequest(
        provider="google",
        provider_id=user_info.provider_id,
        email=user_info.email,
        name=user_info.name,
    ))

    if not response.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.error)

    tokens = jwt_service.create_tokens(response.user.id, response.user.role.name)
    logger.info("oauth_login", provider="google", user_id=str(response.user.id))

    return {"message": "Authentification reussie", "provider": "google", **tokens}


# ============ GitHub ============

@router.get(
    "/github",
    summary="Login GitHub",
    description="Redirige vers la page de login GitHub.",
)
def github_login(
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    state_storage: StateStorage = Depends(get_state_storage),
):
    """Initie le flux OAuth GitHub."""
    if not oauth_settings.github_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth non configure",
        )

    state = secrets.token_urlsafe(32)
    state_storage.set(f"oauth:{state}", "github", ttl_seconds=600)

    provider = GitHubOAuth(oauth_settings)
    return RedirectResponse(url=provider.get_authorization_url(state))


@router.get(
    "/github/callback",
    summary="Callback GitHub",
    description="Callback apres authentification GitHub.",
)
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_settings: OAuthSettings = Depends(get_oauth_settings),
    state_storage: StateStorage = Depends(get_state_storage),
    use_case: OAuthLoginUseCase = Depends(get_oauth_login_use_case),
    jwt_service: JWTService = Depends(get_jwt_service),
):
    """Traite le callback GitHub."""
    stored = state_storage.get(f"oauth:{state}")
    if stored != "github":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State invalide")
    state_storage.delete(f"oauth:{state}")

    provider = GitHubOAuth(oauth_settings)
    user_info = await provider.get_user_info(code)

    if not user_info or not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de recuperer les informations GitHub",
        )

    response = use_case.execute(OAuthLoginRequest(
        provider="github",
        provider_id=user_info.provider_id,
        email=user_info.email,
        name=user_info.name,
    ))

    if not response.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.error)

    tokens = jwt_service.create_tokens(response.user.id, response.user.role.name)
    logger.info("oauth_login", provider="github", user_id=str(response.user.id))

    return {"message": "Authentification reussie", "provider": "github", **tokens}
