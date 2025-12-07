"""
OAuth API - Authentification OAuth2.

Endpoints:
----------
- GET /oauth/google: Redirect vers Google
- GET /oauth/google/callback: Callback Google
- GET /oauth/github: Redirect vers GitHub
- GET /oauth/github/callback: Callback GitHub
"""

from src.presentation.api.oauth.router import router

__all__ = ["router"]
