"""
Value Object pour l'identifiant d'une page Facebook.
"""

from dataclasses import dataclass
from typing import Any

from src.domain.exceptions import InvalidPageIdError


@dataclass(frozen=True, slots=True)
class PageId:
    """
    Identifiant unique d'une page Facebook.

    Un PageId est une chaine representant un identifiant numerique
    attribue par Facebook a chaque page.

    Attributes:
        value: Valeur de l'identifiant (chaine numerique).

    Example:
        >>> page_id = PageId("123456789")
        >>> str(page_id)
        '123456789'
    """

    value: str

    def __post_init__(self) -> None:
        """Valide l'identifiant apres initialisation."""
        self._validate(self.value)

    @staticmethod
    def _validate(value: Any) -> None:
        """
        Valide que la valeur est un identifiant de page valide.

        Args:
            value: Valeur a valider.

        Raises:
            InvalidPageIdError: Si la valeur n'est pas valide.
        """
        if value is None:
            raise InvalidPageIdError(value)

        str_value = str(value).strip()

        if not str_value:
            raise InvalidPageIdError(value)

        # Doit etre numerique (Facebook IDs sont des entiers)
        if not str_value.isdigit():
            raise InvalidPageIdError(value)

    @classmethod
    def from_any(cls, value: Any) -> "PageId":
        """
        Cree un PageId depuis n'importe quelle valeur.

        Args:
            value: Valeur a convertir (str, int, etc.).

        Returns:
            PageId valide.

        Raises:
            InvalidPageIdError: Si la conversion echoue.
        """
        if isinstance(value, cls):
            return value

        str_value = str(value).strip() if value is not None else ""
        return cls(str_value)

    def __str__(self) -> str:
        """Retourne la representation string de l'ID."""
        return self.value

    def __repr__(self) -> str:
        """Retourne la representation debug de l'ID."""
        return f"PageId('{self.value}')"

    def __hash__(self) -> int:
        """Retourne le hash pour utilisation dans sets/dicts."""
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        """Compare deux PageId par valeur."""
        if isinstance(other, PageId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False
