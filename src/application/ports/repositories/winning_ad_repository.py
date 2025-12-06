"""
Interface du repository de Winning Ads.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from src.domain.entities.winning_ad import WinningAd
from src.domain.value_objects import AdId, PageId


class WinningAdRepository(ABC):
    """
    Interface pour la persistance des Winning Ads.

    Cette interface definit les operations de lecture
    et d'ecriture pour les entites WinningAd.
    """

    # ═══════════════════════════════════════════════════════════════════
    # LECTURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_by_ad_id(self, ad_id: AdId) -> WinningAd | None:
        """
        Recupere une winning ad par l'ID de l'annonce.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            WinningAd si trouvee, None sinon.
        """
        pass

    @abstractmethod
    def exists(self, ad_id: AdId) -> bool:
        """
        Verifie si une winning ad existe.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            True si existe.
        """
        pass

    @abstractmethod
    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "detected_at",
        descending: bool = True,
    ) -> list[WinningAd]:
        """
        Recupere toutes les winning ads avec pagination.

        Args:
            limit: Nombre maximum.
            offset: Decalage.
            order_by: Champ de tri.
            descending: Tri descendant.

        Returns:
            Liste des winning ads.
        """
        pass

    @abstractmethod
    def find_by_page(
        self,
        page_id: PageId,
        limit: int = 100,
    ) -> list[WinningAd]:
        """
        Recupere les winning ads d'une page.

        Args:
            page_id: ID de la page.
            limit: Nombre maximum.

        Returns:
            Winning ads de la page.
        """
        pass

    @abstractmethod
    def find_by_criteria(
        self,
        criteria: str,
        limit: int = 100,
    ) -> list[WinningAd]:
        """
        Recupere les winning ads par critere.

        Args:
            criteria: Critere (ex: "4d/15k").
            limit: Nombre maximum.

        Returns:
            Winning ads du critere.
        """
        pass

    @abstractmethod
    def find_recent(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> list[WinningAd]:
        """
        Recupere les winning ads detectees recemment.

        Args:
            days: Nombre de jours.
            limit: Nombre maximum.

        Returns:
            Winning ads recentes.
        """
        pass

    @abstractmethod
    def find_by_search_log(
        self,
        search_log_id: int,
        limit: int = 100,
    ) -> list[WinningAd]:
        """
        Recupere les winning ads d'une recherche.

        Args:
            search_log_id: ID du log de recherche.
            limit: Nombre maximum.

        Returns:
            Winning ads de la recherche.
        """
        pass

    @abstractmethod
    def count(self, filters: dict[str, Any] | None = None) -> int:
        """
        Compte les winning ads.

        Args:
            filters: Filtres optionnels.

        Returns:
            Nombre de winning ads.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # ECRITURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def save(self, winning_ad: WinningAd) -> WinningAd:
        """
        Sauvegarde une winning ad.

        Args:
            winning_ad: Winning ad a sauvegarder.

        Returns:
            Winning ad sauvegardee.
        """
        pass

    @abstractmethod
    def save_many(self, winning_ads: list[WinningAd]) -> tuple:
        """
        Sauvegarde plusieurs winning ads en batch.

        Args:
            winning_ads: Winning ads a sauvegarder.

        Returns:
            Tuple (saved_count, skipped_count).
        """
        pass

    @abstractmethod
    def delete(self, ad_id: AdId) -> bool:
        """
        Supprime une winning ad.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            True si supprimee.
        """
        pass

    @abstractmethod
    def delete_older_than(self, days: int) -> int:
        """
        Supprime les winning ads plus anciennes que X jours.

        Args:
            days: Age minimum pour suppression.

        Returns:
            Nombre supprimees.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # STATISTIQUES
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """
        Recupere les statistiques.

        Returns:
            Dictionnaire de statistiques.
        """
        pass

    @abstractmethod
    def get_criteria_distribution(self) -> dict[str, int]:
        """
        Recupere la distribution par critere.

        Returns:
            {criteria: count}.
        """
        pass

    @abstractmethod
    def get_daily_counts(self, days: int = 30) -> dict[date, int]:
        """
        Recupere les comptes journaliers.

        Args:
            days: Nombre de jours.

        Returns:
            {date: count}.
        """
        pass
