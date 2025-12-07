"""
Tests unitaires pour OAuthLoginUseCase.

Teste la logique de login/creation via OAuth.
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from src.application.use_cases.auth.oauth_login import (
    OAuthLoginUseCase,
    OAuthLoginRequest,
    OAuthLoginResponse,
)
from src.domain.entities.user import User
from src.domain.value_objects.role import Role


class TestOAuthLoginUseCase:
    """Tests pour OAuthLoginUseCase."""

    def test_login_existing_user_by_email(self):
        """Login retourne l'utilisateur existant si email trouve."""
        # Arrange
        existing_user = User(
            id=uuid4(),
            username="john",
            email="john@gmail.com",
            password_hash="",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = existing_user

        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        response = use_case.execute(OAuthLoginRequest(
            provider="google",
            provider_id="123",
            email="john@gmail.com",
        ))

        # Assert
        assert response.success is True
        assert response.user == existing_user
        assert response.is_new_user is False
        audit_repo.log.assert_called_once()

    def test_login_creates_new_user_if_not_found(self):
        """Login cree un nouvel utilisateur si email non trouve."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_email.return_value = None
        user_repo.get_by_username.return_value = None
        user_repo.save.side_effect = lambda u: u

        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        response = use_case.execute(OAuthLoginRequest(
            provider="github",
            provider_id="456",
            email="newuser@github.com",
            name="New User",
        ))

        # Assert
        assert response.success is True
        assert response.is_new_user is True
        assert response.user.email == "newuser@github.com"
        assert response.user.username == "newuser"
        user_repo.save.assert_called_once()

    def test_login_generates_unique_username(self):
        """Login genere un username unique si collision."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_email.return_value = None
        # Simule collision sur "john" et "john1"
        user_repo.get_by_username.side_effect = [
            Mock(),  # "john" existe
            Mock(),  # "john1" existe
            None,    # "john2" libre
        ]
        user_repo.save.side_effect = lambda u: u

        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        response = use_case.execute(OAuthLoginRequest(
            provider="google",
            provider_id="789",
            email="john@example.com",
        ))

        # Assert
        assert response.success is True
        assert response.user.username == "john2"

    def test_login_fails_without_email(self):
        """Login echoue si email vide."""
        # Arrange
        user_repo = Mock()
        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        response = use_case.execute(OAuthLoginRequest(
            provider="google",
            provider_id="123",
            email="",
        ))

        # Assert
        assert response.success is False
        assert response.error == "email_required"

    def test_login_logs_oauth_login_for_existing_user(self):
        """Login log l'action oauth_login pour utilisateur existant."""
        # Arrange
        existing_user = User(
            id=uuid4(),
            username="jane",
            email="jane@gmail.com",
            password_hash="",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = existing_user

        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        use_case.execute(OAuthLoginRequest(
            provider="github",
            provider_id="111",
            email="jane@gmail.com",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "oauth_login"
        assert call_kwargs["details"]["provider"] == "github"

    def test_login_logs_oauth_registration_for_new_user(self):
        """Login log l'action oauth_registration pour nouvel utilisateur."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_email.return_value = None
        user_repo.get_by_username.return_value = None
        user_repo.save.side_effect = lambda u: u

        audit_repo = Mock()

        use_case = OAuthLoginUseCase(user_repo, audit_repo)

        # Act
        use_case.execute(OAuthLoginRequest(
            provider="google",
            provider_id="222",
            email="brand.new@gmail.com",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "oauth_registration"


class TestOAuthLoginRequest:
    """Tests pour OAuthLoginRequest."""

    def test_request_with_all_fields(self):
        """Request accepte tous les champs."""
        request = OAuthLoginRequest(
            provider="google",
            provider_id="123456",
            email="user@gmail.com",
            name="John Doe",
        )

        assert request.provider == "google"
        assert request.provider_id == "123456"
        assert request.email == "user@gmail.com"
        assert request.name == "John Doe"

    def test_request_with_minimal_fields(self):
        """Request fonctionne avec champs minimaux."""
        request = OAuthLoginRequest(
            provider="github",
            provider_id="789",
            email="user@github.com",
        )

        assert request.name is None


class TestOAuthLoginResponse:
    """Tests pour OAuthLoginResponse."""

    def test_ok_factory(self):
        """ok() cree une reponse succes."""
        user = User(
            id=uuid4(),
            username="test",
            email="test@test.com",
            password_hash="",
            role=Role.viewer(),
        )

        response = OAuthLoginResponse.ok(user, is_new=True)

        assert response.success is True
        assert response.user == user
        assert response.is_new_user is True
        assert response.error is None

    def test_fail_factory(self):
        """fail() cree une reponse echec."""
        response = OAuthLoginResponse.fail("email_required")

        assert response.success is False
        assert response.user is None
        assert response.error == "email_required"
