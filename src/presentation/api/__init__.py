"""
API REST - FastAPI.

Presentation layer pour les clients externes (mobile, integrations).
Utilise JWT pour l'authentification.

Routers disponibles:
--------------------
- auth: Login, refresh token
- pages: CRUD pages
- billing: Stripe webhooks

Usage:
------
    uvicorn src.presentation.api.main:app --reload
"""

from src.presentation.api.main import create_app

__all__ = ["create_app"]
