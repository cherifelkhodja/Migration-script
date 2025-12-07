"""
OAuthLoginUseCase - Authentification via OAuth.

Responsabilite unique:
----------------------
Gerer le flux complet OAuth: validation state, recuperation infos, creation/recherche user.

Patterns:
---------
- Use Case avec Request/Response
- Injection de dependances via constructeur
"""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from src.domain.entities.user import User
from src.domain.value_objects.role import Role
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository


@dataclass
class OAuthLoginRequest:
    """
    Requete de login OAuth.

    Attributes:
        provider: Nom du provider (google, github).
        provider_id: ID unique chez le provider.
        email: Email de l'utilisateur.
        name: Nom affiche (optionnel).
    """

    provider: str
    provider_id: str
    email: str
    name: Optional[str] = None


@dataclass
class OAuthLoginResponse:
    """
    Reponse de login OAuth.

    Attributes:
        success: True si authentification reussie.
        user: Utilisateur authentifie.
        is_new_user: True si l'utilisateur vient d'etre cree.
        error: Message d'erreur si echec.
    """

    success: bool
    user: Optional[User] = None
    is_new_user: bool = False
    error: Optional[str] = None

    @classmethod
    def ok(cls, user: User, is_new: bool = False) -> "OAuthLoginResponse":
        """Factory pour succes."""
        return cls(success=True, user=user, is_new_user=is_new)

    @classmethod
    def fail(cls, error: str) -> "OAuthLoginResponse":
        """Factory pour echec."""
        return cls(success=False, error=error)


class OAuthLoginUseCase:
    """
    Use case de login OAuth.

    Trouve ou cree un utilisateur a partir des infos OAuth.

    Example:
        >>> use_case = OAuthLoginUseCase(user_repo, audit_repo)
        >>> response = use_case.execute(OAuthLoginRequest(
        ...     provider="google",
        ...     provider_id="123",
        ...     email="user@gmail.com"
        ... ))
        >>> if response.success:
        ...     print(f"Bienvenue {response.user.username}")
    """

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
    ):
        """
        Initialise le use case.

        Args:
            user_repo: Repository utilisateurs (abstrait).
            audit_repo: Repository audit (abstrait).
        """
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, request: OAuthLoginRequest) -> OAuthLoginResponse:
        """
        Execute le login OAuth.

        Args:
            request: Requete avec infos provider.

        Returns:
            OAuthLoginResponse avec resultat.
        """
        if not request.email:
            return OAuthLoginResponse.fail("email_required")

        # Chercher un utilisateur existant par email
        existing_user = self._user_repo.get_by_email(request.email)

        if existing_user:
            self._log_login(existing_user, request.provider)
            return OAuthLoginResponse.ok(existing_user, is_new=False)

        # Creer un nouvel utilisateur
        new_user = self._create_user(request)
        self._log_registration(new_user, request.provider)

        return OAuthLoginResponse.ok(new_user, is_new=True)

    def _create_user(self, request: OAuthLoginRequest) -> User:
        """Cree un nouvel utilisateur OAuth."""
        username = self._generate_unique_username(request.email)

        user = User(
            id=uuid4(),
            username=username,
            email=request.email,
            password_hash="",  # OAuth users have no password
            role=Role.viewer(),
        )

        return self._user_repo.save(user)

    def _generate_unique_username(self, email: str) -> str:
        """Genere un username unique a partir de l'email."""
        base_username = email.split("@")[0]
        username = base_username
        counter = 1

        while self._user_repo.get_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        return username

    def _log_login(self, user: User, provider: str) -> None:
        """Log un login OAuth."""
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="oauth_login",
            details={"provider": provider},
        )

    def _log_registration(self, user: User, provider: str) -> None:
        """Log une creation d'utilisateur OAuth."""
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="oauth_registration",
            details={"provider": provider},
        )
