"""
Use Case: Detection des Winning Ads.
"""

from dataclasses import dataclass

from src.application.ports.repositories.winning_ad_repository import WinningAdRepository
from src.domain.entities.ad import Ad
from src.domain.entities.winning_ad import DEFAULT_WINNING_CRITERIA, WinningAd
from src.domain.services.winning_ad_detector import (
    WinningAdDetector,
)


@dataclass
class DetectWinningAdsRequest:
    """
    Requete de detection de winning ads.

    Attributes:
        ads: Liste des annonces a analyser.
        search_log_id: ID du log de recherche associe.
        custom_criteria: Criteres personnalises optionnels.
    """

    ads: list[Ad]
    search_log_id: int | None = None
    custom_criteria: list[tuple[int, int]] | None = None


@dataclass
class DetectWinningAdsResponse:
    """
    Reponse de la detection.

    Attributes:
        winning_ads: Liste des winning ads detectees.
        total_analyzed: Nombre d'annonces analysees.
        detection_rate: Taux de detection.
        criteria_distribution: Distribution par critere.
        saved_count: Nombre sauvegardees (si repository fourni).
        skipped_count: Nombre de doublons ignores.
    """

    winning_ads: list[WinningAd]
    total_analyzed: int
    detection_rate: float
    criteria_distribution: dict[str, int]
    saved_count: int = 0
    skipped_count: int = 0

    @property
    def count(self) -> int:
        return len(self.winning_ads)


class DetectWinningAdsUseCase:
    """
    Use Case: Detection des annonces performantes.

    Ce use case analyse les annonces pour identifier celles
    qui repondent aux criteres de performance (reach + recence).

    Example:
        >>> detector = DetectWinningAdsUseCase(winning_ad_repo)
        >>> request = DetectWinningAdsRequest(ads=my_ads)
        >>> response = detector.execute(request)
        >>> print(f"{response.count} winning ads detectees")
    """

    def __init__(
        self,
        winning_ad_repository: WinningAdRepository | None = None,
        criteria: list[tuple[int, int]] | None = None,
    ) -> None:
        """
        Initialise le use case.

        Args:
            winning_ad_repository: Repository pour sauvegarder les winning ads.
            criteria: Criteres par defaut.
        """
        self._repository = winning_ad_repository
        self._default_criteria = criteria or DEFAULT_WINNING_CRITERIA
        self._detector = WinningAdDetector(self._default_criteria)

    def execute(
        self,
        request: DetectWinningAdsRequest,
    ) -> DetectWinningAdsResponse:
        """
        Execute la detection des winning ads.

        Args:
            request: Requete avec les annonces a analyser.

        Returns:
            Reponse avec les winning ads detectees.
        """
        # Utiliser les criteres de la requete ou les criteres par defaut
        criteria = request.custom_criteria or self._default_criteria
        detector = WinningAdDetector(criteria)

        # Detecter les winning ads
        result = detector.detect_all(
            request.ads,
            search_log_id=request.search_log_id,
        )

        # Sauvegarder si repository disponible
        saved_count = 0
        skipped_count = 0

        if self._repository and result.winning_ads:
            saved_count, skipped_count = self._repository.save_many(result.winning_ads)

        return DetectWinningAdsResponse(
            winning_ads=result.winning_ads,
            total_analyzed=result.total_ads_analyzed,
            detection_rate=result.detection_rate,
            criteria_distribution=result.criteria_distribution,
            saved_count=saved_count,
            skipped_count=skipped_count,
        )

    def is_winning(self, ad: Ad) -> bool:
        """
        Verifie rapidement si une annonce est winning.

        Args:
            ad: Annonce a verifier.

        Returns:
            True si l'annonce est winning.
        """
        return self._detector.is_winning(ad)

    def explain(self, ad: Ad) -> str:
        """
        Explique pourquoi une annonce est ou n'est pas winning.

        Args:
            ad: Annonce a analyser.

        Returns:
            Explication textuelle.
        """
        return self._detector.explain(ad)

    def get_criteria(self) -> list[tuple[int, int]]:
        """Retourne les criteres utilises."""
        return self._default_criteria.copy()
