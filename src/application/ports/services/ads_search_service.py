"""
Interface du service de recherche d'annonces Meta.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from src.domain.entities.ad import Ad
from src.domain.value_objects import PageId


@dataclass
class SearchParameters:
    """
    Parametres de recherche d'annonces.

    Attributes:
        keywords: Mots-cles a rechercher.
        countries: Codes pays (ex: ["FR", "BE"]).
        languages: Codes langues (ex: ["fr", "en"]).
        min_ads: Nombre minimum d'annonces pour filtrage.
    """

    keywords: list[str]
    countries: list[str] = field(default_factory=lambda: ["FR"])
    languages: list[str] = field(default_factory=lambda: ["fr"])
    min_ads: int = 1


@dataclass
class SearchResult:
    """
    Resultat d'une recherche d'annonces.

    Attributes:
        ads: Liste des annonces trouvees.
        ads_by_keyword: Nombre d'annonces par mot-cle.
        total_unique_ads: Nombre total d'annonces uniques.
        pages_found: Nombre de pages uniques.
    """

    ads: list[Ad]
    ads_by_keyword: dict[str, int]
    total_unique_ads: int
    pages_found: int


@dataclass
class PageAdsResult:
    """
    Resultat de la recuperation des annonces d'une page.

    Attributes:
        ads: Liste des annonces de la page.
        total_count: Nombre total d'annonces.
        page_id: ID de la page.
    """

    ads: list[Ad]
    total_count: int
    page_id: PageId


# Type pour le callback de progression
ProgressCallback = Callable[[str, int, int], None]  # (keyword, current, total)


class AdsSearchService(ABC):
    """
    Interface pour le service de recherche d'annonces Meta.

    Ce service encapsule les appels a l'API Meta Ads Archive
    pour rechercher des annonces par mots-cles ou par page.
    """

    @abstractmethod
    def search_by_keywords(
        self,
        params: SearchParameters,
        progress_callback: ProgressCallback | None = None,
    ) -> SearchResult:
        """
        Recherche des annonces par mots-cles.

        Args:
            params: Parametres de recherche.
            progress_callback: Callback de progression optionnel.

        Returns:
            Resultat de la recherche.

        Raises:
            SearchError: En cas d'erreur de recherche.
            RateLimitError: Si la limite de taux est atteinte.
        """
        pass

    @abstractmethod
    def fetch_ads_for_page(
        self,
        page_id: PageId,
        countries: list[str],
        languages: list[str] | None = None,
    ) -> PageAdsResult:
        """
        Recupere toutes les annonces d'une page.

        Args:
            page_id: ID de la page.
            countries: Codes pays.
            languages: Codes langues optionnels.

        Returns:
            Annonces de la page.

        Raises:
            SearchError: En cas d'erreur.
        """
        pass

    @abstractmethod
    def fetch_ads_for_pages_batch(
        self,
        page_ids: list[PageId],
        countries: list[str],
        languages: list[str] | None = None,
    ) -> dict[str, PageAdsResult]:
        """
        Recupere les annonces de plusieurs pages en batch.

        Args:
            page_ids: Liste des IDs de pages (max 10).
            countries: Codes pays.
            languages: Codes langues optionnels.

        Returns:
            Dictionnaire {page_id: PageAdsResult}.
        """
        pass

    @abstractmethod
    def extract_website_from_ads(self, ads: list[Ad]) -> str | None:
        """
        Extrait l'URL du site web depuis les annonces.

        Args:
            ads: Liste d'annonces.

        Returns:
            URL extraite ou None.
        """
        pass

    @abstractmethod
    def extract_currency_from_ads(self, ads: list[Ad]) -> str | None:
        """
        Extrait la devise depuis les annonces.

        Args:
            ads: Liste d'annonces.

        Returns:
            Code devise ou None.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifie si le service est disponible.

        Returns:
            True si le service est operationnel.
        """
        pass

    @abstractmethod
    def get_token_info(self) -> dict[str, any]:
        """
        Retourne les informations sur les tokens API.

        Returns:
            Dictionnaire avec infos sur les tokens.
        """
        pass
