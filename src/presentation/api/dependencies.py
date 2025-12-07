"""
Dependencies - Injection de dependances FastAPI.

Responsabilite unique:
----------------------
Fournir les dependances (repos, services) aux endpoints.

Usage:
------
    @router.get("/me")
    def get_me(user: User = Depends(get_current_user)):
        return user
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.presentation.api.config import get_settings, APISettings
from src.presentation.api.auth.jwt_service import JWTService, TokenPayload
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from src.domain.entities.user import User


# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    """Retourne le DatabaseManager."""
    return DatabaseManager()


def get_user_repository(db: DatabaseManager = Depends(get_db)):
    """Retourne le UserRepository."""
    return SqlAlchemyUserRepository(db)


def get_audit_repository(db: DatabaseManager = Depends(get_db)):
    """Retourne l'AuditRepository."""
    return SqlAlchemyAuditRepository(db)


def get_jwt_service(
    settings: APISettings = Depends(get_settings)
) -> JWTService:
    """Retourne le JWTService."""
    return JWTService(settings)


def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> Optional[TokenPayload]:
    """
    Extrait le payload du token JWT.

    Returns:
        TokenPayload si token valide, None sinon.
    """
    if not credentials:
        return None

    return jwt_service.verify_access_token(credentials.credentials)


def get_current_user(
    payload: Optional[TokenPayload] = Depends(get_token_payload),
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> User:
    """
    Retourne l'utilisateur courant.

    Raises:
        HTTPException 401 si non authentifie.
    """
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expire",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_repo.get_by_id(payload.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur inactif ou inexistant",
        )

    return user


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """
    Retourne l'utilisateur courant si admin.

    Raises:
        HTTPException 403 si pas admin.
    """
    if user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces reserve aux administrateurs",
        )
    return user


def require_permission(permission: str):
    """
    Factory pour verifier une permission.

    Usage:
        @router.get("/export")
        def export(user: User = Depends(require_permission("export"))):
            ...
    """
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.role.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission}",
            )
        return user

    return dependency
