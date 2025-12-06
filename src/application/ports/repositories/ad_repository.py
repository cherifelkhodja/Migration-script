"""
Interface du repository d'Annonces.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional, Dict, Any

from src.domain.entities.ad import Ad
from src.domain.value_objects import AdId, PageId


class AdRepository(ABC):
    """
    Interface pour la persistance des Annonces.

    Cette interface definit les operations de lecture
    et d'ecriture pour les entites Ad.
    """

    # ═══════════════════════════════════════════════════════════════════
    # LECTURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_by_id(self, ad_id: AdId) -> Optional[Ad]:
        """
        Recupere une annonce par son ID.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            Ad si trouvee, None sinon.
        """
        pass

    @abstractmethod
    def get_by_ids(self, ad_ids: List[AdId]) -> List[Ad]:
        """
        Recupere plusieurs annonces par leurs IDs.

        Args:
            ad_ids: Liste des IDs.

        Returns:
            Liste des annonces trouvees.
        """
        pass

    @abstractmethod
    def exists(self, ad_id: AdId) -> bool:
        """
        Verifie si une annonce existe.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            True si l'annonce existe.
        """
        pass

    @abstractmethod
    def find_by_page(
        self,
        page_id: PageId,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ad]:
        """
        Recupere les annonces d'une page.

        Args:
            page_id: ID de la page.
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Annonces de la page.
        """
        pass

    @abstractmethod
    def find_recent(
        self,
        days: int = 7,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ad]:
        """
        Recupere les annonces recentes.

        Args:
            days: Age maximum en jours.
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Annonces recentes.
        """
        pass

    @abstractmethod
    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ad]:
        """
        Recupere les annonces dans une plage de dates.

        Args:
            start_date: Date de debut.
            end_date: Date de fin.
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Annonces dans la plage.
        """
        pass

    @abstractmethod
    def count_by_page(self, page_id: PageId) -> int:
        """
        Compte les annonces d'une page.

        Args:
            page_id: ID de la page.

        Returns:
            Nombre d'annonces.
        """
        pass

    @abstractmethod
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Compte les annonces selon les filtres.

        Args:
            filters: Filtres optionnels.

        Returns:
            Nombre d'annonces.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # ECRITURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def save(self, ad: Ad) -> Ad:
        """
        Sauvegarde une annonce.

        Args:
            ad: Annonce a sauvegarder.

        Returns:
            Annonce sauvegardee.
        """
        pass

    @abstractmethod
    def save_many(self, ads: List[Ad]) -> int:
        """
        Sauvegarde plusieurs annonces en batch.

        Args:
            ads: Annonces a sauvegarder.

        Returns:
            Nombre d'annonces sauvegardees.
        """
        pass

    @abstractmethod
    def delete(self, ad_id: AdId) -> bool:
        """
        Supprime une annonce.

        Args:
            ad_id: ID de l'annonce.

        Returns:
            True si supprimee.
        """
        pass

    @abstractmethod
    def delete_by_page(self, page_id: PageId) -> int:
        """
        Supprime toutes les annonces d'une page.

        Args:
            page_id: ID de la page.

        Returns:
            Nombre d'annonces supprimees.
        """
        pass

    @abstractmethod
    def delete_older_than(self, days: int) -> int:
        """
        Supprime les annonces plus anciennes que X jours.

        Args:
            days: Age minimum pour suppression.

        Returns:
            Nombre d'annonces supprimees.
        """
        pass
