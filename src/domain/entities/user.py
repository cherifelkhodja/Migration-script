"""
Entite User - Utilisateur de l'application.

Represente un utilisateur avec son role et ses permissions.
Gere l'authentification et l'autorisation.

Attributes:
-----------
- id: Identifiant unique UUID
- username: Nom d'utilisateur unique
- email: Adresse email
- password_hash: Hash bcrypt du mot de passe
- role: Role et permissions (admin, analyst, viewer)
- is_active: Compte actif ou desactive
- created_at: Date de creation
- last_login: Derniere connexion

Securite:
---------
- Mots de passe hashes avec bcrypt (work factor 12)
- Tokens de session avec expiration
- Verrouillage apres 5 tentatives echouees

Multi-tenancy:
--------------
Chaque utilisateur a son propre espace de donnees.
Les pages, favoris, collections sont lies a user_id.
Les admins peuvent voir toutes les donnees.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.role import Role, RoleLevel


@dataclass
class User:
    """
    Utilisateur de l'application.

    Entite principale pour l'authentification et l'autorisation.
    Contient les informations de profil et le role.

    Attributes:
        id: Identifiant unique UUID.
        username: Nom d'utilisateur (unique, login).
        email: Adresse email.
        password_hash: Hash du mot de passe (bcrypt).
        role: Role avec permissions.
        is_active: True si le compte est actif.
        created_at: Date de creation du compte.
        updated_at: Date de derniere modification.
        last_login: Date de derniere connexion.
        failed_attempts: Nombre de tentatives de connexion echouees.
        locked_until: Date jusqu'a laquelle le compte est verrouille.

    Example:
        >>> user = User.create(
        ...     username="john",
        ...     email="john@example.com",
        ...     password="secret123",
        ...     role="analyst"
        ... )
        >>> user.verify_password("secret123")
        True
        >>> user.role.can("search")
        True
    """

    id: UUID
    username: str
    email: str
    password_hash: str
    role: Role
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None

    # Constantes
    MAX_FAILED_ATTEMPTS = 5
    LOCK_DURATION_MINUTES = 15

    @classmethod
    def create(
        cls,
        username: str,
        email: str,
        password: str,
        role: str = "viewer"
    ) -> "User":
        """
        Factory pour creer un nouvel utilisateur.

        Args:
            username: Nom d'utilisateur (unique).
            email: Adresse email.
            password: Mot de passe en clair (sera hashe).
            role: Nom du role (admin, analyst, viewer).

        Returns:
            Nouvelle instance User avec mot de passe hashe.

        Example:
            >>> user = User.create("john", "john@ex.com", "pass123", "analyst")
        """
        return cls(
            id=uuid4(),
            username=username.strip().lower(),
            email=email.strip().lower(),
            password_hash=cls._hash_password(password),
            role=Role.from_string(role),
        )

    @classmethod
    def create_admin(cls, username: str, email: str, password: str) -> "User":
        """Cree un utilisateur administrateur."""
        return cls.create(username, email, password, role="admin")

    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash un mot de passe avec bcrypt.

        Args:
            password: Mot de passe en clair.

        Returns:
            Hash bcrypt du mot de passe.
        """
        try:
            import bcrypt
            salt = bcrypt.gensalt(rounds=12)
            return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        except ImportError:
            # Fallback si bcrypt non installe (dev only)
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """
        Verifie un mot de passe contre le hash stocke.

        Args:
            password: Mot de passe a verifier.

        Returns:
            True si le mot de passe est correct.
        """
        try:
            import bcrypt
            return bcrypt.checkpw(
                password.encode('utf-8'),
                self.password_hash.encode('utf-8')
            )
        except ImportError:
            # Fallback SHA256
            import hashlib
            return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    def update_password(self, new_password: str) -> None:
        """
        Met a jour le mot de passe.

        Args:
            new_password: Nouveau mot de passe en clair.
        """
        self.password_hash = self._hash_password(new_password)
        self.updated_at = datetime.now()

    def record_login(self) -> None:
        """Enregistre une connexion reussie."""
        self.last_login = datetime.now()
        self.failed_attempts = 0
        self.locked_until = None

    def record_failed_login(self) -> None:
        """
        Enregistre une tentative de connexion echouee.

        Verrouille le compte apres MAX_FAILED_ATTEMPTS.
        """
        from datetime import timedelta

        self.failed_attempts += 1
        if self.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = datetime.now() + timedelta(
                minutes=self.LOCK_DURATION_MINUTES
            )

    @property
    def is_locked(self) -> bool:
        """True si le compte est verrouille."""
        if self.locked_until is None:
            return False
        return datetime.now() < self.locked_until

    @property
    def can_login(self) -> bool:
        """True si l'utilisateur peut se connecter."""
        return self.is_active and not self.is_locked

    def unlock(self) -> None:
        """Deverrouille le compte."""
        self.failed_attempts = 0
        self.locked_until = None
        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        """Desactive le compte."""
        self.is_active = False
        self.updated_at = datetime.now()

    def activate(self) -> None:
        """Active le compte."""
        self.is_active = True
        self.updated_at = datetime.now()

    def change_role(self, new_role: str) -> None:
        """
        Change le role de l'utilisateur.

        Args:
            new_role: Nouveau role (admin, analyst, viewer).
        """
        self.role = Role.from_string(new_role)
        self.updated_at = datetime.now()

    # Delegations vers Role
    def can(self, permission: str) -> bool:
        """Verifie une permission."""
        return self.role.can(permission)

    def can_access_page(self, page_name: str) -> bool:
        """Verifie l'acces a une page."""
        return self.role.can_access_page(page_name)

    @property
    def is_admin(self) -> bool:
        """True si administrateur."""
        return self.role.is_admin

    @property
    def display_name(self) -> str:
        """Nom affichable (username capitalise)."""
        return self.username.capitalize()

    def __eq__(self, other: object) -> bool:
        """Compare par ID."""
        if isinstance(other, User):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash base sur l'ID."""
        return hash(self.id)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"

    def __repr__(self) -> str:
        return f"User(id={self.id}, username='{self.username}', role={self.role})"
