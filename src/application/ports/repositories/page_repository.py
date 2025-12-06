"""
Interface du repository de Pages.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.domain.entities.page import Page
from src.domain.value_objects import PageId


class PageRepository(ABC):
    """
    Interface pour la persistance des Pages.

    Cette interface definit toutes les operations de lecture
    et d'ecriture pour les entites Page.
    """

    # ═══════════════════════════════════════════════════════════════════
    # LECTURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_by_id(self, page_id: PageId) -> Page | None:
        """
        Recupere une page par son ID.

        Args:
            page_id: ID de la page.

        Returns:
            Page si trouvee, None sinon.
        """
        pass

    @abstractmethod
    def get_by_ids(self, page_ids: list[PageId]) -> list[Page]:
        """
        Recupere plusieurs pages par leurs IDs.

        Args:
            page_ids: Liste des IDs.

        Returns:
            Liste des pages trouvees.
        """
        pass

    @abstractmethod
    def exists(self, page_id: PageId) -> bool:
        """
        Verifie si une page existe.

        Args:
            page_id: ID de la page.

        Returns:
            True si la page existe.
        """
        pass

    @abstractmethod
    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "updated_at",
        descending: bool = True,
    ) -> list[Page]:
        """
        Recupere toutes les pages avec pagination.

        Args:
            limit: Nombre maximum de resultats.
            offset: Decalage pour la pagination.
            order_by: Champ de tri.
            descending: Tri descendant si True.

        Returns:
            Liste des pages.
        """
        pass

    @abstractmethod
    def find_by_etat(
        self,
        etats: list[str],
        limit: int = 100,
        offset: int = 0,
    ) -> list[Page]:
        """
        Recupere les pages par etat.

        Args:
            etats: Liste des etats a inclure (ex: ["L", "XL", "XXL"]).
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Pages correspondantes.
        """
        pass

    @abstractmethod
    def find_by_cms(
        self,
        cms_types: list[str],
        limit: int = 100,
        offset: int = 0,
    ) -> list[Page]:
        """
        Recupere les pages par CMS.

        Args:
            cms_types: Liste des CMS (ex: ["Shopify", "WooCommerce"]).
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Pages correspondantes.
        """
        pass

    @abstractmethod
    def find_by_category(
        self,
        category: str,
        subcategory: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Page]:
        """
        Recupere les pages par categorie.

        Args:
            category: Categorie principale.
            subcategory: Sous-categorie optionnelle.
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Pages correspondantes.
        """
        pass

    @abstractmethod
    def find_needing_scan(
        self,
        older_than_days: int = 1,
        limit: int = 100,
    ) -> list[Page]:
        """
        Recupere les pages necessitant un nouveau scan.

        Args:
            older_than_days: Age minimum du dernier scan.
            limit: Nombre maximum.

        Returns:
            Pages a scanner.
        """
        pass

    @abstractmethod
    def find_unclassified(self, limit: int = 100) -> list[Page]:
        """
        Recupere les pages non classifiees.

        Args:
            limit: Nombre maximum.

        Returns:
            Pages sans classification.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Page]:
        """
        Recherche de pages avec filtres.

        Args:
            query: Terme de recherche (nom, domaine).
            filters: Filtres additionnels.
            limit: Nombre maximum.
            offset: Decalage.

        Returns:
            Pages correspondantes.
        """
        pass

    @abstractmethod
    def count(self, filters: dict[str, Any] | None = None) -> int:
        """
        Compte les pages selon les filtres.

        Args:
            filters: Filtres optionnels.

        Returns:
            Nombre de pages.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # ECRITURE
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def save(self, page: Page) -> Page:
        """
        Sauvegarde une page (creation ou mise a jour).

        Args:
            page: Page a sauvegarder.

        Returns:
            Page sauvegardee.
        """
        pass

    @abstractmethod
    def save_many(self, pages: list[Page]) -> int:
        """
        Sauvegarde plusieurs pages en batch.

        Args:
            pages: Pages a sauvegarder.

        Returns:
            Nombre de pages sauvegardees.
        """
        pass

    @abstractmethod
    def update(self, page: Page) -> Page:
        """
        Met a jour une page existante.

        Args:
            page: Page a mettre a jour.

        Returns:
            Page mise a jour.

        Raises:
            PageNotFoundError: Si la page n'existe pas.
        """
        pass

    @abstractmethod
    def delete(self, page_id: PageId) -> bool:
        """
        Supprime une page.

        Args:
            page_id: ID de la page a supprimer.

        Returns:
            True si supprimee, False si non trouvee.
        """
        pass

    @abstractmethod
    def update_classification(
        self,
        page_id: PageId,
        category: str,
        subcategory: str | None,
        confidence: float,
    ) -> bool:
        """
        Met a jour la classification d'une page.

        Args:
            page_id: ID de la page.
            category: Nouvelle categorie.
            subcategory: Nouvelle sous-categorie.
            confidence: Score de confiance.

        Returns:
            True si mise a jour reussie.
        """
        pass

    @abstractmethod
    def update_scan_date(self, page_id: PageId, scan_date: datetime) -> bool:
        """
        Met a jour la date de scan d'une page.

        Args:
            page_id: ID de la page.
            scan_date: Nouvelle date de scan.

        Returns:
            True si mise a jour reussie.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # STATISTIQUES
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """
        Recupere les statistiques globales.

        Returns:
            Dictionnaire de statistiques.
        """
        pass

    @abstractmethod
    def get_etat_distribution(self) -> dict[str, int]:
        """
        Recupere la distribution par etat.

        Returns:
            {etat: count}.
        """
        pass

    @abstractmethod
    def get_cms_distribution(self) -> dict[str, int]:
        """
        Recupere la distribution par CMS.

        Returns:
            {cms: count}.
        """
        pass

    @abstractmethod
    def get_category_distribution(self) -> dict[str, int]:
        """
        Recupere la distribution par categorie.

        Returns:
            {category: count}.
        """
        pass
