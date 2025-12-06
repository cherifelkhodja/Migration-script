"""
View Model pour l'affichage detaille d'une Page.

Encapsule la logique de presentation pour la visualisation
et la gestion des pages Facebook.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.application.ports.repositories.page_repository import PageRepository
from src.application.ports.services.website_analyzer_service import (
    WebsiteAnalyzerService,
)
from src.application.use_cases.analyze_website import (
    AnalyzeWebsiteRequest,
    AnalyzeWebsiteUseCase,
)
from src.domain.entities.ad import Ad
from src.domain.entities.page import Page
from src.domain.value_objects import PageId


@dataclass
class PageDetailItem:
    """
    Donnees formatees d'une page pour l'affichage.

    Attributes:
        page_id: ID de la page.
        page_name: Nom de la page.
        website: URL du site web.
        domain: Domaine extrait.
        cms: CMS detecte.
        cms_theme: Theme du CMS.
        etat: Niveau d'activite.
        ads_count: Nombre d'annonces actives.
        product_count: Nombre de produits.
        category: Categorie thematique.
        subcategory: Sous-categorie.
        confidence: Score de confiance classification.
        currency: Devise detectee.
        payment_methods: Moyens de paiement.
        keywords: Mots-cles associes.
        last_scan: Date du dernier scan.
        is_shopify: True si Shopify.
        facebook_url: URL de la page Facebook.
    """

    page_id: str
    page_name: str
    website: str
    domain: str
    cms: str
    cms_theme: str
    etat: str
    ads_count: int
    product_count: int
    category: str
    subcategory: str
    confidence: float
    currency: str
    payment_methods: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    last_scan: str = ""
    is_shopify: bool = False
    facebook_url: str = ""

    @classmethod
    def from_page(cls, page: Page) -> "PageDetailItem":
        """
        Cree un PageDetailItem depuis une entite Page.

        Args:
            page: Entite Page du domaine.

        Returns:
            PageDetailItem formate pour l'affichage.
        """
        return cls(
            page_id=str(page.id),
            page_name=page.name,
            website=str(page.website) if page.website else "",
            domain=page.domain or "",
            cms=page.cms.name,
            cms_theme=page.cms.theme or "",
            etat=page.etat.level.value if page.etat else "XS",
            ads_count=page.active_ads_count,
            product_count=page.product_count,
            category=page.category or "Non classifie",
            subcategory=page.subcategory or "",
            confidence=page.classification.confidence if page.classification else 0.0,
            currency=page.currency.code if page.currency else "",
            payment_methods=list(page.payment_methods),
            keywords=sorted(page.keywords),
            last_scan=page.last_scan_at.strftime("%Y-%m-%d %H:%M") if page.last_scan_at else "Jamais",
            is_shopify=page.is_shopify,
            facebook_url=f"https://www.facebook.com/{page.id}",
        )

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour DataFrame."""
        return {
            "page_id": self.page_id,
            "page_name": self.page_name,
            "website": self.website,
            "domain": self.domain,
            "cms": self.cms,
            "etat": self.etat,
            "ads_count": self.ads_count,
            "product_count": self.product_count,
            "category": self.category,
            "subcategory": self.subcategory,
            "confidence": f"{self.confidence:.1%}",
            "currency": self.currency,
            "payment_methods": ", ".join(self.payment_methods),
            "keywords": ", ".join(self.keywords),
            "last_scan": self.last_scan,
        }


@dataclass
class ScanResult:
    """
    Resultat d'un scan de site web.

    Attributes:
        success: True si le scan a reussi.
        cms_detected: CMS detecte.
        product_count: Nombre de produits.
        currency: Devise detectee.
        error_message: Message d'erreur si echec.
        duration_ms: Duree du scan en ms.
    """

    success: bool
    cms_detected: str = ""
    product_count: int = 0
    currency: str = ""
    error_message: str = ""
    duration_ms: int = 0


