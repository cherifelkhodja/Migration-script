"""
Auth API - Authentification JWT.

Endpoints:
----------
- POST /auth/login: Obtenir un access token
- POST /auth/refresh: Rafraichir le token
- GET /auth/me: Profil utilisateur courant
"""

from src.presentation.api.auth.router import router
from src.presentation.api.auth.jwt_service import JWTService

__all__ = ["router", "JWTService"]
