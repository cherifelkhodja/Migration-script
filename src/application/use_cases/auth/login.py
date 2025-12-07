"""
LoginUseCase - Authentification d'un utilisateur.

Responsabilite unique:
----------------------
Verifier les credentials et retourner l'utilisateur si valide.
Gere le verrouillage apres echecs multiples.

Dependances:
------------
- UserRepository: Recuperer l'utilisateur
- AuditRepository: Logger les tentatives
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository


@dataclass
class LoginRequest:
    """
    Requete de login.

    Attributes:
        username: Username ou email.
        password: Mot de passe en clair.
        ip_address: Adresse IP (pour audit).
    """
    username: str
    password: str
    ip_address: Optional[str] = None


@dataclass
class LoginResponse:
    """
    Reponse de login.

    Attributes:
        success: True si authentification reussie.
        user: Utilisateur si succes.
        error: Code erreur si echec.
    """
    success: bool
    user: Optional[User] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, user: User) -> "LoginResponse":
        """Factory pour succes."""
        return cls(success=True, user=user)

    @classmethod
    def fail(cls, error: str) -> "LoginResponse":
        """Factory pour echec."""
        return cls(success=False, error=error)


class LoginUseCase:
    """
    Use case d'authentification.

    Verifie les credentials et gere les echecs.

    Example:
        >>> use_case = LoginUseCase(user_repo, audit_repo)
        >>> response = use_case.execute(LoginRequest("john", "pass"))
        >>> if response.success:
        ...     print(f"Bienvenue {response.user.username}")
    """

    # Constantes
    MAX_ATTEMPTS = 5
    LOCK_MINUTES = 15

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
    ):
        """
        Initialise le use case.

        Args:
            user_repo: Repository utilisateurs.
            audit_repo: Repository audit.
        """
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, request: LoginRequest) -> LoginResponse:
        """
        Execute l'authentification.

        Args:
            request: Requete avec credentials.

        Returns:
            LoginResponse avec resultat.
        """
        # Chercher l'utilisateur (par username ou email)
        user = self._find_user(request.username)

        if not user:
            self._log_failure(None, request, "user_not_found")
            return LoginResponse.fail("invalid_credentials")

        # Verifier compte actif
        if not user.is_active:
            self._log_failure(user, request, "account_inactive")
            return LoginResponse.fail("account_inactive")

        # Verifier verrouillage
        if user.is_locked:
            self._log_failure(user, request, "account_locked")
            return LoginResponse.fail("account_locked")

        # Verifier mot de passe
        if not user.verify_password(request.password):
            self._handle_failed_attempt(user, request)
            return LoginResponse.fail("invalid_credentials")

        # Succes
        user.record_login()
        self._user_repo.save(user)
        self._log_success(user, request)

        return LoginResponse.ok(user)

    def _find_user(self, identifier: str) -> Optional[User]:
        """Cherche par username ou email."""
        user = self._user_repo.get_by_username(identifier)
        if not user:
            user = self._user_repo.get_by_email(identifier)
        return user

    def _handle_failed_attempt(
        self,
        user: User,
        request: LoginRequest
    ) -> None:
        """Gere une tentative echouee."""
        user.record_failed_login()
        self._user_repo.save(user)
        self._log_failure(user, request, "wrong_password")

    def _log_success(self, user: User, request: LoginRequest) -> None:
        """Log un succes."""
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="login_success",
            ip_address=request.ip_address,
        )

    def _log_failure(
        self,
        user: Optional[User],
        request: LoginRequest,
        reason: str
    ) -> None:
        """Log un echec."""
        self._audit_repo.log(
            user_id=user.id if user else None,
            username=user.username if user else request.username,
            action="login_failed",
            details={"reason": reason},
            ip_address=request.ip_address,
        )
