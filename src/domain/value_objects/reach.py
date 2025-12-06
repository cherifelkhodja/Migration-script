"""
Value Object pour la portee (reach) d'une annonce.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True, slots=True)
class Reach:
    """
    Portee estimee d'une annonce Meta.

    La portee represente le nombre estime de personnes uniques
    qui ont vu l'annonce.

    Attributes:
        value: Portee estimee (nombre de personnes).
        lower_bound: Borne inferieure de l'estimation (optionnel).
        upper_bound: Borne superieure de l'estimation (optionnel).

    Example:
        >>> reach = Reach(50000)
        >>> reach.is_significant
        True
        >>> reach.format()
        '50K'
    """

    value: int
    lower_bound: Optional[int] = None
    upper_bound: Optional[int] = None

    def __post_init__(self) -> None:
        """Valide la portee apres initialisation."""
        if self.value < 0:
            object.__setattr__(self, "value", 0)

    @classmethod
    def from_meta_response(
        cls,
        eu_total_reach: Optional[dict]
    ) -> "Reach":
        """
        Cree un Reach depuis une reponse Meta API.

        Args:
            eu_total_reach: Dictionnaire eu_total_reach de l'API Meta.

        Returns:
            Reach avec les valeurs extraites.

        Example:
            >>> data = {"lower_bound": 1000, "upper_bound": 5000}
            >>> Reach.from_meta_response(data)
            Reach(value=3000, lower_bound=1000, upper_bound=5000)
        """
        if not eu_total_reach:
            return cls(value=0)

        if isinstance(eu_total_reach, (int, float)):
            return cls(value=int(eu_total_reach))

        lower = eu_total_reach.get("lower_bound", 0)
        upper = eu_total_reach.get("upper_bound", 0)

        if isinstance(lower, str):
            lower = int(lower) if lower.isdigit() else 0
        if isinstance(upper, str):
            upper = int(upper) if upper.isdigit() else 0

        # Utiliser la moyenne comme valeur principale
        if lower and upper:
            value = (lower + upper) // 2
        else:
            value = upper or lower

        return cls(value=value, lower_bound=lower or None, upper_bound=upper or None)

    @classmethod
    def zero(cls) -> "Reach":
        """Factory pour creer un reach nul."""
        return cls(value=0)

    @property
    def is_zero(self) -> bool:
        """Retourne True si la portee est nulle."""
        return self.value == 0

    @property
    def is_significant(self) -> bool:
        """Retourne True si la portee est significative (>= 1000)."""
        return self.value >= 1000

    @property
    def is_high(self) -> bool:
        """Retourne True si la portee est elevee (>= 10000)."""
        return self.value >= 10000

    @property
    def is_very_high(self) -> bool:
        """Retourne True si la portee est tres elevee (>= 100000)."""
        return self.value >= 100000

    @property
    def range(self) -> Optional[Tuple[int, int]]:
        """Retourne la plage (lower, upper) si disponible."""
        if self.lower_bound is not None and self.upper_bound is not None:
            return (self.lower_bound, self.upper_bound)
        return None

    def format(self, precision: int = 0) -> str:
        """
        Formate la portee en format lisible.

        Args:
            precision: Nombre de decimales (0 par defaut).

        Returns:
            Chaine formatee (ex: "50K", "1.5M").

        Example:
            >>> Reach(1500000).format()
            '1.5M'
            >>> Reach(50000).format()
            '50K'
        """
        if self.value >= 1_000_000:
            val = self.value / 1_000_000
            suffix = "M"
        elif self.value >= 1_000:
            val = self.value / 1_000
            suffix = "K"
        else:
            return str(self.value)

        if precision == 0:
            # Afficher la decimale seulement si necessaire
            if val == int(val):
                return f"{int(val)}{suffix}"
            return f"{val:.1f}{suffix}"

        return f"{val:.{precision}f}{suffix}"

    def format_range(self) -> str:
        """
        Formate la plage de portee.

        Returns:
            Chaine formatee (ex: "10K - 50K").
        """
        if self.range:
            lower_fmt = Reach(self.lower_bound).format()
            upper_fmt = Reach(self.upper_bound).format()
            return f"{lower_fmt} - {upper_fmt}"
        return self.format()

    def __int__(self) -> int:
        """Conversion en int."""
        return self.value

    def __str__(self) -> str:
        """Retourne la representation formatee."""
        return self.format()

    def __repr__(self) -> str:
        """Retourne la representation debug."""
        if self.range:
            return f"Reach({self.value}, range={self.range})"
        return f"Reach({self.value})"

    def __lt__(self, other: "Reach") -> bool:
        """Compare deux portees."""
        if isinstance(other, Reach):
            return self.value < other.value
        return self.value < other

    def __le__(self, other: "Reach") -> bool:
        """Compare deux portees."""
        if isinstance(other, Reach):
            return self.value <= other.value
        return self.value <= other

    def __gt__(self, other: "Reach") -> bool:
        """Compare deux portees."""
        if isinstance(other, Reach):
            return self.value > other.value
        return self.value > other

    def __ge__(self, other: "Reach") -> bool:
        """Compare deux portees."""
        if isinstance(other, Reach):
            return self.value >= other.value
        return self.value >= other

    def __add__(self, other: "Reach") -> "Reach":
        """Additionne deux portees."""
        if isinstance(other, Reach):
            return Reach(self.value + other.value)
        return Reach(self.value + other)
