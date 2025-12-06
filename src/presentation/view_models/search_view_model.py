"""
View Model pour la recherche d'annonces.

Encapsule la logique de presentation pour la fonctionnalite
de recherche d'annonces.
"""

from dataclasses import dataclass, field
from typing import Any

from src.application.ports.services.ads_search_service import AdsSearchService
from src.application.use_cases.detect_winning_ads import (
    DetectWinningAdsRequest,
    DetectWinningAdsUseCase,
)
from src.application.use_cases.search_ads import (
    SearchAdsRequest,
    SearchAdsResponse,
    SearchAdsUseCase,
)
from src.domain.entities.ad import Ad
from src.domain.entities.winning_ad import WinningAd


@dataclass
class SearchResultItem:
    """
    Element de resultat de recherche pour l'affichage.

    Attributes:
        page_id: ID de la page.
        page_name: Nom de la page.
        ads_count: Nombre d'annonces.
        etat: Etat calcule (XS, S, M, L, XL, XXL).
        website: URL du site.
        cms: CMS detecte.
        winning_count: Nombre de winning ads.
        keywords: Mots-cles associes.
    """

    page_id: str
    page_name: str
    ads_count: int
    etat: str
    website: str | None = None
    cms: str | None = None
    winning_count: int = 0
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour DataFrame."""
        return {
            "page_id": self.page_id,
            "page_name": self.page_name,
            "ads_count": self.ads_count,
            "etat": self.etat,
            "website": self.website or "",
            "cms": self.cms or "Unknown",
            "winning_count": self.winning_count,
            "keywords": ", ".join(self.keywords),
        }


@dataclass
class SearchStats:
    """
    Statistiques de recherche pour l'affichage.

    Attributes:
        total_pages: Nombre total de pages.
        total_ads: Nombre total d'annonces.
        unique_ads: Nombre d'annonces uniques.
        winning_ads: Nombre de winning ads.
        duration_ms: Duree de la recherche en ms.
        etat_distribution: Distribution par etat.
        keyword_stats: Stats par mot-cle.
    """

    total_pages: int
    total_ads: int
    unique_ads: int
    winning_ads: int
    duration_ms: int
    etat_distribution: dict[str, int] = field(default_factory=dict)
    keyword_stats: dict[str, int] = field(default_factory=dict)

    @property
    def winning_rate(self) -> float:
        """Taux de winning ads."""
        if self.total_ads == 0:
            return 0.0
        return (self.winning_ads / self.total_ads) * 100


class SearchViewModel:
    """
    View Model pour la recherche d'annonces.

    Orchestre les use cases et formate les donnees pour l'UI.

    Example:
        >>> vm = SearchViewModel(ads_service, winning_repo)
        >>> results = vm.search(["bijoux"], ["FR"])
        >>> for item in results:
        ...     print(f"{item.page_name}: {item.ads_count} ads")
    """

    def __init__(
        self,
        ads_service: AdsSearchService,
        winning_repository: Any | None = None,
        blacklist: set[str] | None = None,
    ) -> None:
        """
        Initialise le view model.

        Args:
            ads_service: Service de recherche d'annonces.
            winning_repository: Repository de winning ads (optionnel).
            blacklist: Set des page_ids a exclure.
        """
        self._search_use_case = SearchAdsUseCase(
            ads_service=ads_service,
            blacklist=blacklist,
        )
        self._detect_winning_use_case = DetectWinningAdsUseCase(
            winning_ad_repository=winning_repository,
        )

        # Resultats caches
        self._last_response: SearchAdsResponse | None = None
        self._last_winning: list[WinningAd] = []
        self._last_stats: SearchStats | None = None

    def search(
        self,
        keywords: list[str],
        countries: list[str],
        languages: list[str] | None = None,
        min_ads: int = 1,
        progress_callback: Any | None = None,
    ) -> list[SearchResultItem]:
        """
        Execute une recherche et retourne les resultats formates.

        Args:
            keywords: Mots-cles a rechercher.
            countries: Codes pays.
            languages: Codes langues.
            min_ads: Minimum d'annonces par page.
            progress_callback: Callback de progression.

        Returns:
            Liste des resultats formates pour l'affichage.
        """
        # Executer la recherche
        request = SearchAdsRequest(
            keywords=keywords,
            countries=countries,
            languages=languages or ["fr"],
            min_ads=min_ads,
        )

        self._last_response = self._search_use_case.execute(
            request,
            progress_callback=progress_callback,
        )

        # Detecter les winning ads
        all_ads = []
        for page_with_ads in self._last_response.pages:
            all_ads.extend(page_with_ads.ads)

        if all_ads:
            winning_request = DetectWinningAdsRequest(ads=all_ads)
            winning_response = self._detect_winning_use_case.execute(winning_request)
            self._last_winning = winning_response.winning_ads
        else:
            self._last_winning = []

        # Construire les resultats
        winning_by_page: dict[str, int] = {}
        for winning in self._last_winning:
            page_id = str(winning.ad.page_id)
            winning_by_page[page_id] = winning_by_page.get(page_id, 0) + 1

        results = []
        etat_distribution: dict[str, int] = {}

        for page_with_ads in self._last_response.pages:
            page = page_with_ads.page
            etat_str = page.etat.level.value if page.etat else "XS"

            etat_distribution[etat_str] = etat_distribution.get(etat_str, 0) + 1

            item = SearchResultItem(
                page_id=str(page.id),
                page_name=page.name,
                ads_count=page_with_ads.ads_count,
                etat=etat_str,
                website=str(page.website) if page.website else None,
                cms=page.cms.type.value if page.cms else None,
                winning_count=winning_by_page.get(str(page.id), 0),
                keywords=list(page_with_ads.keywords_found),
            )
            results.append(item)

        # Calculer les stats
        self._last_stats = SearchStats(
            total_pages=self._last_response.pages_count,
            total_ads=self._last_response.total_ads_found,
            unique_ads=self._last_response.unique_ads_count,
            winning_ads=len(self._last_winning),
            duration_ms=self._last_response.search_duration_ms,
            etat_distribution=etat_distribution,
            keyword_stats=self._last_response.keywords_stats,
        )

        return results

    @property
    def stats(self) -> SearchStats | None:
        """Retourne les statistiques de la derniere recherche."""
        return self._last_stats

    @property
    def winning_ads(self) -> list[WinningAd]:
        """Retourne les winning ads de la derniere recherche."""
        return self._last_winning

    def get_page_ads(self, page_id: str) -> list[Ad]:
        """
        Retourne les annonces d'une page specifique.

        Args:
            page_id: ID de la page.

        Returns:
            Liste des annonces de la page.
        """
        if not self._last_response:
            return []

        for page_with_ads in self._last_response.pages:
            if str(page_with_ads.page.id) == page_id:
                return page_with_ads.ads

        return []

    def to_dataframe_data(self) -> list[dict]:
        """
        Convertit les resultats en donnees pour DataFrame.

        Returns:
            Liste de dictionnaires pour pandas.DataFrame.
        """
        if not self._last_response:
            return []

        results = []
        for page_with_ads in self._last_response.pages:
            page = page_with_ads.page
            results.append({
                "page_id": str(page.id),
                "page_name": page.name,
                "ads_count": page_with_ads.ads_count,
                "etat": page.etat.level.value if page.etat else "XS",
                "website": str(page.website) if page.website else "",
                "cms": page.cms.type.value if page.cms else "Unknown",
                "keywords": ", ".join(page_with_ads.keywords_found),
            })

        return results

    def set_blacklist(self, blacklist: set[str]) -> None:
        """Met a jour la blacklist."""
        self._search_use_case.set_blacklist(blacklist)

    def add_to_blacklist(self, page_id: str) -> None:
        """Ajoute une page a la blacklist."""
        self._search_use_case.add_to_blacklist(page_id)
