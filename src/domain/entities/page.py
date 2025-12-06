"""
Entite Page - Page Facebook avec metadonnees e-commerce.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.value_objects import (
    CMS,
    Currency,
    Etat,
    PageId,
    Thematique,
    ThematiqueClassification,
    Url,
)


@dataclass
class Page:
    """
    Page Facebook avec ses metadonnees e-commerce.

    Une Page represente une page Facebook qui fait de la publicite
    pour un site e-commerce. Elle contient toutes les informations
    collectees lors de l'analyse.

    Attributes:
        id: Identifiant unique de la page Facebook.
        name: Nom de la page.
        website: URL du site e-commerce associe.
        cms: Systeme de gestion de contenu detecte.
        etat: Niveau d'activite publicitaire.
        active_ads_count: Nombre d'annonces actives.
        product_count: Nombre de produits sur le site.
        classification: Classification thematique du site.
        currency: Devise utilisee.
        payment_methods: Moyens de paiement detectes.
        keywords: Mots-cles ayant trouve cette page.
        created_at: Date de premiere decouverte.
        updated_at: Date de derniere mise a jour.
        last_scan_at: Date du dernier scan.

    Example:
        >>> page = Page(
        ...     id=PageId("123456789"),
        ...     name="Ma Boutique",
        ...     website=Url.from_string("maboutique.com"),
        ...     cms=CMS.shopify(theme="Dawn"),
        ...     active_ads_count=50
        ... )
        >>> page.etat.level
        <EtatLevel.L: 'L'>
    """

    id: PageId
    name: str
    website: Url | None = None
    cms: CMS = field(default_factory=CMS.unknown)
    etat: Etat | None = None
    active_ads_count: int = 0
    product_count: int = 0
    classification: ThematiqueClassification | None = None
    currency: Currency | None = None
    payment_methods: list[str] = field(default_factory=list)
    keywords: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_scan_at: datetime | None = None

    # Champs internes pour tracking
    _is_new: bool = field(default=True, repr=False)
    _is_dirty: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Initialise les champs calcules."""
        # Calculer l'etat si non fourni
        if self.etat is None and self.active_ads_count >= 0:
            self.etat = Etat.from_ads_count(self.active_ads_count)

    @classmethod
    def create(
        cls,
        page_id: str,
        name: str,
        website: str | None = None,
        cms: str | None = None,
        active_ads_count: int = 0,
    ) -> "Page":
        """
        Factory pour creer une nouvelle Page.

        Args:
            page_id: ID de la page Facebook.
            name: Nom de la page.
            website: URL du site (optionnel).
            cms: Nom du CMS (optionnel).
            active_ads_count: Nombre d'annonces actives.

        Returns:
            Nouvelle instance de Page.
        """
        return cls(
            id=PageId.from_any(page_id),
            name=name.strip() if name else "",
            website=Url.try_from_string(website) if website else None,
            cms=CMS.from_string(cms) if cms else CMS.unknown(),
            active_ads_count=active_ads_count,
        )

    def update_ads_count(self, count: int) -> None:
        """
        Met a jour le nombre d'annonces et recalcule l'etat.

        Args:
            count: Nouveau nombre d'annonces actives.
        """
        if count != self.active_ads_count:
            self.active_ads_count = count
            self.etat = Etat.from_ads_count(count)
            self._mark_dirty()

    def update_website(self, url: str) -> None:
        """
        Met a jour l'URL du site.

        Args:
            url: Nouvelle URL du site.
        """
        new_url = Url.try_from_string(url)
        if new_url and new_url != self.website:
            self.website = new_url
            self._mark_dirty()

    def update_cms(self, cms_name: str, theme: str | None = None) -> None:
        """
        Met a jour le CMS detecte.

        Args:
            cms_name: Nom du CMS.
            theme: Nom du theme (optionnel).
        """
        new_cms = CMS.from_string(cms_name, theme=theme)
        if new_cms.type != self.cms.type:
            self.cms = new_cms
            self._mark_dirty()

    def update_classification(
        self,
        category: str,
        subcategory: str | None = None,
        confidence: float = 0.5,
        source: str = "unknown"
    ) -> None:
        """
        Met a jour la classification thematique.

        Args:
            category: Categorie principale.
            subcategory: Sous-categorie.
            confidence: Score de confiance.
            source: Source de la classification.
        """
        thematique = Thematique.from_classification(category, subcategory)
        self.classification = ThematiqueClassification(
            thematique=thematique,
            confidence=confidence,
            source=source
        )
        self._mark_dirty()

    def update_product_count(self, count: int) -> None:
        """
        Met a jour le nombre de produits.

        Args:
            count: Nouveau nombre de produits.
        """
        if count != self.product_count:
            self.product_count = max(0, count)
            self._mark_dirty()

    def add_keyword(self, keyword: str) -> None:
        """
        Ajoute un mot-cle qui a trouve cette page.

        Args:
            keyword: Mot-cle a ajouter.
        """
        if keyword and keyword.strip():
            self.keywords.add(keyword.strip().lower())

    def mark_scanned(self) -> None:
        """Marque la page comme scannee."""
        self.last_scan_at = datetime.now()
        self.updated_at = datetime.now()

    def _mark_dirty(self) -> None:
        """Marque la page comme modifiee."""
        self._is_dirty = True
        self.updated_at = datetime.now()

    @property
    def is_shopify(self) -> bool:
        """Retourne True si le site utilise Shopify."""
        return self.cms.is_shopify

    @property
    def is_active(self) -> bool:
        """Retourne True si la page a des annonces actives."""
        return self.active_ads_count > 0

    @property
    def is_classified(self) -> bool:
        """Retourne True si la page est classifiee."""
        return (
            self.classification is not None and
            not self.classification.thematique.is_unknown
        )

    @property
    def category(self) -> str | None:
        """Raccourci vers la categorie."""
        if self.classification:
            return self.classification.category
        return None

    @property
    def subcategory(self) -> str | None:
        """Raccourci vers la sous-categorie."""
        if self.classification:
            return self.classification.subcategory
        return None

    @property
    def domain(self) -> str | None:
        """Retourne le domaine du site."""
        if self.website:
            return self.website.domain
        return None

    def __eq__(self, other: object) -> bool:
        """Compare deux pages par leur ID."""
        if isinstance(other, Page):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash base sur l'ID."""
        return hash(self.id)

    def __str__(self) -> str:
        """Representation string."""
        return f"{self.name} ({self.id})"

    def __repr__(self) -> str:
        """Representation debug."""
        return (
            f"Page(id={self.id}, name='{self.name}', "
            f"ads={self.active_ads_count}, cms={self.cms.name})"
        )