class PageViewModel:
    """
    View Model pour la gestion des pages.

    Fournit les operations CRUD et d'analyse pour les pages.

    Example:
        >>> vm = PageViewModel(page_repo, analyzer_service)
        >>> detail = vm.get_page_detail("123456789")
        >>> if detail:
        ...     print(f"{detail.page_name}: {detail.ads_count} ads")
    """

    def __init__(
        self,
        page_repository: PageRepository,
        analyzer_service: WebsiteAnalyzerService | None = None,
    ) -> None:
        """
        Initialise le view model.

        Args:
            page_repository: Repository pour acceder aux pages.
            analyzer_service: Service d'analyse de sites (optionnel).
        """
        self._page_repo = page_repository
        self._analyzer = analyzer_service

        # Cache local
        self._current_page: Page | None = None
        self._current_ads: list[Ad] = []

    def get_page_detail(self, page_id: str) -> PageDetailItem | None:
        """
        Recupere les details d'une page.

        Args:
            page_id: ID de la page.

        Returns:
            PageDetailItem formate ou None si non trouve.
        """
        try:
            pid = PageId.from_any(page_id)
            page = self._page_repo.get_by_id(pid)

            if page:
                self._current_page = page
                return PageDetailItem.from_page(page)

            return None
        except Exception:
            return None

    def get_pages_by_etat(self, etat: str, limit: int = 100) -> list[PageDetailItem]:
        """
        Recupere les pages par etat.

        Args:
            etat: Code etat (XS, S, M, L, XL, XXL).
            limit: Nombre max de pages.

        Returns:
            Liste des pages formatees.
        """
        try:
            pages = self._page_repo.find_by_etat([etat], limit=limit)
            return [PageDetailItem.from_page(p) for p in pages]
        except Exception:
            return []

    def get_pages_by_cms(self, cms: str, limit: int = 100) -> list[PageDetailItem]:
        """
        Recupere les pages par CMS.

        Args:
            cms: Nom du CMS.
            limit: Nombre max de pages.

        Returns:
            Liste des pages formatees.
        """
        try:
            pages = self._page_repo.find_by_cms([cms], limit=limit)
            return [PageDetailItem.from_page(p) for p in pages]
        except Exception:
            return []

    def get_pages_by_category(
        self, category: str, limit: int = 100
    ) -> list[PageDetailItem]:
        """
        Recupere les pages par categorie.

        Args:
            category: Categorie thematique.
            limit: Nombre max de pages.

        Returns:
            Liste des pages formatees.
        """
        try:
            pages = self._page_repo.find_by_category(category)
            return [PageDetailItem.from_page(p) for p in pages[:limit]]
        except Exception:
            return []

    def scan_website(self, page_id: str) -> ScanResult:
        """
        Lance un scan du site web d'une page.

        Args:
            page_id: ID de la page a scanner.

        Returns:
            Resultat du scan.
        """
        if not self._analyzer:
            return ScanResult(
                success=False,
                error_message="Service d'analyse non disponible",
            )

        try:
            pid = PageId.from_any(page_id)
            page = self._page_repo.get_by_id(pid)

            if not page or not page.website:
                return ScanResult(
                    success=False,
                    error_message="Page non trouvee ou sans site web",
                )

            # Executer l'analyse
            use_case = AnalyzeWebsiteUseCase(self._analyzer)
            request = AnalyzeWebsiteRequest(url=str(page.website))

            start_time = datetime.now()
            response = use_case.execute(request)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)

            if response.success:
                # Mettre a jour la page
                if response.cms:
                    page.update_cms(response.cms)
                if response.product_count:
                    page.update_product_count(response.product_count)
                page.mark_scanned()
                self._page_repo.save(page)

                return ScanResult(
                    success=True,
                    cms_detected=response.cms or "",
                    product_count=response.product_count or 0,
                    currency=response.currency or "",
                    duration_ms=duration,
                )
            else:
                return ScanResult(
                    success=False,
                    error_message=response.error_message or "Echec du scan",
                    duration_ms=duration,
                )

        except Exception as e:
            return ScanResult(
                success=False,
                error_message=str(e),
            )

    def update_classification(
        self,
        page_id: str,
        category: str,
        subcategory: str | None = None,
        confidence: float = 1.0,
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
        try:
            pid = PageId.from_any(page_id)
            page = self._page_repo.get_by_id(pid)

            if page:
                page.update_classification(
                    category=category,
                    subcategory=subcategory,
                    confidence=confidence,
                    source="manual",
                )
                self._page_repo.save(page)
                return True

            return False
        except Exception:
            return False

    def get_statistics(self) -> dict:
        """
        Recupere les statistiques globales des pages.

        Returns:
            Dictionnaire avec les statistiques.
        """
        try:
            total = self._page_repo.count()
            by_etat = self._page_repo.get_etat_distribution()
            by_cms = self._page_repo.get_cms_distribution()

            return {
                "total_pages": total,
                "by_etat": by_etat,
                "by_cms": by_cms,
            }
        except Exception:
            return {
                "total_pages": 0,
                "by_etat": {},
                "by_cms": {},
            }

    def get_pages_needing_scan(self, limit: int = 50) -> list[PageDetailItem]:
        """
        Recupere les pages necessitant un scan.

        Args:
            limit: Nombre max de pages.

        Returns:
            Liste des pages a scanner.
        """
        try:
            pages = self._page_repo.find_needing_scan(limit=limit)
            return [PageDetailItem.from_page(p) for p in pages]
        except Exception:
            return []

    def set_page_ads(self, ads: list[Ad]) -> None:
        """
        Definit les annonces de la page courante.

        Args:
            ads: Liste des annonces.
        """
        self._current_ads = ads

    @property
    def current_page(self) -> Page | None:
        """Retourne la page courante."""
        return self._current_page

    @property
    def current_ads(self) -> list[Ad]:
        """Retourne les annonces de la page courante."""
        return self._current_ads
