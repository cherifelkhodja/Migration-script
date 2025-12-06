"""
Interface du service d'analyse de sites web.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.value_objects import CMS


@dataclass
class WebsiteAnalysisResult:
    """
    Resultat de l'analyse d'un site web.

    Attributes:
        url: URL analysee.
        cms: CMS detecte.
        theme: Theme detecte (pour Shopify).
        product_count: Nombre de produits.
        payment_methods: Moyens de paiement detectes.
        currency: Devise detectee.
        site_title: Titre du site.
        site_description: Meta description.
        site_h1: Premier H1.
        site_keywords: Meta keywords.
        error: Message d'erreur si echec.
    """

    url: str
    cms: CMS = field(default_factory=CMS.unknown)
    theme: str | None = None
    product_count: int = 0
    payment_methods: list[str] = field(default_factory=list)
    currency: str | None = None
    site_title: str = ""
    site_description: str = ""
    site_h1: str = ""
    site_keywords: str = ""
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Retourne True si l'analyse a reussi."""
        return self.error is None

    @property
    def has_content(self) -> bool:
        """Retourne True si du contenu a ete extrait."""
        return bool(
            self.site_title or
            self.site_description or
            self.site_h1 or
            self.site_keywords
        )

    @property
    def is_shopify(self) -> bool:
        """Retourne True si c'est un site Shopify."""
        return self.cms.is_shopify


@dataclass
class CMSDetectionResult:
    """
    Resultat de la detection de CMS.

    Attributes:
        cms: CMS detecte.
        confidence: Score de confiance.
        theme: Theme detecte (optionnel).
        evidence: Elements de preuve.
    """

    cms: CMS
    confidence: float = 1.0
    theme: str | None = None
    evidence: list[str] = field(default_factory=list)


class WebsiteAnalyzerService(ABC):
    """
    Interface pour le service d'analyse de sites web.

    Ce service encapsule le scraping et l'analyse des sites
    e-commerce (detection CMS, comptage produits, etc.).
    """

    @abstractmethod
    def analyze(
        self,
        url: str,
        country_code: str = "FR",
    ) -> WebsiteAnalysisResult:
        """
        Analyse complete d'un site web.

        Args:
            url: URL du site a analyser.
            country_code: Code pays pour le sitemap.

        Returns:
            Resultat de l'analyse.
        """
        pass

    @abstractmethod
    def analyze_batch(
        self,
        urls: list[str],
        country_code: str = "FR",
        max_concurrent: int = 5,
    ) -> dict[str, WebsiteAnalysisResult]:
        """
        Analyse plusieurs sites en parallele.

        Args:
            urls: Liste des URLs a analyser.
            country_code: Code pays.
            max_concurrent: Nombre max de requetes simultanees.

        Returns:
            Dictionnaire {url: resultat}.
        """
        pass

    @abstractmethod
    def detect_cms(self, url: str) -> CMSDetectionResult:
        """
        Detecte le CMS d'un site.

        Args:
            url: URL du site.

        Returns:
            Resultat de la detection.
        """
        pass

    @abstractmethod
    def count_products(
        self,
        url: str,
        country_code: str = "FR",
    ) -> int:
        """
        Compte les produits d'un site.

        Args:
            url: URL du site.
            country_code: Code pays pour le sitemap.

        Returns:
            Nombre de produits.
        """
        pass

    @abstractmethod
    def detect_payments(self, url: str) -> list[str]:
        """
        Detecte les moyens de paiement.

        Args:
            url: URL du site.

        Returns:
            Liste des moyens de paiement.
        """
        pass

    @abstractmethod
    def extract_metadata(self, url: str) -> dict[str, str]:
        """
        Extrait les metadonnees d'un site.

        Args:
            url: URL du site.

        Returns:
            Dictionnaire {title, description, h1, keywords}.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifie si le service est disponible.

        Returns:
            True si operationnel.
        """
        pass
