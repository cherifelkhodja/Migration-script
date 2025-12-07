"""
Tests unitaires pour les Use Cases de reset de mot de passe.

Teste:
- RequestPasswordResetUseCase
- ResetPasswordUseCase
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from src.application.use_cases.auth.request_password_reset import (
    RequestPasswordResetUseCase,
    RequestPasswordResetRequest,
    RequestPasswordResetResponse,
)
from src.application.use_cases.auth.reset_password import (
    ResetPasswordUseCase,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from src.domain.entities.user import User
from src.domain.value_objects.role import Role


class TestRequestPasswordResetUseCase:
    """Tests pour RequestPasswordResetUseCase."""

    def test_execute_generates_token_for_existing_user(self):
        """execute() genere un token pour un utilisateur existant."""
        # Arrange
        user = User(
            id=uuid4(),
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = user

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        response = use_case.execute(RequestPasswordResetRequest(
            email="john@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert
        assert response.success is True
        assert response._token is not None
        assert len(response._token) >= 32
        state_storage.set.assert_called_once()
        email_service.send.assert_called_once()

    def test_execute_returns_success_for_unknown_email(self):
        """execute() retourne succes meme pour email inconnu (securite)."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_email.return_value = None

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        response = use_case.execute(RequestPasswordResetRequest(
            email="unknown@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert - toujours succes pour ne pas reveler si email existe
        assert response.success is True
        assert response._token is None
        email_service.send.assert_not_called()

    def test_execute_does_not_send_email_for_inactive_user(self):
        """execute() n'envoie pas d'email pour utilisateur inactif."""
        # Arrange
        user = User(
            id=uuid4(),
            username="inactive",
            email="inactive@example.com",
            password_hash="hash",
            role=Role.viewer(),
            is_active=False,
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = user

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        response = use_case.execute(RequestPasswordResetRequest(
            email="inactive@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert
        assert response.success is True
        email_service.send.assert_not_called()

    def test_execute_stores_token_with_ttl(self):
        """execute() stocke le token avec TTL d'1 heure."""
        # Arrange
        user = User(
            id=uuid4(),
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = user

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        response = use_case.execute(RequestPasswordResetRequest(
            email="john@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert
        call_args = state_storage.set.call_args
        assert call_args.kwargs.get("ttl_seconds") == 3600

    def test_execute_logs_password_reset_requested(self):
        """execute() log l'action password_reset_requested."""
        # Arrange
        user = User(
            id=uuid4(),
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_email.return_value = user

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        use_case.execute(RequestPasswordResetRequest(
            email="john@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "password_reset_requested"

    def test_execute_logs_unknown_email_attempt(self):
        """execute() log les tentatives sur email inconnu."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_email.return_value = None

        state_storage = Mock()
        email_service = Mock()
        audit_repo = Mock()

        use_case = RequestPasswordResetUseCase(
            user_repo, state_storage, email_service, audit_repo
        )

        # Act
        use_case.execute(RequestPasswordResetRequest(
            email="unknown@example.com",
            reset_url_base="https://app.com/reset",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "password_reset_requested_unknown_email"


class TestResetPasswordUseCase:
    """Tests pour ResetPasswordUseCase."""

    def test_execute_changes_password_with_valid_token(self):
        """execute() change le mot de passe avec token valide."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            username="john",
            email="john@example.com",
            password_hash="old_hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        state_storage = Mock()
        state_storage.get.return_value = str(user_id)

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NewSecure123",
        ))

        # Assert
        assert response.success is True
        user_repo.save.assert_called_once_with(user)
        state_storage.delete.assert_called_once()

    def test_execute_fails_with_invalid_token(self):
        """execute() echoue avec token invalide."""
        # Arrange
        user_repo = Mock()
        state_storage = Mock()
        state_storage.get.return_value = None  # Token non trouve

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="invalid_token_1234567890123456",
            new_password="NewSecure123",
        ))

        # Assert
        assert response.success is False
        assert response.error == "invalid_or_expired_token"

    def test_execute_fails_with_short_password(self):
        """execute() echoue avec mot de passe trop court."""
        # Arrange
        user_repo = Mock()
        state_storage = Mock()
        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="short",  # < 8 caracteres
        ))

        # Assert
        assert response.success is False
        assert response.error == "password_too_short"

    def test_execute_fails_with_weak_password(self):
        """execute() echoue avec mot de passe sans chiffres."""
        # Arrange
        user_repo = Mock()
        state_storage = Mock()
        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NoDigitsHere",  # Pas de chiffres
        ))

        # Assert
        assert response.success is False
        assert response.error == "password_too_weak"

    def test_execute_fails_with_password_only_digits(self):
        """execute() echoue avec mot de passe sans lettres."""
        # Arrange
        user_repo = Mock()
        state_storage = Mock()
        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="12345678",  # Pas de lettres
        ))

        # Assert
        assert response.success is False
        assert response.error == "password_too_weak"

    def test_execute_fails_for_user_not_found(self):
        """execute() echoue si utilisateur non trouve."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_id.return_value = None

        state_storage = Mock()
        state_storage.get.return_value = str(uuid4())

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NewSecure123",
        ))

        # Assert
        assert response.success is False
        assert response.error == "user_not_found"

    def test_execute_fails_for_inactive_user(self):
        """execute() echoue pour utilisateur inactif."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            username="inactive",
            email="inactive@example.com",
            password_hash="hash",
            role=Role.viewer(),
            is_active=False,
        )

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        state_storage = Mock()
        state_storage.get.return_value = str(user_id)

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        response = use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NewSecure123",
        ))

        # Assert
        assert response.success is False
        assert response.error == "account_inactive"

    def test_execute_invalidates_token_after_use(self):
        """execute() invalide le token apres usage."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        state_storage = Mock()
        state_storage.get.return_value = str(user_id)

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)
        token = "valid_token_12345678901234567890"

        # Act
        use_case.execute(ResetPasswordRequest(
            token=token,
            new_password="NewSecure123",
        ))

        # Assert
        state_storage.delete.assert_called_once_with(f"password_reset:{token}")

    def test_execute_resets_failed_login_attempts(self):
        """execute() reset le compteur de tentatives echouees."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )
        user.failed_login_attempts = 5

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        state_storage = Mock()
        state_storage.get.return_value = str(user_id)

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NewSecure123",
        ))

        # Assert
        assert user.failed_login_attempts == 0

    def test_execute_logs_password_reset_completed(self):
        """execute() log l'action password_reset_completed."""
        # Arrange
        user_id = uuid4()
        user = User(
            id=user_id,
            username="john",
            email="john@example.com",
            password_hash="hash",
            role=Role.viewer(),
        )

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        state_storage = Mock()
        state_storage.get.return_value = str(user_id)

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        use_case.execute(ResetPasswordRequest(
            token="valid_token_12345678901234567890",
            new_password="NewSecure123",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "password_reset_completed"

    def test_execute_logs_invalid_token_attempt(self):
        """execute() log les tentatives avec token invalide."""
        # Arrange
        user_repo = Mock()
        state_storage = Mock()
        state_storage.get.return_value = None

        audit_repo = Mock()

        use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)

        # Act
        use_case.execute(ResetPasswordRequest(
            token="invalid_token_1234567890123456",
            new_password="NewSecure123",
        ))

        # Assert
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "password_reset_invalid_token"


class TestRequestPasswordResetResponse:
    """Tests pour RequestPasswordResetResponse."""

    def test_response_always_reports_success(self):
        """Response est toujours succes (securite)."""
        response = RequestPasswordResetResponse(
            success=True,
            message="Si cet email existe, un lien a ete envoye.",
        )

        assert response.success is True

    def test_response_has_generic_message(self):
        """Response a un message generique."""
        response = RequestPasswordResetResponse(
            success=True,
            message="Si cet email existe, un lien a ete envoye.",
        )

        # Message ne revele pas si l'email existe
        assert "si" in response.message.lower() or "if" in response.message.lower()


class TestResetPasswordResponse:
    """Tests pour ResetPasswordResponse."""

    def test_ok_factory(self):
        """ok() cree une reponse succes."""
        response = ResetPasswordResponse.ok()

        assert response.success is True
        assert response.error is None

    def test_fail_factory(self):
        """fail() cree une reponse echec."""
        response = ResetPasswordResponse.fail("invalid_token")

        assert response.success is False
        assert response.error == "invalid_token"
