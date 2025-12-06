"""
Exceptions metier du domaine.

Ces exceptions representent des violations des regles metier
et sont independantes de l'infrastructure.
"""

from typing import Any


class DomainException(Exception):
    """Exception de base pour toutes les erreurs du domaine."""

    def __init__(self, message: str, code: str | None = None) -> None:
        """
        Initialise une exception du domaine.

        Args:
            message: Message d'erreur descriptif.
            code: Code d'erreur optionnel pour identification programmatique.
        """
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class InvalidPageIdError(DomainException):
    """Leve quand un ID de page Facebook est invalide."""

    def __init__(self, value: Any) -> None:
        super().__init__(
            f"ID de page invalide: '{value}'. "
            "L'ID doit etre une chaine non vide representant un entier.",
            code="INVALID_PAGE_ID"
        )
        self.invalid_value = value


class InvalidAdIdError(DomainException):
    """Leve quand un ID d'annonce est invalide."""

    def __init__(self, value: Any) -> None:
        super().__init__(
            f"ID d'annonce invalide: '{value}'. "
            "L'ID doit etre une chaine non vide.",
            code="INVALID_AD_ID"
        )
        self.invalid_value = value


class InvalidEtatError(DomainException):
    """Leve quand un etat de page est invalide."""

    VALID_ETATS = ("XS", "S", "M", "L", "XL", "XXL")

    def __init__(self, value: Any) -> None:
        super().__init__(
            f"Etat invalide: '{value}'. "
            f"Les etats valides sont: {', '.join(self.VALID_ETATS)}",
            code="INVALID_ETAT"
        )
        self.invalid_value = value


class InvalidCMSError(DomainException):
    """Leve quand un CMS est invalide."""

    VALID_CMS = (
        "Shopify", "WooCommerce", "PrestaShop", "Magento",
        "BigCommerce", "Wix", "Squarespace", "Unknown"
    )

    def __init__(self, value: Any) -> None:
        super().__init__(
            f"CMS invalide: '{value}'. "
            f"Les CMS supportes sont: {', '.join(self.VALID_CMS)}",
            code="INVALID_CMS"
        )
        self.invalid_value = value


class InvalidUrlError(DomainException):
    """Leve quand une URL est invalide."""

    def __init__(self, value: Any, reason: str | None = None) -> None:
        message = f"URL invalide: '{value}'."
        if reason:
            message += f" Raison: {reason}"
        super().__init__(message, code="INVALID_URL")
        self.invalid_value = value


class InvalidThematiqueError(DomainException):
    """Leve quand une thematique est invalide."""

    def __init__(self, category: str, subcategory: str | None = None) -> None:
        message = f"Thematique invalide: categorie='{category}'"
        if subcategory:
            message += f", sous-categorie='{subcategory}'"
        super().__init__(message, code="INVALID_THEMATIQUE")
        self.category = category
        self.subcategory = subcategory


class WinningAdCriteriaError(DomainException):
    """Leve quand les criteres de winning ad sont invalides."""

    def __init__(self, age_days: int, reach: int) -> None:
        super().__init__(
            f"Criteres winning ad invalides: age={age_days} jours, reach={reach}. "
            "L'age doit etre positif et le reach >= 0.",
            code="INVALID_WINNING_CRITERIA"
        )
        self.age_days = age_days
        self.reach = reach


class PageNotFoundError(DomainException):
    """Leve quand une page n'est pas trouvee."""

    def __init__(self, page_id: str) -> None:
        super().__init__(
            f"Page non trouvee: '{page_id}'",
            code="PAGE_NOT_FOUND"
        )
        self.page_id = page_id


class AdNotFoundError(DomainException):
    """Leve quand une annonce n'est pas trouvee."""

    def __init__(self, ad_id: str) -> None:
        super().__init__(
            f"Annonce non trouvee: '{ad_id}'",
            code="AD_NOT_FOUND"
        )
        self.ad_id = ad_id


class SearchError(DomainException):
    """Leve quand une recherche echoue."""

    def __init__(self, message: str, keyword: str | None = None) -> None:
        full_message = message
        if keyword:
            full_message = f"Recherche '{keyword}': {message}"
        super().__init__(full_message, code="SEARCH_ERROR")
        self.keyword = keyword


class RateLimitError(DomainException):
    """Leve quand une limite de taux est atteinte."""

    def __init__(
        self,
        service: str,
        retry_after_seconds: int | None = None
    ) -> None:
        message = f"Limite de taux atteinte pour {service}."
        if retry_after_seconds:
            message += f" Reessayer dans {retry_after_seconds} secondes."
        super().__init__(message, code="RATE_LIMIT")
        self.service = service
        self.retry_after_seconds = retry_after_seconds


class ClassificationError(DomainException):
    """Leve quand la classification echoue."""

    def __init__(self, message: str, page_id: str | None = None) -> None:
        full_message = message
        if page_id:
            full_message = f"Classification page '{page_id}': {message}"
        super().__init__(full_message, code="CLASSIFICATION_ERROR")
        self.page_id = page_id
