"""
Service de detection des Winning Ads.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple, Iterator

from src.domain.entities.ad import Ad
from src.domain.entities.winning_ad import WinningAd, DEFAULT_WINNING_CRITERIA


@dataclass
class WinningAdDetectionResult:
    """
    Resultat de la detection de winning ads.

    Attributes:
        winning_ads: Liste des winning ads detectees.
        total_ads_analyzed: Nombre total d'annonces analysees.
        detection_rate: Taux de detection (winning/total).
        criteria_distribution: Distribution par critere.
    """

    winning_ads: List[WinningAd]
    total_ads_analyzed: int
    criteria_distribution: dict

    @property
    def count(self) -> int:
        """Nombre de winning ads detectees."""
        return len(self.winning_ads)

    @property
    def detection_rate(self) -> float:
        """Taux de detection."""
        if self.total_ads_analyzed == 0:
            return 0.0
        return self.count / self.total_ads_analyzed

    def by_criteria(self, criteria: str) -> List[WinningAd]:
        """Retourne les winning ads pour un critere donne."""
        return [w for w in self.winning_ads if w.matched_criteria == criteria]


class WinningAdDetector:
    """
    Service de detection des annonces performantes.

    Ce service analyse les annonces et identifie celles qui
    repondent aux criteres de performance (reach eleve + recence).

    Example:
        >>> detector = WinningAdDetector()
        >>> result = detector.detect_all(ads)
        >>> print(f"{result.count} winning ads trouvees")
    """

    def __init__(
        self,
        criteria: Optional[List[Tuple[int, int]]] = None
    ) -> None:
        """
        Initialise le detecteur.

        Args:
            criteria: Criteres personnalises [(max_age, min_reach), ...].
                     Utilise les criteres par defaut si non fourni.
        """
        self.criteria = criteria or DEFAULT_WINNING_CRITERIA

    def detect(
        self,
        ad: Ad,
        reference_date: Optional[date] = None,
        search_log_id: Optional[int] = None,
    ) -> Optional[WinningAd]:
        """
        Detecte si une annonce est une winning ad.

        Args:
            ad: Annonce a evaluer.
            reference_date: Date de reference pour l'age.
            search_log_id: ID du log de recherche.

        Returns:
            WinningAd si qualifiee, None sinon.
        """
        return WinningAd.detect(
            ad,
            criteria=self.criteria,
            reference_date=reference_date,
            search_log_id=search_log_id,
        )

    def detect_all(
        self,
        ads: List[Ad],
        reference_date: Optional[date] = None,
        search_log_id: Optional[int] = None,
    ) -> WinningAdDetectionResult:
        """
        Detecte toutes les winning ads dans une liste.

        Args:
            ads: Liste d'annonces a analyser.
            reference_date: Date de reference.
            search_log_id: ID du log de recherche.

        Returns:
            Resultat complet de la detection.
        """
        winning_ads = []
        criteria_dist = {}

        for ad in ads:
            winning = self.detect(ad, reference_date, search_log_id)
            if winning:
                winning_ads.append(winning)
                criteria = winning.matched_criteria
                criteria_dist[criteria] = criteria_dist.get(criteria, 0) + 1

        return WinningAdDetectionResult(
            winning_ads=winning_ads,
            total_ads_analyzed=len(ads),
            criteria_distribution=criteria_dist,
        )

    def detect_iter(
        self,
        ads: Iterator[Ad],
        reference_date: Optional[date] = None,
    ) -> Iterator[WinningAd]:
        """
        Detecte les winning ads de maniere iterative (lazy).

        Args:
            ads: Iterateur d'annonces.
            reference_date: Date de reference.

        Yields:
            WinningAd pour chaque annonce qualifiee.
        """
        for ad in ads:
            winning = self.detect(ad, reference_date)
            if winning:
                yield winning

    def is_winning(self, ad: Ad, reference_date: Optional[date] = None) -> bool:
        """
        Verifie rapidement si une annonce est winning.

        Args:
            ad: Annonce a verifier.
            reference_date: Date de reference.

        Returns:
            True si l'annonce est qualifiee.
        """
        return self.detect(ad, reference_date) is not None

    def get_applicable_criteria(self, ad: Ad) -> List[str]:
        """
        Retourne tous les criteres applicables a une annonce.

        Args:
            ad: Annonce a evaluer.

        Returns:
            Liste des criteres valides pour cette annonce.
        """
        if not ad.creation_date:
            return []

        age_days = ad.age_days
        reach = ad.reach.value
        applicable = []

        for max_age, min_reach in self.criteria:
            if age_days <= max_age and reach >= min_reach:
                applicable.append(f"{max_age}d/{min_reach // 1000}k")

        return applicable

    def explain(self, ad: Ad) -> str:
        """
        Explique pourquoi une annonce est ou n'est pas winning.

        Args:
            ad: Annonce a analyser.

        Returns:
            Explication textuelle.
        """
        if not ad.creation_date:
            return "Date de creation inconnue - impossible d'evaluer"

        age = ad.age_days
        reach = ad.reach.value

        winning = self.detect(ad)
        if winning:
            return (
                f"WINNING: Age {age}j, Reach {reach:,} "
                f"- Critere {winning.matched_criteria}"
            )

        # Trouver le critere le plus proche
        closest = None
        closest_gap = float("inf")

        for max_age, min_reach in self.criteria:
            if age <= max_age:
                gap = min_reach - reach
                if 0 < gap < closest_gap:
                    closest = (max_age, min_reach)
                    closest_gap = gap

        if closest:
            return (
                f"NON WINNING: Age {age}j, Reach {reach:,}. "
                f"Manque {closest_gap:,} reach pour critere "
                f"{closest[0]}d/{closest[1] // 1000}k"
            )

        return f"NON WINNING: Age {age}j trop eleve pour les criteres disponibles"
