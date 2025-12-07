"""
OAuth Providers - Integration Google et GitHub.

Responsabilite unique:
----------------------
Gerer les flux OAuth2 avec Google et GitHub.

Usage:
------
    provider = GoogleOAuth(settings)
    auth_url = provider.get_authorization_url(state="xxx")
    user_info = await provider.get_user_info(code="yyy")
"""

from dataclasses import dataclass
from typing import Optional
import httpx

from src.presentation.api.oauth.config import OAuthSettings


@dataclass
class OAuthUserInfo:
    """
    Informations utilisateur OAuth.

    Attributes:
        provider: Nom du provider (google, github).
        provider_id: ID unique chez le provider.
        email: Email de l'utilisateur.
        name: Nom affiche.
        avatar_url: URL de l'avatar.
    """

    provider: str
    provider_id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class GoogleOAuth:
    """
    Provider OAuth Google.

    Gere le flux authorization code avec Google.
    """

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def __init__(self, settings: OAuthSettings):
        """
        Initialise le provider Google.

        Args:
            settings: Configuration OAuth.
        """
        self._client_id = settings.google_client_id
        self._client_secret = settings.google_client_secret
        self._redirect_uri = f"{settings.oauth_redirect_base}/api/v1/oauth/google/callback"

    def get_authorization_url(self, state: str) -> str:
        """
        Genere l'URL d'autorisation Google.

        Args:
            state: Token anti-CSRF.

        Returns:
            URL de redirection vers Google.
        """
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTHORIZE_URL}?{query}"

    async def get_user_info(self, code: str) -> Optional[OAuthUserInfo]:
        """
        Echange le code contre les infos utilisateur.

        Args:
            code: Code d'autorisation.

        Returns:
            OAuthUserInfo ou None si erreur.
        """
        async with httpx.AsyncClient() as client:
            # Echanger code contre token
            token_response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

            if token_response.status_code != 200:
                return None

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            if not access_token:
                return None

            # Recuperer les infos utilisateur
            user_response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if user_response.status_code != 200:
                return None

            user_data = user_response.json()

            return OAuthUserInfo(
                provider="google",
                provider_id=user_data.get("id", ""),
                email=user_data.get("email", ""),
                name=user_data.get("name"),
                avatar_url=user_data.get("picture"),
            )


class GitHubOAuth:
    """
    Provider OAuth GitHub.

    Gere le flux authorization code avec GitHub.
    """

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def __init__(self, settings: OAuthSettings):
        """
        Initialise le provider GitHub.

        Args:
            settings: Configuration OAuth.
        """
        self._client_id = settings.github_client_id
        self._client_secret = settings.github_client_secret
        self._redirect_uri = f"{settings.oauth_redirect_base}/api/v1/oauth/github/callback"

    def get_authorization_url(self, state: str) -> str:
        """
        Genere l'URL d'autorisation GitHub.

        Args:
            state: Token anti-CSRF.

        Returns:
            URL de redirection vers GitHub.
        """
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTHORIZE_URL}?{query}"

    async def get_user_info(self, code: str) -> Optional[OAuthUserInfo]:
        """
        Echange le code contre les infos utilisateur.

        Args:
            code: Code d'autorisation.

        Returns:
            OAuthUserInfo ou None si erreur.
        """
        async with httpx.AsyncClient() as client:
            # Echanger code contre token
            token_response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            if token_response.status_code != 200:
                return None

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            if not access_token:
                return None

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            # Recuperer les infos utilisateur
            user_response = await client.get(self.USERINFO_URL, headers=headers)

            if user_response.status_code != 200:
                return None

            user_data = user_response.json()

            # Recuperer l'email (peut etre prive)
            email = user_data.get("email")
            if not email:
                emails_response = await client.get(self.EMAILS_URL, headers=headers)
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary = next(
                        (e for e in emails if e.get("primary")),
                        emails[0] if emails else None
                    )
                    if primary:
                        email = primary.get("email", "")

            return OAuthUserInfo(
                provider="github",
                provider_id=str(user_data.get("id", "")),
                email=email or "",
                name=user_data.get("name") or user_data.get("login"),
                avatar_url=user_data.get("avatar_url"),
            )
