"""
Use Case: Recherche d'annonces par mots-cles.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Set, Callable

from src.domain.entities.page import Page
from src.domain.entities.ad import Ad
from src.domain.value_objects import PageId, Etat
from src.application.ports.services.ads_search_service import (
    AdsSearchService,
    SearchParameters,
    SearchResult,
)
from src.application.ports.repositories.page_repository import PageRepository


@dataclass
class SearchAdsRequest:
    """
    Requete de recherche d'annonces.

    Attributes:
        keywords: Mots-cles a rechercher.
        countries: Codes pays.
        languages: Codes langues.
        min_ads: Nombre minimum d'annonces par page.
        cms_filter: CMS a inclure.
        exclude_blacklisted: Exclure les pages blacklistees.
    """

    keywords: List[str]
    countries: List[str] = field(default_factory=lambda: ["FR"])
    languages: List[str] = field(default_factory=lambda: ["fr"])
    min_ads: int = 1
    cms_filter: List[str] = field(default_factory=list)
    exclude_blacklisted: bool = True


@dataclass
class PageWithAds:
    """
    Page avec ses annonces.

    Attributes:
        page: Entite Page.
        ads: Liste des annonces.
        keywords_found: Mots-cles qui ont trouve cette page.
    """

    page: Page
    ads: List[Ad]
    keywords_found: Set[str] = field(default_factory=set)

    @property
    def ads_count(self) -> int:
        return len(self.ads)


@dataclass
class SearchAdsResponse:
    """
    Reponse de la recherche d'annonces.

    Attributes:
        pages: Pages trouvees avec leurs annonces.
        total_ads_found: Nombre total d'annonces trouvees.
        unique_ads_count: Nombre d'annonces uniques.
        pages_before_filter: Pages avant filtrage.
        pages_after_filter: Pages apres filtrage.
        search_duration_ms: Duree de la recherche en ms.
        keywords_stats: Statistiques par mot-cle.
    """

    pages: List[PageWithAds]
    total_ads_found: int
    unique_ads_count: int
    pages_before_filter: int
    pages_after_filter: int
    search_duration_ms: int
    keywords_stats: Dict[str, int]

    @property
    def pages_count(self) -> int:
        return len(self.pages)


# Type pour le callback de progression
ProgressCallback = Callable[[str, int, int], None]


class SearchAdsUseCase:
    """
    Use Case: Recherche d'annonces par mots-cles.

    Ce use case orchestre la recherche d'annonces via l'API Meta,
    regroupe les resultats par page et applique les filtres.

    Example:
        >>> search = SearchAdsUseCase(ads_service, page_repo)
        >>> request = SearchAdsRequest(keywords=["bijoux"], countries=["FR"])
        >>> response = search.execute(request)
        >>> print(f"{response.pages_count} pages trouvees")
    """

    def __init__(
        self,
        ads_service: AdsSearchService,
        page_repository: Optional[PageRepository] = None,
        blacklist: Optional[Set[str]] = None,
    ) -> None:
        """
        Initialise le use case.

        Args:
            ads_service: Service de recherche d'annonces.
            page_repository: Repository de pages pour le cache.
            blacklist: Set des page_ids a exclure.
        """
        self._ads_service = ads_service
        self._page_repository = page_repository
        self._blacklist = blacklist or set()

    def execute(
        self,
        request: SearchAdsRequest,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> SearchAdsResponse:
        """
        Execute la recherche d'annonces.

        Args:
            request: Requete de recherche.
            progress_callback: Callback de progression optionnel.

        Returns:
            Reponse avec les pages et annonces trouvees.
        """
        start_time = datetime.now()

        # 1. Rechercher les annonces
        search_params = SearchParameters(
            keywords=request.keywords,
            countries=request.countries,
            languages=request.languages,
            min_ads=request.min_ads,
        )

        search_result = self._ads_service.search_by_keywords(
            search_params,
            progress_callback=progress_callback,
        )

        # 2. Regrouper par page
        pages_dict: Dict[str, PageWithAds] = {}

        for ad in search_result.ads:
            page_id = str(ad.page_id)

            # Verifier blacklist
            if request.exclude_blacklisted and page_id in self._blacklist:
                continue

            if page_id not in pages_dict:
                page = Page.create(
                    page_id=page_id,
                    name=ad.page_name,
                    active_ads_count=0,
                )
                pages_dict[page_id] = PageWithAds(page=page, ads=[])

            pages_dict[page_id].ads.append(ad)

            # Ajouter le mot-cle
            if ad._keyword:
                pages_dict[page_id].keywords_found.add(ad._keyword)
                pages_dict[page_id].page.add_keyword(ad._keyword)

        # Mettre a jour le nombre d'ads
        for page_with_ads in pages_dict.values():
            page_with_ads.page.update_ads_count(len(page_with_ads.ads))

        pages_before_filter = len(pages_dict)

        # 3. Appliquer le filtre min_ads
        filtered_pages = [
            p for p in pages_dict.values()
            if p.ads_count >= request.min_ads
        ]

        # 4. Calculer les statistiques
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return SearchAdsResponse(
            pages=filtered_pages,
            total_ads_found=len(search_result.ads),
            unique_ads_count=search_result.total_unique_ads,
            pages_before_filter=pages_before_filter,
            pages_after_filter=len(filtered_pages),
            search_duration_ms=duration_ms,
            keywords_stats=search_result.ads_by_keyword,
        )

    def set_blacklist(self, blacklist: Set[str]) -> None:
        """Met a jour la blacklist."""
        self._blacklist = blacklist

    def add_to_blacklist(self, page_id: str) -> None:
        """Ajoute une page a la blacklist."""
        self._blacklist.add(page_id)
