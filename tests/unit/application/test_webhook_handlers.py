"""
Tests unitaires pour les Webhook Handlers.

Teste les use cases de traitement des webhooks Stripe.
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock

from src.application.use_cases.billing.webhook_handlers import (
    HandleCheckoutCompleted,
    HandleSubscriptionUpdated,
    HandleSubscriptionCanceled,
    WebhookResult,
)


class TestHandleCheckoutCompleted:
    """Tests pour HandleCheckoutCompleted."""

    def test_execute_logs_subscription_created(self):
        """execute() log la creation d'abonnement."""
        # Arrange
        user_id = uuid4()
        user = Mock()
        user.id = user_id
        user.username = "john"

        user_repo = Mock()
        user_repo.get_by_id.return_value = user

        audit_repo = Mock()

        handler = HandleCheckoutCompleted(user_repo, audit_repo)

        event_data = {
            "metadata": {"user_id": str(user_id)},
            "customer": "cus_123456",
        }

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert result.action_taken == "subscription_linked"
        audit_repo.log.assert_called_once()

    def test_execute_ignores_missing_user_id(self):
        """execute() ignore les events sans user_id."""
        # Arrange
        user_repo = Mock()
        audit_repo = Mock()

        handler = HandleCheckoutCompleted(user_repo, audit_repo)

        event_data = {"customer": "cus_123456"}

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert result.action_taken == "ignored_missing_data"
        audit_repo.log.assert_not_called()

    def test_execute_fails_on_invalid_user_id(self):
        """execute() echoue sur user_id invalide."""
        # Arrange
        user_repo = Mock()
        audit_repo = Mock()

        handler = HandleCheckoutCompleted(user_repo, audit_repo)

        event_data = {
            "metadata": {"user_id": "not-a-uuid"},
            "customer": "cus_123456",
        }

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is False
        assert result.error == "invalid_user_id"

    def test_execute_fails_on_user_not_found(self):
        """execute() echoue si utilisateur non trouve."""
        # Arrange
        user_repo = Mock()
        user_repo.get_by_id.return_value = None

        audit_repo = Mock()

        handler = HandleCheckoutCompleted(user_repo, audit_repo)

        event_data = {
            "metadata": {"user_id": str(uuid4())},
            "customer": "cus_123456",
        }

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is False
        assert result.error == "user_not_found"


class TestHandleSubscriptionUpdated:
    """Tests pour HandleSubscriptionUpdated."""

    def test_execute_logs_status_update(self):
        """execute() log la mise a jour de statut."""
        # Arrange
        user_id = uuid4()
        audit_repo = Mock()

        handler = HandleSubscriptionUpdated(audit_repo)

        event_data = {
            "metadata": {"user_id": str(user_id)},
            "status": "active",
        }

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert "active" in result.action_taken
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "subscription_updated"

    def test_execute_ignores_missing_user_id(self):
        """execute() ignore les events sans user_id."""
        # Arrange
        audit_repo = Mock()

        handler = HandleSubscriptionUpdated(audit_repo)

        event_data = {"status": "canceled"}

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert result.action_taken == "ignored_no_user_id"


class TestHandleSubscriptionCanceled:
    """Tests pour HandleSubscriptionCanceled."""

    def test_execute_logs_cancellation(self):
        """execute() log l'annulation."""
        # Arrange
        user_id = uuid4()
        audit_repo = Mock()

        handler = HandleSubscriptionCanceled(audit_repo)

        event_data = {"metadata": {"user_id": str(user_id)}}

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert result.action_taken == "logged_cancellation"
        audit_repo.log.assert_called_once()
        call_kwargs = audit_repo.log.call_args.kwargs
        assert call_kwargs["action"] == "subscription_canceled"

    def test_execute_ignores_missing_user_id(self):
        """execute() ignore les events sans user_id."""
        # Arrange
        audit_repo = Mock()

        handler = HandleSubscriptionCanceled(audit_repo)

        event_data = {}

        # Act
        result = handler.execute(event_data)

        # Assert
        assert result.success is True
        assert result.action_taken == "ignored_no_user_id"


class TestWebhookResult:
    """Tests pour WebhookResult."""

    def test_success_result(self):
        """WebhookResult represente un succes."""
        result = WebhookResult(
            success=True,
            action_taken="subscription_linked"
        )

        assert result.success is True
        assert result.action_taken == "subscription_linked"
        assert result.error is None

    def test_failure_result(self):
        """WebhookResult represente un echec."""
        result = WebhookResult(
            success=False,
            error="user_not_found"
        )

        assert result.success is False
        assert result.error == "user_not_found"
