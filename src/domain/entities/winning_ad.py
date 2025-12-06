"""
Entite WinningAd - Annonce performante.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.domain.entities.ad import Ad
from src.domain.value_objects import AdId, PageId, Reach

# Criteres par defaut pour qualifier une "Winning Ad"
# Format: (max_age_days, min_reach)
DEFAULT_WINNING_CRITERIA: list[tuple[int, int]] = [
    (4, 15000),    # <= 4 jours et > 15k reach
    (5, 20000),    # <= 5 jours et > 20k reach
    (6, 30000),    # <= 6 jours et > 30k reach
    (7, 40000),    # <= 7 jours et > 40k reach
    (8, 50000),    # <= 8 jours et > 50k reach
    (15, 100000),  # <= 15 jours et > 100k reach
    (22, 200000),  # <= 22 jours et > 200k reach
    (29, 400000),  # <= 29 jours et > 400k reach
]


@dataclass
class WinningAd:
    """
    Annonce performante identifiee comme "gagnante".

    Une WinningAd est une annonce qui remplit des criteres
    de performance (reach eleve par rapport a son age).
    Ces annonces sont particulierement interessantes pour
    l'analyse des tendances publicitaires.

    Attributes:
        ad: L'annonce source.
        matched_criteria: Le critere qui a ete valide.
        detected_at: Date de detection comme winning.
        reach_at_detection: Reach au moment de la detection.
        search_log_id: ID du log de recherche associe.

    Example:
        >>> ad = Ad(...)  # Annonce avec 50k reach et 3 jours
        >>> winning = WinningAd.detect(ad)
        >>> winning is not None
        True
        >>> winning.matched_criteria
        '4d/15k'
    """

    ad: Ad
    matched_criteria: str
    detected_at: datetime = field(default_factory=datetime.now)
    reach_at_detection: int = 0
    search_log_id: int | None = None

    def __post_init__(self) -> None:
        """Initialise les champs calcules."""
        if self.reach_at_detection == 0:
            self.reach_at_detection = self.ad.reach.value

    @classmethod
    def detect(
        cls,
        ad: Ad,
        criteria: list[tuple[int, int]] | None = None,
        reference_date: date | None = None,
        search_log_id: int | None = None,
    ) -> Optional["WinningAd"]:
        """
        Detecte si une annonce est une Winning Ad.

        Args:
            ad: Annonce a evaluer.
            criteria: Criteres personnalises (optionnel).
            reference_date: Date de reference pour le calcul de l'age.
            search_log_id: ID du log de recherche.

        Returns:
            WinningAd si l'annonce valide un critere, None sinon.
        """
        criteria = criteria or DEFAULT_WINNING_CRITERIA

        # Calculer l'age
        if not ad.creation_date:
            return None

        ref = reference_date or date.today()
        age_days = (ref - ad.creation_date).days

        if age_days < 0:
            return None

        reach = ad.reach.value

        # Verifier chaque critere
        for max_age, min_reach in criteria:
            if age_days <= max_age and reach >= min_reach:
                criteria_str = f"{max_age}d/{min_reach // 1000}k"
                return cls(
                    ad=ad,
                    matched_criteria=criteria_str,
                    reach_at_detection=reach,
                    search_log_id=search_log_id,
                )

        return None

    @classmethod
    def is_winning(
        cls,
        ad: Ad,
        criteria: list[tuple[int, int]] | None = None,
    ) -> bool:
        """
        Verifie rapidement si une annonce est winning.

        Args:
            ad: Annonce a verifier.
            criteria: Criteres personnalises.

        Returns:
            True si l'annonce est winning.
        """
        return cls.detect(ad, criteria) is not None

    @property
    def id(self) -> AdId:
        """ID de l'annonce."""
        return self.ad.id

    @property
    def page_id(self) -> PageId:
        """ID de la page."""
        return self.ad.page_id

    @property
    def page_name(self) -> str:
        """Nom de la page."""
        return self.ad.page_name

    @property
    def reach(self) -> Reach:
        """Reach de l'annonce."""
        return self.ad.reach

    @property
    def age_days(self) -> int:
        """Age de l'annonce en jours."""
        return self.ad.age_days

    @property
    def creation_date(self) -> date | None:
        """Date de creation de l'annonce."""
        return self.ad.creation_date

    @property
    def snapshot_url(self) -> str:
        """URL de l'apercu de l'annonce."""
        return self.ad.snapshot_url

    def to_dict(self) -> dict:
        """
        Convertit en dictionnaire pour serialisation.

        Returns:
            Dictionnaire avec les donnees principales.
        """
        return {
            "ad_id": str(self.ad.id),
            "page_id": str(self.page_id),
            "page_name": self.page_name,
            "reach": self.reach.value,
            "age_days": self.age_days,
            "matched_criteria": self.matched_criteria,
            "detected_at": self.detected_at.isoformat(),
            "snapshot_url": self.snapshot_url,
        }

    def __eq__(self, other: object) -> bool:
        """Compare par ID d'annonce."""
        if isinstance(other, WinningAd):
            return self.ad.id == other.ad.id
        return False

    def __hash__(self) -> int:
        """Hash base sur l'ID de l'annonce."""
        return hash(self.ad.id)

    def __str__(self) -> str:
        """Representation string."""
        return f"WinningAd({self.id}) - {self.reach} reach, {self.age_days}d"

    def __repr__(self) -> str:
        """Representation debug."""
        return (
            f"WinningAd(ad_id={self.id}, page={self.page_name}, "
            f"reach={self.reach}, criteria='{self.matched_criteria}')"
        )
