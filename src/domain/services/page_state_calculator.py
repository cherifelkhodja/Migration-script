"""
Service de calcul de l'etat des pages.
"""

from dataclasses import dataclass

from src.domain.entities.page import Page
from src.domain.value_objects.etat import DEFAULT_THRESHOLDS, Etat, EtatLevel


@dataclass
class PageStateStatistics:
    """
    Statistiques sur la distribution des etats.

    Attributes:
        distribution: Nombre de pages par etat.
        total_pages: Nombre total de pages.
        total_ads: Nombre total d'annonces.
    """

    distribution: dict[EtatLevel, int]
    total_pages: int
    total_ads: int

    @property
    def average_ads_per_page(self) -> float:
        """Moyenne d'annonces par page."""
        if self.total_pages == 0:
            return 0.0
        return self.total_ads / self.total_pages

    def percentage(self, level: EtatLevel) -> float:
        """Pourcentage de pages dans un etat donne."""
        if self.total_pages == 0:
            return 0.0
        return (self.distribution.get(level, 0) / self.total_pages) * 100

    def to_dict(self) -> dict[str, int]:
        """Convertit en dictionnaire avec les labels."""
        return {
            level.value: count
            for level, count in self.distribution.items()
        }


class PageStateCalculator:
    """
    Service de calcul et d'analyse des etats de pages.

    Ce service calcule l'etat des pages en fonction du nombre
    d'annonces actives et fournit des statistiques.

    Example:
        >>> calculator = PageStateCalculator()
        >>> etat = calculator.calculate(50)
        >>> etat.level
        <EtatLevel.L: 'L'>
    """

    def __init__(
        self,
        thresholds: dict[EtatLevel, int] | None = None
    ) -> None:
        """
        Initialise le calculateur.

        Args:
            thresholds: Seuils personnalises {EtatLevel: min_ads}.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def calculate(self, ads_count: int) -> Etat:
        """
        Calcule l'etat pour un nombre d'annonces.

        Args:
            ads_count: Nombre d'annonces actives.

        Returns:
            Etat correspondant.
        """
        return Etat.from_ads_count(ads_count, self.thresholds)

    def calculate_for_page(self, page: Page) -> Etat:
        """
        Calcule l'etat pour une page.

        Args:
            page: Page a evaluer.

        Returns:
            Etat de la page.
        """
        return self.calculate(page.active_ads_count)

    def get_statistics(self, pages: list[Page]) -> PageStateStatistics:
        """
        Calcule les statistiques pour une liste de pages.

        Args:
            pages: Liste de pages.

        Returns:
            Statistiques de distribution.
        """
        distribution = dict.fromkeys(EtatLevel, 0)
        total_ads = 0

        for page in pages:
            etat = page.etat or self.calculate_for_page(page)
            distribution[etat.level] += 1
            total_ads += page.active_ads_count

        return PageStateStatistics(
            distribution=distribution,
            total_pages=len(pages),
            total_ads=total_ads,
        )

    def filter_by_state(
        self,
        pages: list[Page],
        states: list[EtatLevel]
    ) -> list[Page]:
        """
        Filtre les pages par etat.

        Args:
            pages: Liste de pages.
            states: Etats a inclure.

        Returns:
            Pages filtrees.
        """
        return [
            page for page in pages
            if page.etat and page.etat.level in states
        ]

    def filter_minimum_state(
        self,
        pages: list[Page],
        minimum: EtatLevel
    ) -> list[Page]:
        """
        Filtre les pages avec un etat minimum.

        Args:
            pages: Liste de pages.
            minimum: Etat minimum requis.

        Returns:
            Pages avec etat >= minimum.
        """
        min_index = list(EtatLevel).index(minimum)
        return [
            page for page in pages
            if page.etat and list(EtatLevel).index(page.etat.level) >= min_index
        ]

    def get_threshold(self, level: EtatLevel) -> int:
        """
        Retourne le seuil pour un niveau donne.

        Args:
            level: Niveau d'etat.

        Returns:
            Seuil minimum d'annonces.
        """
        return self.thresholds.get(level, 0)

    def get_threshold_range(self, level: EtatLevel) -> tuple:
        """
        Retourne la plage de valeurs pour un niveau.

        Args:
            level: Niveau d'etat.

        Returns:
            Tuple (min, max) ou max peut etre None pour XXL.
        """
        levels = list(EtatLevel)
        index = levels.index(level)
        min_val = self.thresholds[level]

        if index < len(levels) - 1:
            next_level = levels[index + 1]
            max_val = self.thresholds[next_level] - 1
        else:
            max_val = None  # Pas de limite superieure pour XXL

        return (min_val, max_val)

    def describe_thresholds(self) -> str:
        """
        Retourne une description textuelle des seuils.

        Returns:
            Description formatee.
        """
        lines = ["Seuils d'etat:"]
        for level in EtatLevel:
            min_val, max_val = self.get_threshold_range(level)
            if max_val:
                lines.append(f"  {level.value}: {min_val}-{max_val} ads")
            else:
                lines.append(f"  {level.value}: {min_val}+ ads")
        return "\n".join(lines)
