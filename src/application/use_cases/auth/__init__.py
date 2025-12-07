"""
Use Cases d'authentification.

Chaque use case a une responsabilite unique:
- LoginUseCase: Authentifier un utilisateur
- CreateUserUseCase: Creer un nouvel utilisateur
- OAuthLoginUseCase: Authentifier via OAuth (Google, GitHub)

Pattern Command:
----------------
Chaque use case recoit une Request et retourne une Response.
Les dependances sont injectees via le constructeur.
"""

from src.application.use_cases.auth.login import LoginUseCase, LoginRequest, LoginResponse
from src.application.use_cases.auth.create_user import (
    CreateUserUseCase,
    CreateUserRequest,
    CreateUserResponse,
)
from src.application.use_cases.auth.oauth_login import (
    OAuthLoginUseCase,
    OAuthLoginRequest,
    OAuthLoginResponse,
)

__all__ = [
    "LoginUseCase",
    "LoginRequest",
    "LoginResponse",
    "CreateUserUseCase",
    "CreateUserRequest",
    "CreateUserResponse",
    "OAuthLoginUseCase",
    "OAuthLoginRequest",
    "OAuthLoginResponse",
]
