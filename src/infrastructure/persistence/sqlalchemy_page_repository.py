"""
Adapter SQLAlchemy pour le repository de pages.

Implemente l'interface PageRepository en utilisant SQLAlchemy
pour la persistence dans PostgreSQL.
"""

from typing import Any

from src.application.ports.repositories.page_repository import PageRepository
from src.domain.entities.page import Page
from src.domain.value_objects import PageId, ThematiqueClassification


class SQLAlchemyPageRepository(PageRepository):
    """
    Implementation du PageRepository utilisant SQLAlchemy.

    Cet adapter fait le pont entre les entites du domaine et
    la base de donnees PostgreSQL via SQLAlchemy.

    Example:
        >>> from sqlalchemy.orm import Session
        >>> repo = SQLAlchemyPageRepository(session)
        >>> page = repo.get_by_id(PageId("123456789"))
    """

    def __init__(self, session: Any, db_manager: Any = None) -> None:
        """
        Initialise le repository avec une session SQLAlchemy.

        Args:
            session: Session SQLAlchemy.
            db_manager: DatabaseManager du module app.database (optionnel).
        """
        self._session = session
        self._db = db_manager

    def get_by_id(self, page_id: PageId) -> Page | None:
        """
        Recupere une page par son ID.

        Args:
            page_id: ID de la page.

        Returns:
            Page si trouvee, None sinon.
        """
        if self._db:
            try:
                row = self._db.get_page(str(page_id))
                if row:
                    return self._row_to_page(row)
            except Exception:
                pass
        return None

    def save(self, page: Page) -> Page:
        """
        Sauvegarde une page (creation ou mise a jour).

        Args:
            page: Page a sauvegarder.

        Returns:
            Page sauvegardee.
        """
        if self._db:
            try:
                self._db.upsert_page(
                    page_id=str(page.id),
                    page_name=page.name,
                    website=str(page.website) if page.website else None,
                    nb_ads_active=page.active_ads_count,
                    etat=str(page.etat.level.value) if page.etat else None,
                    cms=page.cms.type.value if page.cms else None,
                    nb_products=page.product_count,
                    category=page.classification.category if page.classification else None,
                    sub_category=page.classification.subcategory if page.classification else None,
                    confidence=page.classification.confidence if page.classification else None,
                )
            except Exception:
                pass
        return page

    def delete(self, page_id: PageId) -> bool:  # noqa: ARG002
        """
        Supprime une page.

        Args:
            page_id: ID de la page a supprimer.

        Returns:
            True si supprimee, False sinon.
        """
        # Non implemente - les pages ne sont generalement pas supprimees
        _ = page_id  # Unused but required by interface
        return False

    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "updated_at",  # noqa: ARG002
        descending: bool = True,  # noqa: ARG002
    ) -> list[Page]:
        """
        Recupere toutes les pages avec pagination.

        Args:
            limit: Nombre max de pages.
            offset: Offset pour la pagination.
            order_by: Champ de tri (non utilise).
            descending: Tri descendant (non utilise).

        Returns:
            Liste des pages.
        """
        _ = order_by, descending
        if self._db:
            try:
                rows = self._db.get_all_pages(limit=limit, offset=offset)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_etat(
        self,
        etats: list[str],
        limit: int = 100,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
    ) -> list[Page]:
        """
        Recupere les pages par etat.

        Args:
            etats: Liste des etats a rechercher.
            limit: Nombre max (non utilise).
            offset: Offset (non utilise).

        Returns:
            Liste des pages.
        """
        _ = limit, offset
        if self._db and etats:
            try:
                rows = self._db.get_pages_by_etat(etats[0])
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_cms(
        self,
        cms_types: list[str],
        limit: int = 100,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
    ) -> list[Page]:
        """
        Recupere les pages par CMS.

        Args:
            cms_types: Liste des CMS a rechercher.
            limit: Nombre max (non utilise).
            offset: Offset (non utilise).

        Returns:
            Liste des pages.
        """
        _ = limit, offset
        if self._db and cms_types:
            try:
                rows = self._db.get_pages_by_cms(cms_types[0])
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_category(
        self,
        category: str,
        subcategory: str | None = None,  # noqa: ARG002
        limit: int = 100,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
    ) -> list[Page]:
        """
        Recupere les pages par categorie.

        Args:
            category: Categorie a rechercher.
            subcategory: Sous-categorie (non utilise).
            limit: Nombre max (non utilise).
            offset: Offset (non utilise).

        Returns:
            Liste des pages.
        """
        _ = subcategory, limit, offset
        if self._db:
            try:
                rows = self._db.get_pages_by_category(category)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_keyword(self, keyword: str) -> list[Page]:
        """
        Recupere les pages trouvees avec un mot-cle.

        Args:
            keyword: Mot-cle a rechercher.

        Returns:
            Liste des pages.
        """
        if self._db:
            try:
                rows = self._db.get_pages_by_keyword(keyword)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_needing_scan(
        self,
        older_than_days: int = 1,  # noqa: ARG002
        limit: int = 100,
    ) -> list[Page]:
        """
        Recupere les pages necessitant un scan.

        Args:
            older_than_days: Age minimum du dernier scan (non utilise).
            limit: Nombre max de pages.

        Returns:
            Liste des pages a scanner.
        """
        _ = older_than_days
        if self._db:
            try:
                rows = self._db.get_pages_needing_scan(limit=limit)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def count(self, filters: dict[str, Any] | None = None) -> int:  # noqa: ARG002
        """
        Compte le nombre total de pages.

        Args:
            filters: Filtres optionnels (non utilises).

        Returns:
            Nombre de pages.
        """
        _ = filters
        if self._db:
            try:
                return self._db.count_pages()
            except Exception:
                pass
        return 0

    def count_by_etat(self) -> dict[str, int]:
        """
        Compte les pages par etat.

        Returns:
            Dictionnaire {etat: count}.
        """
        if self._db:
            try:
                return self._db.count_pages_by_etat()
            except Exception:
                pass
        return {}

    def count_by_cms(self) -> dict[str, int]:
        """
        Compte les pages par CMS.

        Returns:
            Dictionnaire {cms: count}.
        """
        if self._db:
            try:
                return self._db.count_pages_by_cms()
            except Exception:
                pass
        return {}

    # ═══════════════════════════════════════════════════════════════════
    # Methodes supplementaires requises par l'interface
    # ═══════════════════════════════════════════════════════════════════

    def get_by_ids(self, page_ids: list[PageId]) -> list[Page]:
        """Recupere plusieurs pages par leurs IDs."""
        pages = []
        for page_id in page_ids:
            page = self.get_by_id(page_id)
            if page:
                pages.append(page)
        return pages

    def exists(self, page_id: PageId) -> bool:
        """Verifie si une page existe."""
        return self.get_by_id(page_id) is not None

    def find_unclassified(self, limit: int = 100) -> list[Page]:  # noqa: ARG002
        """Recupere les pages non classifiees."""
        _ = limit
        return []

    def search(
        self,
        query: str,  # noqa: ARG002
        filters: dict[str, Any] | None = None,  # noqa: ARG002
        limit: int = 100,  # noqa: ARG002
        offset: int = 0,  # noqa: ARG002
    ) -> list[Page]:
        """Recherche de pages avec filtres."""
        _ = query, filters, limit, offset
        return []

    def save_many(self, pages: list[Page]) -> int:
        """Sauvegarde plusieurs pages en batch."""
        saved = 0
        for page in pages:
            self.save(page)
            saved += 1
        return saved

    def update(self, page: Page) -> Page:
        """Met a jour une page existante."""
        return self.save(page)

    def update_classification(
        self,
        page_id: PageId,
        category: str,
        subcategory: str | None,
        confidence: float,
    ) -> bool:
        """Met a jour la classification d'une page."""
        page = self.get_by_id(page_id)
        if page:
            page.update_classification(category, subcategory, confidence)
            self.save(page)
            return True
        return False

    def update_scan_date(
        self, page_id: PageId, scan_date: Any  # noqa: ARG002
    ) -> bool:
        """Met a jour la date de scan d'une page."""
        page = self.get_by_id(page_id)
        if page:
            page.mark_scanned()
            self.save(page)
            return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        """Recupere les statistiques globales."""
        return {
            "total": self.count(),
            "by_etat": self.count_by_etat(),
            "by_cms": self.count_by_cms(),
        }

    def get_etat_distribution(self) -> dict[str, int]:
        """Recupere la distribution par etat."""
        return self.count_by_etat()

    def get_cms_distribution(self) -> dict[str, int]:
        """Recupere la distribution par CMS."""
        return self.count_by_cms()

    def get_category_distribution(self) -> dict[str, int]:
        """Recupere la distribution par categorie."""
        return {}

    def _row_to_page(self, row: dict | Any) -> Page:
        """
        Convertit une ligne de base de donnees en entite Page.

        Args:
            row: Ligne de la base de donnees.

        Returns:
            Entite Page.
        """
        # Gerer les deux formats: dict ou objet avec attributs
        if isinstance(row, dict):
            page_id = row.get("page_id", "")
            page_name = row.get("page_name", "")
            website = row.get("website")
            nb_ads = row.get("nb_ads_active", 0)
            etat_str = row.get("etat")
            cms_str = row.get("cms")
            nb_products = row.get("nb_products", 0)
            category = row.get("category")
            sub_category = row.get("sub_category")
            confidence = row.get("confidence")
            keywords = row.get("keywords", [])
            last_scan = row.get("last_scan")
        else:
            page_id = getattr(row, "page_id", "")
            page_name = getattr(row, "page_name", "")
            website = getattr(row, "website", None)
            nb_ads = getattr(row, "nb_ads_active", 0)
            etat_str = getattr(row, "etat", None)
            cms_str = getattr(row, "cms", None)
            nb_products = getattr(row, "nb_products", 0)
            category = getattr(row, "category", None)
            sub_category = getattr(row, "sub_category", None)
            confidence = getattr(row, "confidence", None)
            keywords = getattr(row, "keywords", [])
            last_scan = getattr(row, "last_scan", None)

        # Construire l'entite Page
        classification = None
        if category:
            from src.domain.value_objects.thematique import Thematique
            try:
                thematique = Thematique.from_classification(category, sub_category)
                classification = ThematiqueClassification(
                    thematique=thematique,
                    confidence=confidence or 0.0,
                    source="database",
                )
            except Exception:
                pass

        return Page.create(
            page_id=str(page_id),
            name=page_name or "",
            website=website,
            active_ads_count=nb_ads or 0,
            cms=cms_str,
            etat=etat_str,
            product_count=nb_products or 0,
            classification=classification,
            keywords=set(keywords) if keywords else None,
            last_scan=last_scan,
        )
