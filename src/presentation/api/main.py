"""
Main - Factory FastAPI.

Responsabilite unique:
----------------------
Creer et configurer l'application FastAPI.

Usage:
------
    # Development
    uvicorn src.presentation.api.main:app --reload

    # Production
    uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.presentation.api.config import get_settings
from src.presentation.api.auth.router import router as auth_router
from src.presentation.api.billing.router import router as billing_router
from src.presentation.api.oauth.router import router as oauth_router
from src.infrastructure.logging import configure_logging, get_logger
from src.infrastructure.logging.config import RequestLogger


def create_app() -> FastAPI:
    """
    Factory pour creer l'application FastAPI.

    Returns:
        Application FastAPI configuree.
    """
    settings = get_settings()

    # Configure logging (JSON in production)
    is_production = os.getenv("ENV", "development") == "production"
    configure_logging(json_logs=is_production)
    logger = get_logger("api")

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Request logging middleware
    app.add_middleware(BaseHTTPMiddleware, dispatch=RequestLogger())

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info("app_started", version=settings.api_version)

    # Health check
    @app.get("/health", tags=["Health"])
    def health():
        """Endpoint de sante."""
        return {"status": "healthy"}

    # Routers
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(billing_router, prefix=settings.api_prefix)
    app.include_router(oauth_router, prefix=settings.api_prefix)

    return app


# Instance pour uvicorn
app = create_app()
