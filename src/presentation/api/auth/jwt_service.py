"""
JWTService - Gestion des tokens JWT.

Responsabilite unique:
----------------------
Creer et valider les tokens JWT (access et refresh).

Usage:
------
    service = JWTService(settings)
    tokens = service.create_tokens(user_id, role)
    payload = service.verify_token(token)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from dataclasses import dataclass

import jwt
from jwt.exceptions import PyJWTError

from src.presentation.api.config import APISettings


@dataclass
class TokenPayload:
    """
    Payload decode d'un token JWT.

    Attributes:
        user_id: ID de l'utilisateur.
        role: Role de l'utilisateur.
        token_type: "access" ou "refresh".
        exp: Date d'expiration.
    """

    user_id: UUID
    role: str
    token_type: str
    exp: datetime


class JWTService:
    """
    Service de gestion JWT.

    Cree et valide les tokens access/refresh.
    """

    def __init__(self, settings: APISettings):
        """
        Initialise le service.

        Args:
            settings: Configuration API.
        """
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_expire = settings.jwt_access_expire_minutes
        self._refresh_expire = settings.jwt_refresh_expire_days

    def create_tokens(self, user_id: UUID, role: str) -> dict:
        """
        Cree une paire access/refresh tokens.

        Args:
            user_id: ID de l'utilisateur.
            role: Role de l'utilisateur.

        Returns:
            Dict avec access_token, refresh_token, expires_in.
        """
        now = datetime.now(timezone.utc)

        # Access token (courte duree)
        access_exp = now + timedelta(minutes=self._access_expire)
        access_token = self._encode({
            "sub": str(user_id),
            "role": role,
            "type": "access",
            "exp": access_exp,
            "iat": now,
        })

        # Refresh token (longue duree)
        refresh_exp = now + timedelta(days=self._refresh_expire)
        refresh_token = self._encode({
            "sub": str(user_id),
            "role": role,
            "type": "refresh",
            "exp": refresh_exp,
            "iat": now,
        })

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self._access_expire * 60,
        }

    def verify_access_token(self, token: str) -> Optional[TokenPayload]:
        """
        Verifie un access token.

        Args:
            token: Token JWT.

        Returns:
            TokenPayload si valide, None sinon.
        """
        payload = self._decode(token)
        if not payload:
            return None

        if payload.get("type") != "access":
            return None

        return self._to_payload(payload)

    def verify_refresh_token(self, token: str) -> Optional[TokenPayload]:
        """
        Verifie un refresh token.

        Args:
            token: Token JWT.

        Returns:
            TokenPayload si valide, None sinon.
        """
        payload = self._decode(token)
        if not payload:
            return None

        if payload.get("type") != "refresh":
            return None

        return self._to_payload(payload)

    def _encode(self, payload: dict) -> str:
        """Encode un payload en JWT."""
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def _decode(self, token: str) -> Optional[dict]:
        """Decode un JWT, retourne None si invalide."""
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm]
            )
        except PyJWTError:
            return None

    def _to_payload(self, data: dict) -> TokenPayload:
        """Convertit un dict en TokenPayload."""
        return TokenPayload(
            user_id=UUID(data["sub"]),
            role=data["role"],
            token_type=data["type"],
            exp=datetime.fromtimestamp(data["exp"], tz=timezone.utc),
        )
