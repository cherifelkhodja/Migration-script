"""
Auth Schemas - Modeles Pydantic pour l'authentification.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les endpoints auth.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class LoginRequest(BaseModel):
    """
    Requete de login.

    Example:
        {"username": "john", "password": "secret123"}
    """

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """
    Reponse avec tokens JWT.

    Example:
        {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Requete de refresh token."""

    refresh_token: str


class UserResponse(BaseModel):
    """
    Profil utilisateur.

    Retourne par GET /auth/me.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class ErrorResponse(BaseModel):
    """Reponse d'erreur standardisee."""

    error: str
    detail: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    """
    Requete de demande de reset de mot de passe.

    Example:
        {"email": "user@example.com"}
    """

    email: str = Field(..., min_length=5)


class ForgotPasswordResponse(BaseModel):
    """
    Reponse de demande de reset.

    Note: Toujours succes pour eviter enumeration d'emails.
    """

    message: str


class ResetPasswordRequest(BaseModel):
    """
    Requete de reset de mot de passe.

    Example:
        {"token": "abc123...", "new_password": "NewSecureP@ss123"}
    """

    token: str = Field(..., min_length=32)
    new_password: str = Field(..., min_length=8)


class ResetPasswordResponse(BaseModel):
    """Reponse de reset de mot de passe."""

    message: str
