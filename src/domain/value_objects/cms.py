"""
Value Object pour le systeme de gestion de contenu (CMS) d'un site.
"""

from dataclasses import dataclass
from enum import Enum


class CMSType(Enum):
    """
    Types de CMS supportes.

    Enumere les plateformes e-commerce detectables par l'analyseur.
    """

    SHOPIFY = "Shopify"
    WOOCOMMERCE = "WooCommerce"
    PRESTASHOP = "PrestaShop"
    MAGENTO = "Magento"
    BIGCOMMERCE = "BigCommerce"
    WIX = "Wix"
    SQUARESPACE = "Squarespace"
    UNKNOWN = "Unknown"


# Mapping des aliases vers les types de CMS
CMS_ALIASES = {
    "shopify": CMSType.SHOPIFY,
    "woocommerce": CMSType.WOOCOMMERCE,
    "woo": CMSType.WOOCOMMERCE,
    "wordpress": CMSType.WOOCOMMERCE,  # WooCommerce est base sur WordPress
    "prestashop": CMSType.PRESTASHOP,
    "presta": CMSType.PRESTASHOP,
    "magento": CMSType.MAGENTO,
    "adobe commerce": CMSType.MAGENTO,
    "bigcommerce": CMSType.BIGCOMMERCE,
    "big commerce": CMSType.BIGCOMMERCE,
    "wix": CMSType.WIX,
    "squarespace": CMSType.SQUARESPACE,
    "unknown": CMSType.UNKNOWN,
    "inconnu": CMSType.UNKNOWN,
    "autre": CMSType.UNKNOWN,
    "": CMSType.UNKNOWN,
}


@dataclass(frozen=True, slots=True)
class CMS:
    """
    Systeme de gestion de contenu d'un site e-commerce.

    Represente le CMS/plateforme utilise par un site,
    avec une indication de confiance dans la detection.

    Attributes:
        type: Type de CMS detecte.
        confidence: Score de confiance (0.0 a 1.0).
        theme: Nom du theme utilise (optionnel, Shopify seulement).

    Example:
        >>> cms = CMS.shopify(theme="Dawn", confidence=0.95)
        >>> cms.is_shopify
        True
        >>> cms.theme
        'Dawn'
    """

    type: CMSType
    confidence: float = 1.0
    theme: str | None = None

    def __post_init__(self) -> None:
        """Valide le CMS apres initialisation."""
        # Valider confidence
        object.__setattr__(
            self,
            "confidence",
            max(0.0, min(1.0, self.confidence))
        )

    @classmethod
    def from_string(
        cls,
        value: str,
        confidence: float = 1.0,
        theme: str | None = None
    ) -> "CMS":
        """
        Cree un CMS depuis une chaine.

        Args:
            value: Nom du CMS (peut etre un alias).
            confidence: Score de confiance.
            theme: Nom du theme.

        Returns:
            CMS correspondant.

        Example:
            >>> CMS.from_string("shopify")
            CMS(type=<CMSType.SHOPIFY: 'Shopify'>, confidence=1.0)
        """
        normalized = value.lower().strip() if value else ""
        cms_type = CMS_ALIASES.get(normalized, CMSType.UNKNOWN)
        return cls(type=cms_type, confidence=confidence, theme=theme)

    @classmethod
    def shopify(
        cls,
        confidence: float = 1.0,
        theme: str | None = None
    ) -> "CMS":
        """Factory pour creer un CMS Shopify."""
        return cls(type=CMSType.SHOPIFY, confidence=confidence, theme=theme)

    @classmethod
    def woocommerce(cls, confidence: float = 1.0) -> "CMS":
        """Factory pour creer un CMS WooCommerce."""
        return cls(type=CMSType.WOOCOMMERCE, confidence=confidence)

    @classmethod
    def unknown(cls) -> "CMS":
        """Factory pour creer un CMS inconnu."""
        return cls(type=CMSType.UNKNOWN, confidence=0.0)

    @property
    def is_shopify(self) -> bool:
        """Retourne True si le CMS est Shopify."""
        return self.type == CMSType.SHOPIFY

    @property
    def is_woocommerce(self) -> bool:
        """Retourne True si le CMS est WooCommerce."""
        return self.type == CMSType.WOOCOMMERCE

    @property
    def is_known(self) -> bool:
        """Retourne True si le CMS est connu."""
        return self.type != CMSType.UNKNOWN

    @property
    def is_ecommerce(self) -> bool:
        """Retourne True si c'est une plateforme e-commerce."""
        return self.type in (
            CMSType.SHOPIFY,
            CMSType.WOOCOMMERCE,
            CMSType.PRESTASHOP,
            CMSType.MAGENTO,
            CMSType.BIGCOMMERCE,
        )

    @property
    def name(self) -> str:
        """Retourne le nom du CMS."""
        return self.type.value

    def __str__(self) -> str:
        """Retourne la representation string du CMS."""
        if self.theme:
            return f"{self.type.value} ({self.theme})"
        return self.type.value

    def __repr__(self) -> str:
        """Retourne la representation debug du CMS."""
        parts = [f"type={self.type}"]
        if self.confidence < 1.0:
            parts.append(f"confidence={self.confidence:.2f}")
        if self.theme:
            parts.append(f"theme='{self.theme}'")
        return f"CMS({', '.join(parts)})"
