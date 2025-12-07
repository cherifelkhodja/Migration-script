"""
Configuration API - Settings Pydantic.

Responsabilite unique:
----------------------
Charger et valider la configuration API depuis les variables d'env.

Variables requises:
-------------------
- JWT_SECRET_KEY: Cle secrete pour signer les tokens
- JWT_ALGORITHM: Algorithme (defaut: HS256)
- JWT_EXPIRE_MINUTES: Duree de vie access token
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class APISettings(BaseSettings):
    """
    Configuration de l'API REST.

    Chargee depuis les variables d'environnement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # JWT
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # API
    api_title: str = "Meta Ads Analyzer API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["*"]

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""
    stripe_price_pro: str = ""
    stripe_price_enterprise: str = ""

    # SendGrid
    sendgrid_api_key: str = ""


@lru_cache
def get_settings() -> APISettings:
    """Retourne la configuration (cached)."""
    return APISettings()
