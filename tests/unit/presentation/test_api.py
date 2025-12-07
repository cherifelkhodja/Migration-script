"""
Tests unitaires pour l'API REST.

Teste les endpoints auth et la configuration JWT.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from src.presentation.api.auth.jwt_service import JWTService, TokenPayload
from src.presentation.api.auth.schemas import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from src.presentation.api.billing.schemas import (
    PlanType,
    SubscriptionStatus,
    CheckoutRequest,
)
from src.presentation.api.config import APISettings


class TestJWTService:
    """Tests pour le service JWT."""

    def test_create_tokens_returns_access_and_refresh(self):
        """create_tokens retourne access et refresh tokens."""
        settings = APISettings(jwt_secret_key="test-secret-key")
        service = JWTService(settings)

        user_id = uuid4()
        tokens = service.create_tokens(user_id, "admin")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] > 0

    def test_verify_access_token_valid(self):
        """verify_access_token retourne payload si valide."""
        settings = APISettings(jwt_secret_key="test-secret-key")
        service = JWTService(settings)

        user_id = uuid4()
        tokens = service.create_tokens(user_id, "analyst")

        payload = service.verify_access_token(tokens["access_token"])

        assert payload is not None
        assert payload.user_id == user_id
        assert payload.role == "analyst"
        assert payload.token_type == "access"

    def test_verify_access_token_invalid(self):
        """verify_access_token retourne None si invalide."""
        settings = APISettings(jwt_secret_key="test-secret-key")
        service = JWTService(settings)

        payload = service.verify_access_token("invalid-token")

        assert payload is None

    def test_verify_refresh_token_valid(self):
        """verify_refresh_token retourne payload si valide."""
        settings = APISettings(jwt_secret_key="test-secret-key")
        service = JWTService(settings)

        user_id = uuid4()
        tokens = service.create_tokens(user_id, "viewer")

        payload = service.verify_refresh_token(tokens["refresh_token"])

        assert payload is not None
        assert payload.user_id == user_id
        assert payload.token_type == "refresh"

    def test_access_token_not_valid_as_refresh(self):
        """Un access token n'est pas valide comme refresh."""
        settings = APISettings(jwt_secret_key="test-secret-key")
        service = JWTService(settings)

        user_id = uuid4()
        tokens = service.create_tokens(user_id, "admin")

        # Access token ne doit pas etre accepte comme refresh
        payload = service.verify_refresh_token(tokens["access_token"])

        assert payload is None

    def test_different_secrets_fail(self):
        """Token signe avec autre secret est invalide."""
        service1 = JWTService(APISettings(jwt_secret_key="secret-1"))
        service2 = JWTService(APISettings(jwt_secret_key="secret-2"))

        user_id = uuid4()
        tokens = service1.create_tokens(user_id, "admin")

        # Token de service1 invalide pour service2
        payload = service2.verify_access_token(tokens["access_token"])

        assert payload is None


class TestAPISchemas:
    """Tests pour les schemas Pydantic."""

    def test_login_request_validation(self):
        """LoginRequest valide les champs."""
        request = LoginRequest(username="john", password="password123")

        assert request.username == "john"
        assert request.password == "password123"

    def test_login_request_username_min_length(self):
        """Username doit avoir au moins 3 caracteres."""
        with pytest.raises(Exception):  # ValidationError
            LoginRequest(username="ab", password="password123")

    def test_login_request_password_min_length(self):
        """Password doit avoir au moins 8 caracteres."""
        with pytest.raises(Exception):  # ValidationError
            LoginRequest(username="john", password="short")

    def test_user_response_from_dict(self):
        """UserResponse peut etre cree depuis un dict."""
        data = {
            "id": uuid4(),
            "username": "john",
            "email": "john@example.com",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "last_login": None,
        }

        response = UserResponse(**data)

        assert response.username == "john"
        assert response.role == "admin"

    def test_checkout_request_validation(self):
        """CheckoutRequest valide le plan."""
        request = CheckoutRequest(
            plan=PlanType.PRO,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert request.plan == PlanType.PRO

    def test_plan_types(self):
        """Les types de plans sont corrects."""
        assert PlanType.STARTER.value == "starter"
        assert PlanType.PRO.value == "pro"
        assert PlanType.ENTERPRISE.value == "enterprise"

    def test_subscription_statuses(self):
        """Les statuts d'abonnement sont corrects."""
        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.CANCELED.value == "canceled"
        assert SubscriptionStatus.NONE.value == "none"


class TestAPIConfig:
    """Tests pour la configuration API."""

    def test_default_values(self):
        """APISettings a des valeurs par defaut."""
        settings = APISettings()

        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_expire_minutes == 30
        assert settings.jwt_refresh_expire_days == 7
        assert settings.api_prefix == "/api/v1"

    def test_custom_values(self):
        """APISettings accepte des valeurs custom."""
        settings = APISettings(
            jwt_secret_key="my-secret",
            jwt_access_expire_minutes=60,
        )

        assert settings.jwt_secret_key == "my-secret"
        assert settings.jwt_access_expire_minutes == 60
