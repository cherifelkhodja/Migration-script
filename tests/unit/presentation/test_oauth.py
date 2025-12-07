"""
Tests unitaires pour OAuth.

Teste la configuration et les providers OAuth.
"""

import pytest

from src.presentation.api.oauth.config import OAuthSettings
from src.presentation.api.oauth.providers import (
    GoogleOAuth,
    GitHubOAuth,
    OAuthUserInfo,
)


class TestOAuthSettings:
    """Tests pour la configuration OAuth."""

    def test_google_disabled_without_credentials(self):
        """google_enabled est False sans credentials."""
        settings = OAuthSettings()

        assert settings.google_enabled is False

    def test_google_enabled_with_credentials(self):
        """google_enabled est True avec credentials."""
        settings = OAuthSettings(
            google_client_id="client-id",
            google_client_secret="client-secret"
        )

        assert settings.google_enabled is True

    def test_github_disabled_without_credentials(self):
        """github_enabled est False sans credentials."""
        settings = OAuthSettings()

        assert settings.github_enabled is False

    def test_github_enabled_with_credentials(self):
        """github_enabled est True avec credentials."""
        settings = OAuthSettings(
            github_client_id="client-id",
            github_client_secret="client-secret"
        )

        assert settings.github_enabled is True


class TestGoogleOAuth:
    """Tests pour le provider Google."""

    def test_get_authorization_url_includes_state(self):
        """get_authorization_url inclut le state."""
        settings = OAuthSettings(
            google_client_id="test-client",
            google_client_secret="test-secret",
            oauth_redirect_base="http://localhost:8000"
        )
        provider = GoogleOAuth(settings)

        url = provider.get_authorization_url(state="test-state-123")

        assert "test-state-123" in url
        assert "test-client" in url
        assert "accounts.google.com" in url

    def test_get_authorization_url_includes_scopes(self):
        """get_authorization_url inclut les scopes."""
        settings = OAuthSettings(
            google_client_id="test-client",
            google_client_secret="test-secret"
        )
        provider = GoogleOAuth(settings)

        url = provider.get_authorization_url(state="xxx")

        assert "openid" in url
        assert "email" in url
        assert "profile" in url


class TestGitHubOAuth:
    """Tests pour le provider GitHub."""

    def test_get_authorization_url_includes_state(self):
        """get_authorization_url inclut le state."""
        settings = OAuthSettings(
            github_client_id="test-client",
            github_client_secret="test-secret",
            oauth_redirect_base="http://localhost:8000"
        )
        provider = GitHubOAuth(settings)

        url = provider.get_authorization_url(state="test-state-456")

        assert "test-state-456" in url
        assert "test-client" in url
        assert "github.com" in url

    def test_get_authorization_url_includes_scope(self):
        """get_authorization_url inclut le scope email."""
        settings = OAuthSettings(
            github_client_id="test-client",
            github_client_secret="test-secret"
        )
        provider = GitHubOAuth(settings)

        url = provider.get_authorization_url(state="xxx")

        assert "user:email" in url


class TestOAuthUserInfo:
    """Tests pour OAuthUserInfo."""

    def test_user_info_from_google(self):
        """OAuthUserInfo peut stocker les infos Google."""
        info = OAuthUserInfo(
            provider="google",
            provider_id="123456789",
            email="user@gmail.com",
            name="John Doe",
            avatar_url="https://lh3.googleusercontent.com/..."
        )

        assert info.provider == "google"
        assert info.email == "user@gmail.com"
        assert info.name == "John Doe"

    def test_user_info_minimal(self):
        """OAuthUserInfo fonctionne avec le minimum."""
        info = OAuthUserInfo(
            provider="github",
            provider_id="987654",
            email="user@github.com"
        )

        assert info.provider == "github"
        assert info.email == "user@github.com"
        assert info.name is None
        assert info.avatar_url is None
