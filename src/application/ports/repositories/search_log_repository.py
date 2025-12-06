"""
Interface du repository de logs de recherche.
"""

from abc import ABC, abstractmethod
from typing import Any


class SearchLogRepository(ABC):
    """
    Interface pour la persistance des logs de recherche.
    """

    @abstractmethod
    def create(
        self,
        keywords: list[str],
        countries: str,
        languages: str,
        min_ads: int,
        selected_cms: list[str],
    ) -> int:
        """
        Cree un nouveau log de recherche.

        Returns:
            ID du log cree.
        """
        pass

    @abstractmethod
    def update_status(
        self,
        log_id: int,
        status: str,
        error_message: str | None = None,
    ) -> bool:
        """Met a jour le statut d'un log."""
        pass

    @abstractmethod
    def update_results(
        self,
        log_id: int,
        total_ads_found: int,
        total_pages_found: int,
        pages_after_filter: int,
        winning_ads_count: int,
        pages_saved: int,
        ads_saved: int,
    ) -> bool:
        """Met a jour les resultats d'un log."""
        pass

    @abstractmethod
    def get_by_id(self, log_id: int) -> dict[str, Any] | None:
        """Recupere un log par son ID."""
        pass

    @abstractmethod
    def find_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recupere les logs recents."""
        pass

    @abstractmethod
    def find_by_status(
        self,
        status: str,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Recupere les logs par statut."""
        pass

    @abstractmethod
    def delete_older_than(self, days: int) -> int:
        """Supprime les logs plus anciens que X jours."""
        pass
