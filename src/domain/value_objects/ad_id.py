"""
Value Object pour l'identifiant d'une annonce Meta.
"""

from dataclasses import dataclass
from typing import Any

from src.domain.exceptions import InvalidAdIdError


@dataclass(frozen=True, slots=True)
class AdId:
    """
    Identifiant unique d'une annonce Meta Ads.

    Un AdId est une chaine representant l'identifiant unique
    d'une annonce dans l'archive Meta Ads.

    Attributes:
        value: Valeur de l'identifiant.

    Example:
        >>> ad_id = AdId("987654321")
        >>> str(ad_id)
        '987654321'
    """

    value: str

    def __post_init__(self) -> None:
        """Valide l'identifiant apres initialisation."""
        self._validate(self.value)

    @staticmethod
    def _validate(value: Any) -> None:
        """
        Valide que la valeur est un identifiant d'annonce valide.

        Args:
            value: Valeur a valider.

        Raises:
            InvalidAdIdError: Si la valeur n'est pas valide.
        """
        if value is None:
            raise InvalidAdIdError(value)

        str_value = str(value).strip()

        if not str_value:
            raise InvalidAdIdError(value)

    @classmethod
    def from_any(cls, value: Any) -> "AdId":
        """
        Cree un AdId depuis n'importe quelle valeur.

        Args:
            value: Valeur a convertir (str, int, etc.).

        Returns:
            AdId valide.

        Raises:
            InvalidAdIdError: Si la conversion echoue.
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
        return f"AdId('{self.value}')"

    def __hash__(self) -> int:
        """Retourne le hash pour utilisation dans sets/dicts."""
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        """Compare deux AdId par valeur."""
        if isinstance(other, AdId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False
