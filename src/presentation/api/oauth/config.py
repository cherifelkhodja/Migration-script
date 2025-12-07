"""
OAuth Config - Configuration des providers OAuth.

Responsabilite unique:
----------------------
Configurer les providers OAuth (Google, GitHub).

Variables requises:
-------------------
- GOOGLE_CLIENT_ID: ID client Google
- GOOGLE_CLIENT_SECRET: Secret client Google
- GITHUB_CLIENT_ID: ID client GitHub
- GITHUB_CLIENT_SECRET: Secret client GitHub
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class OAuthSettings(BaseSettings):
    """
    Configuration OAuth.

    Chargee depuis les variables d'environnement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # URLs
    oauth_redirect_base: str = "http://localhost:8000"

    @property
    def google_enabled(self) -> bool:
        """Retourne True si Google OAuth est configure."""
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def github_enabled(self) -> bool:
        """Retourne True si GitHub OAuth est configure."""
        return bool(self.github_client_id and self.github_client_secret)


@lru_cache
def get_oauth_settings() -> OAuthSettings:
    """Retourne la configuration OAuth (cached)."""
    return OAuthSettings()
