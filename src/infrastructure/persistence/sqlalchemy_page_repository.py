"""
Adapter SQLAlchemy pour le repository de pages.

Implemente l'interface PageRepository en utilisant SQLAlchemy
pour la persistence dans PostgreSQL.
"""

from typing import Any

from src.application.ports.repositories.page_repository import PageRepository
from src.domain.entities.page import Page
from src.domain.value_objects import CMS, Etat, PageId, ThematiqueClassification


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

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Page]:
        """
        Recupere toutes les pages avec pagination.

        Args:
            limit: Nombre max de pages.
            offset: Offset pour la pagination.

        Returns:
            Liste des pages.
        """
        if self._db:
            try:
                rows = self._db.get_all_pages(limit=limit, offset=offset)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_etat(self, etat: Etat) -> list[Page]:
        """
        Recupere les pages par etat.

        Args:
            etat: Etat a rechercher.

        Returns:
            Liste des pages.
        """
        if self._db:
            try:
                rows = self._db.get_pages_by_etat(etat.level.value)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_cms(self, cms: CMS) -> list[Page]:
        """
        Recupere les pages par CMS.

        Args:
            cms: CMS a rechercher.

        Returns:
            Liste des pages.
        """
        if self._db:
            try:
                rows = self._db.get_pages_by_cms(cms.type.value)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def find_by_category(self, category: str) -> list[Page]:
        """
        Recupere les pages par categorie.

        Args:
            category: Categorie a rechercher.

        Returns:
            Liste des pages.
        """
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

    def find_needing_scan(self, limit: int = 100) -> list[Page]:
        """
        Recupere les pages necessitant un scan.

        Args:
            limit: Nombre max de pages.

        Returns:
            Liste des pages a scanner.
        """
        if self._db:
            try:
                rows = self._db.get_pages_needing_scan(limit=limit)
                return [self._row_to_page(row) for row in rows]
            except Exception:
                pass
        return []

    def count(self) -> int:
        """
        Compte le nombre total de pages.

        Returns:
            Nombre de pages.
        """
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
            classification = ThematiqueClassification(
                category=category,
                subcategory=sub_category,
                confidence=confidence or 0.0,
            )

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
