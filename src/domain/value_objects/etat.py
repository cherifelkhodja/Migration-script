"""
Value Object pour l'etat d'une page (basé sur le nombre d'annonces).
"""

from dataclasses import dataclass
from enum import Enum

from src.domain.exceptions import InvalidEtatError


class EtatLevel(Enum):
    """
    Niveaux d'etat possibles pour une page.

    Les niveaux representent l'activite publicitaire d'une page,
    base sur le nombre d'annonces actives.
    """

    XS = "XS"   # 1-9 annonces
    S = "S"     # 10-19 annonces
    M = "M"     # 20-34 annonces
    L = "L"     # 35-79 annonces
    XL = "XL"   # 80-149 annonces
    XXL = "XXL" # 150+ annonces


# Seuils par defaut pour chaque niveau
DEFAULT_THRESHOLDS: dict[EtatLevel, int] = {
    EtatLevel.XS: 1,
    EtatLevel.S: 10,
    EtatLevel.M: 20,
    EtatLevel.L: 35,
    EtatLevel.XL: 80,
    EtatLevel.XXL: 150,
}


@dataclass(frozen=True, slots=True)
class Etat:
    """
    Etat d'une page base sur son activite publicitaire.

    L'etat categorise les pages selon leur nombre d'annonces actives,
    de XS (peu actif) a XXL (tres actif).

    Attributes:
        level: Niveau d'etat (XS a XXL).
        ads_count: Nombre d'annonces utilisé pour determiner l'etat.

    Example:
        >>> etat = Etat.from_ads_count(50)
        >>> etat.level
        <EtatLevel.L: 'L'>
        >>> etat.is_large
        True
    """

    level: EtatLevel
    ads_count: int

    def __post_init__(self) -> None:
        """Valide l'etat apres initialisation."""
        if not isinstance(self.level, EtatLevel):
            raise InvalidEtatError(self.level)
        if self.ads_count < 0:
            raise InvalidEtatError(f"ads_count={self.ads_count}")

    @classmethod
    def from_ads_count(
        cls,
        ads_count: int,
        thresholds: dict[EtatLevel, int] | None = None
    ) -> "Etat":
        """
        Cree un Etat depuis un nombre d'annonces.

        Args:
            ads_count: Nombre d'annonces actives.
            thresholds: Seuils personnalises (optionnel).

        Returns:
            Etat correspondant au nombre d'annonces.

        Example:
            >>> Etat.from_ads_count(25)
            Etat(level=<EtatLevel.M: 'M'>, ads_count=25)
        """
        if ads_count < 0:
            ads_count = 0

        thresholds = thresholds or DEFAULT_THRESHOLDS

        # Parcourir du plus grand au plus petit
        for level in reversed(list(EtatLevel)):
            if ads_count >= thresholds[level]:
                return cls(level=level, ads_count=ads_count)

        # Par defaut, XS
        return cls(level=EtatLevel.XS, ads_count=ads_count)

    @classmethod
    def from_string(cls, value: str, ads_count: int = 0) -> "Etat":
        """
        Cree un Etat depuis une chaine.

        Args:
            value: Niveau sous forme de chaine (ex: "XL").
            ads_count: Nombre d'annonces (optionnel).

        Returns:
            Etat correspondant.

        Raises:
            InvalidEtatError: Si la valeur n'est pas reconnue.
        """
        try:
            level = EtatLevel(value.upper().strip())
            return cls(level=level, ads_count=ads_count)
        except ValueError:
            raise InvalidEtatError(value)

    @property
    def is_small(self) -> bool:
        """Retourne True si l'etat est petit (XS ou S)."""
        return self.level in (EtatLevel.XS, EtatLevel.S)

    @property
    def is_medium(self) -> bool:
        """Retourne True si l'etat est moyen (M)."""
        return self.level == EtatLevel.M

    @property
    def is_large(self) -> bool:
        """Retourne True si l'etat est grand (L, XL ou XXL)."""
        return self.level in (EtatLevel.L, EtatLevel.XL, EtatLevel.XXL)

    @property
    def is_extra_large(self) -> bool:
        """Retourne True si l'etat est tres grand (XL ou XXL)."""
        return self.level in (EtatLevel.XL, EtatLevel.XXL)

    def __str__(self) -> str:
        """Retourne la representation string de l'etat."""
        return self.level.value

    def __repr__(self) -> str:
        """Retourne la representation debug de l'etat."""
        return f"Etat(level={self.level}, ads_count={self.ads_count})"

    def __lt__(self, other: "Etat") -> bool:
        """Compare deux etats pour le tri."""
        order = list(EtatLevel)
        return order.index(self.level) < order.index(other.level)

    def __le__(self, other: "Etat") -> bool:
        """Compare deux etats pour le tri."""
        return self == other or self < other

    def __gt__(self, other: "Etat") -> bool:
        """Compare deux etats pour le tri."""
        return not self <= other

    def __ge__(self, other: "Etat") -> bool:
        """Compare deux etats pour le tri."""
        return not self < other
