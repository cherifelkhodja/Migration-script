"""
Users Schemas - Modeles Pydantic pour les endpoints users.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour la gestion des utilisateurs.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserResponse(BaseModel):
    """Representation d'un utilisateur."""

    id: UUID
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserListResponse(BaseModel):
    """Liste paginee d'utilisateurs."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CreateUserRequest(BaseModel):
    """Requete de creation d'utilisateur."""

    username: str = Field(..., min_length=3, max_length=50, description="Nom d'utilisateur")
    email: str = Field(..., description="Email")
    password: str = Field(..., min_length=6, description="Mot de passe")
    role: str = Field(default="viewer", description="Role (admin, analyst, viewer)")


class UpdateUserRequest(BaseModel):
    """Requete de mise a jour d'utilisateur."""

    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """Requete de changement de mot de passe."""

    current_password: str = Field(..., description="Mot de passe actuel")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe")
