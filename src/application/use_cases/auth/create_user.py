"""
CreateUserUseCase - Creation d'un nouvel utilisateur.

Responsabilite unique:
----------------------
Valider et creer un nouvel utilisateur.
Verifier l'unicite username/email.

Dependances:
------------
- UserRepository: Persister l'utilisateur
- AuditRepository: Logger la creation
"""

from dataclasses import dataclass
from typing import Optional

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository


@dataclass
class CreateUserRequest:
    """
    Requete de creation utilisateur.

    Attributes:
        username: Nom d'utilisateur (unique).
        email: Adresse email (unique).
        password: Mot de passe en clair.
        role: Role (admin, analyst, viewer).
        created_by_id: ID de l'admin createur.
    """
    username: str
    email: str
    password: str
    role: str = "viewer"
    created_by_id: Optional[str] = None


@dataclass
class CreateUserResponse:
    """
    Reponse de creation.

    Attributes:
        success: True si creation reussie.
        user: Utilisateur cree.
        error: Code erreur si echec.
    """
    success: bool
    user: Optional[User] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, user: User) -> "CreateUserResponse":
        """Factory pour succes."""
        return cls(success=True, user=user)

    @classmethod
    def fail(cls, error: str) -> "CreateUserResponse":
        """Factory pour echec."""
        return cls(success=False, error=error)


class CreateUserUseCase:
    """
    Use case de creation utilisateur.

    Valide les donnees et cree l'utilisateur.

    Example:
        >>> use_case = CreateUserUseCase(user_repo, audit_repo)
        >>> request = CreateUserRequest("john", "john@ex.com", "pass123")
        >>> response = use_case.execute(request)
        >>> if response.success:
        ...     print(f"Utilisateur {response.user.username} cree")
    """

    # Constantes de validation
    MIN_USERNAME_LENGTH = 3
    MIN_PASSWORD_LENGTH = 6

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

    def execute(self, request: CreateUserRequest) -> CreateUserResponse:
        """
        Execute la creation.

        Args:
            request: Requete avec donnees utilisateur.

        Returns:
            CreateUserResponse avec resultat.
        """
        # Valider les donnees
        error = self._validate(request)
        if error:
            return CreateUserResponse.fail(error)

        # Verifier unicite
        if self._user_repo.exists(request.username):
            return CreateUserResponse.fail("username_taken")

        if self._user_repo.get_by_email(request.email):
            return CreateUserResponse.fail("email_taken")

        # Creer l'utilisateur
        user = User.create(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role,
        )

        # Persister
        self._user_repo.save(user)

        # Logger
        self._audit_repo.log(
            user_id=None,
            username=request.created_by_id or "system",
            action="user_created",
            resource_type="user",
            resource_id=str(user.id),
            details={"username": user.username, "role": request.role},
        )

        return CreateUserResponse.ok(user)

    def _validate(self, request: CreateUserRequest) -> Optional[str]:
        """Valide les donnees."""
        if len(request.username) < self.MIN_USERNAME_LENGTH:
            return "username_too_short"

        if len(request.password) < self.MIN_PASSWORD_LENGTH:
            return "password_too_short"

        if "@" not in request.email:
            return "invalid_email"

        if request.role not in ("admin", "analyst", "viewer"):
            return "invalid_role"

        return None
