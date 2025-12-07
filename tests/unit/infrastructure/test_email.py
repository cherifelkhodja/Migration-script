"""
Tests unitaires pour le service email.

Teste les templates et le service d'envoi.
"""

import pytest

from src.infrastructure.email.templates import EmailTemplate, EmailContent
from src.infrastructure.email.service import EmailService, EmailResult


class TestEmailTemplate:
    """Tests pour les templates email."""

    def test_welcome_returns_email_content(self):
        """welcome() retourne un EmailContent."""
        result = EmailTemplate.welcome(username="John")

        assert isinstance(result, EmailContent)
        assert result.subject == "Bienvenue sur Meta Ads Analyzer"
        assert "John" in result.html
        assert "John" in result.text

    def test_password_reset_includes_url(self):
        """password_reset() inclut l'URL de reset."""
        reset_url = "https://example.com/reset/abc123"
        result = EmailTemplate.password_reset(
            username="Jane",
            reset_url=reset_url
        )

        assert reset_url in result.html
        assert reset_url in result.text
        assert "Reset" in result.subject

    def test_subscription_confirmed_includes_plan(self):
        """subscription_confirmed() inclut le plan."""
        result = EmailTemplate.subscription_confirmed(
            username="Bob",
            plan="pro",
            amount="49€"
        )

        assert "PRO" in result.html
        assert "49€" in result.html
        assert "PRO" in result.subject

    def test_scan_completed_includes_stats(self):
        """scan_completed() inclut les stats."""
        result = EmailTemplate.scan_completed(
            username="Alice",
            site_count=100,
            winning_count=25
        )

        assert "100" in result.html
        assert "25" in result.html
        assert "25" in result.subject

    def test_alert_rate_limit_includes_api_name(self):
        """alert_rate_limit() inclut le nom de l'API."""
        result = EmailTemplate.alert_rate_limit(
            api_name="Meta API",
            retry_after=60
        )

        assert "Meta API" in result.html
        assert "60" in result.html
        assert "Rate Limit" in result.subject


class TestEmailService:
    """Tests pour le service email."""

    def test_service_disabled_without_api_key(self):
        """Service desactive sans cle API."""
        service = EmailService(api_key="")

        assert service.is_enabled is False

    def test_service_enabled_with_api_key(self):
        """Service active avec cle API."""
        service = EmailService(api_key="SG.test-key")

        assert service.is_enabled is True

    def test_send_returns_error_when_disabled(self):
        """send() retourne erreur si desactive."""
        service = EmailService(api_key="")

        result = service.send(
            to="test@example.com",
            subject="Test",
            html="<h1>Test</h1>"
        )

        assert isinstance(result, EmailResult)
        assert result.success is False
        assert "disabled" in result.error.lower()

    def test_send_with_custom_from_email(self):
        """Service utilise l'email expediteur custom."""
        service = EmailService(
            api_key="",
            from_email="custom@example.com",
            from_name="Custom Name"
        )

        assert service._from_email == "custom@example.com"
        assert service._from_name == "Custom Name"
