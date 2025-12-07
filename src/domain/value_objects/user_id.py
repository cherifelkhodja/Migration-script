"""
Value Object UserId - Identifiant utilisateur pour le multi-tenancy.

Le UserId est utilise pour l'isolation des donnees par utilisateur.
Chaque entite "tenant-aware" a un owner_id de type UserId.

Cas particulier:
----------------
SYSTEM_USER est un UserId special pour les operations systeme
et les donnees partagees (non liees a un utilisateur specifique).

Usage:
------
    >>> from src.domain.value_objects.user_id import UserId, SYSTEM_USER
    >>>
    >>> # Creation depuis UUID
    >>> user_id = UserId(uuid4())
    >>>
    >>> # Creation depuis string
    >>> user_id = UserId.from_string("550e8400-e29b-41d4-a716-446655440000")
    >>>
    >>> # Creation flexible
    >>> user_id = UserId.from_any(some_value)  # UUID, string, UserId, ou None
    >>>
    >>> # Verification systeme
    >>> if user_id.is_system:
    ...     print("Operation systeme")

Architecture:
-------------
Ce Value Object fait partie de la couche Domain et est utilise par:
- Les entites (Page, Collection, Favorite, etc.) via owner_id
- Les repositories pour filtrer les requetes
- Le TenantContext pour propager le contexte utilisateur
"""

from dataclasses import dataclass
from uuid import UUID


# UUID special pour les operations systeme (tous zeros)
_SYSTEM_UUID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True)
class UserId:
    """
    Identifiant utilisateur immutable.

    Value Object encapsulant un UUID utilisateur pour le multi-tenancy.
    Immutable et comparable par valeur.

    Attributes:
        value: UUID de l'utilisateur.

    Example:
        >>> user_id = UserId(uuid4())
        >>> user_id == UserId(user_id.value)
        True
    """

    value: UUID

    @classmethod
    def from_string(cls, uuid_str: str) -> "UserId":
        """
        Cree un UserId depuis une string UUID.

        Args:
            uuid_str: String au format UUID.

        Returns:
            Instance UserId.

        Raises:
            ValueError: Si la string n'est pas un UUID valide.
        """
        try:
            return cls(UUID(uuid_str))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"UUID invalide: {uuid_str}") from e

    @classmethod
    def from_any(cls, value) -> "UserId":
        """
        Cree un UserId depuis differents types.

        Accepte:
        - UUID: Utilise directement
        - str: Parse comme UUID
        - UserId: Retourne tel quel
        - None: Retourne SYSTEM_USER

        Args:
            value: Valeur a convertir.

        Returns:
            Instance UserId.

        Example:
            >>> UserId.from_any("550e8400-e29b-41d4-a716-446655440000")
            UserId(value=UUID('550e8400-e29b-41d4-a716-446655440000'))
            >>> UserId.from_any(None)
            UserId(value=UUID('00000000-0000-0000-0000-000000000000'))
        """
        if value is None:
            return SYSTEM_USER

        if isinstance(value, UserId):
            return value

        if isinstance(value, UUID):
            return cls(value)

        if isinstance(value, str):
            return cls.from_string(value)

        raise TypeError(f"Impossible de convertir {type(value)} en UserId")

    @property
    def is_system(self) -> bool:
        """
        True si c'est le SYSTEM_USER.

        Les entites avec owner_id=SYSTEM_USER sont considerees
        comme publiques/partagees.
        """
        return self.value == _SYSTEM_UUID

    def __str__(self) -> str:
        """Representation string (UUID)."""
        return str(self.value)

    def __repr__(self) -> str:
        """Representation debug."""
        if self.is_system:
            return "UserId(SYSTEM)"
        return f"UserId({self.value})"


# Constante pour les operations systeme
SYSTEM_USER = UserId(_SYSTEM_UUID)
