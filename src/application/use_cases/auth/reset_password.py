"""
ResetPasswordUseCase - Reinitialisation du mot de passe.

Responsabilite unique:
----------------------
Valider le token et changer le mot de passe.

Flow:
-----
1. Verifier que le token existe et n'est pas expire
2. Recuperer l'utilisateur associe
3. Valider le nouveau mot de passe
4. Mettre a jour le mot de passe (hash bcrypt)
5. Invalider le token (usage unique)
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository
from src.domain.ports.state_storage import StateStorage


@dataclass
class ResetPasswordRequest:
    """
    Requete de reset de mot de passe.

    Attributes:
        token: Token de reset recu par email.
        new_password: Nouveau mot de passe.
    """

    token: str
    new_password: str


@dataclass
class ResetPasswordResponse:
    """
    Reponse de reset de mot de passe.

    Attributes:
        success: True si reset reussi.
        error: Code erreur si echec.
    """

    success: bool
    error: Optional[str] = None

    @classmethod
    def ok(cls) -> "ResetPasswordResponse":
        """Factory pour succes."""
        return cls(success=True)

    @classmethod
    def fail(cls, error: str) -> "ResetPasswordResponse":
        """Factory pour echec."""
        return cls(success=False, error=error)


class ResetPasswordUseCase:
    """
    Use case de reinitialisation de mot de passe.

    Valide le token et change le mot de passe.

    Example:
        >>> use_case = ResetPasswordUseCase(user_repo, state_storage, audit_repo)
        >>> response = use_case.execute(ResetPasswordRequest(
        ...     token="abc123",
        ...     new_password="NewSecureP@ss123"
        ... ))
        >>> if response.success:
        ...     print("Mot de passe change!")
    """

    MIN_PASSWORD_LENGTH = 8

    def __init__(
        self,
        user_repo: UserRepository,
        state_storage: StateStorage,
        audit_repo: AuditRepository,
    ):
        """
        Initialise le use case.

        Args:
            user_repo: Repository utilisateurs.
            state_storage: Stockage des tokens temporaires.
            audit_repo: Repository audit.
        """
        self._user_repo = user_repo
        self._state_storage = state_storage
        self._audit_repo = audit_repo

    def execute(self, request: ResetPasswordRequest) -> ResetPasswordResponse:
        """
        Execute le reset de mot de passe.

        Args:
            request: Requete avec token et nouveau mot de passe.

        Returns:
            ResetPasswordResponse avec resultat.
        """
        # 1. Valider le nouveau mot de passe
        validation_error = self._validate_password(request.new_password)
        if validation_error:
            return ResetPasswordResponse.fail(validation_error)

        # 2. Verifier le token
        user_id_str = self._state_storage.get(f"password_reset:{request.token}")

        if not user_id_str:
            self._log_invalid_token(request.token)
            return ResetPasswordResponse.fail("invalid_or_expired_token")

        # 3. Recuperer l'utilisateur
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            return ResetPasswordResponse.fail("invalid_token_data")

        user = self._user_repo.get_by_id(user_id)

        if not user:
            return ResetPasswordResponse.fail("user_not_found")

        if not user.is_active:
            return ResetPasswordResponse.fail("account_inactive")

        # 4. Changer le mot de passe
        user.update_password(request.new_password)

        # 5. Reset compteur de tentatives echouees
        user.failed_login_attempts = 0
        user.locked_until = None

        # 6. Sauvegarder
        self._user_repo.save(user)

        # 7. Invalider le token (usage unique)
        self._state_storage.delete(f"password_reset:{request.token}")

        # 8. Log
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="password_reset_completed",
            details={},
        )

        return ResetPasswordResponse.ok()

    def _validate_password(self, password: str) -> Optional[str]:
        """
        Valide le mot de passe.

        Args:
            password: Mot de passe a valider.

        Returns:
            Code erreur si invalide, None si valide.
        """
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return "password_too_short"

        # Au moins une lettre et un chiffre
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not has_letter or not has_digit:
            return "password_too_weak"

        return None

    def _log_invalid_token(self, token: str) -> None:
        """Log une tentative avec token invalide."""
        self._audit_repo.log(
            user_id=None,
            username="unknown",
            action="password_reset_invalid_token",
            details={"token_prefix": token[:8] if len(token) >= 8 else token},
        )
