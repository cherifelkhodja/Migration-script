"""
Adapter pour le service de recherche Meta Ads.

Cet adapter implemente l'interface AdsSearchService en delegant
les appels au client Meta API existant.
"""

from typing import Any

from src.application.ports.services.ads_search_service import (
    AdsSearchService,
    PageAdsResult,
    ProgressCallback,
    SearchParameters,
    SearchResult,
)
from src.domain.entities.ad import Ad
from src.domain.exceptions import RateLimitError, SearchError
from src.domain.value_objects import PageId


class MetaAdsSearchAdapter(AdsSearchService):
    """
    Adapter qui implemente AdsSearchService en utilisant le client Meta API.

    Cet adapter fait le pont entre l'interface du domaine et
    l'implementation concrete de l'API Meta.

    Example:
        >>> from app.meta_api import MetaAdsClient
        >>> client = MetaAdsClient(access_token="...")
        >>> adapter = MetaAdsSearchAdapter(client)
        >>> result = adapter.search_by_keywords(params)
    """

    def __init__(self, meta_client: Any) -> None:
        """
        Initialise l'adapter avec un client Meta API.

        Args:
            meta_client: Instance de MetaAdsClient du module app.meta_api.
        """
        self._client = meta_client

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
            Resultat de la recherche avec les annonces trouvees.

        Raises:
            SearchError: En cas d'erreur de recherche.
            RateLimitError: Si la limite de taux est atteinte.
        """
        all_ads: list[Ad] = []
        ads_by_keyword: dict[str, int] = {}
        unique_page_ids: set[str] = set()

        total_keywords = len(params.keywords)

        for idx, keyword in enumerate(params.keywords):
            if progress_callback:
                progress_callback(keyword, idx + 1, total_keywords)

            try:
                # Appeler le client Meta
                raw_ads = self._client.search_ads(
                    keyword=keyword,
                    countries=params.countries,
                    languages=params.languages,
                )

                # Convertir en entites Ad du domaine
                keyword_ads = []
                for raw in raw_ads:
                    try:
                        ad = Ad.from_meta_response(raw)
                        ad.set_keyword(keyword)
                        keyword_ads.append(ad)
                        unique_page_ids.add(str(ad.page_id))
                    except Exception:
                        # Ignorer les annonces malformees
                        continue

                ads_by_keyword[keyword] = len(keyword_ads)
                all_ads.extend(keyword_ads)

            except RuntimeError as e:
                error_msg = str(e)
                if "rate limit" in error_msg.lower():
                    raise RateLimitError(
                        service="Meta Ads API",
                        retry_after_seconds=60,
                    ) from e
                raise SearchError(error_msg, keyword=keyword) from e

        # Dedupliquer par ad_id
        unique_ads = {str(ad.id): ad for ad in all_ads}

        return SearchResult(
            ads=list(unique_ads.values()),
            ads_by_keyword=ads_by_keyword,
            total_unique_ads=len(unique_ads),
            pages_found=len(unique_page_ids),
        )

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
        try:
            raw_ads = self._client.get_ads_for_page(
                page_id=str(page_id),
                countries=countries,
                languages=languages or [],
            )

            ads = []
            for raw in raw_ads:
                try:
                    ad = Ad.from_meta_response(raw)
                    ads.append(ad)
                except Exception:
                    continue

            return PageAdsResult(
                ads=ads,
                total_count=len(ads),
                page_id=page_id,
            )

        except RuntimeError as e:
            raise SearchError(str(e)) from e

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
        results = {}

        for page_id in page_ids[:10]:  # Limite a 10 pages
            try:
                result = self.fetch_ads_for_page(
                    page_id=page_id,
                    countries=countries,
                    languages=languages,
                )
                results[str(page_id)] = result
            except SearchError:
                # Continuer avec les autres pages en cas d'erreur
                results[str(page_id)] = PageAdsResult(
                    ads=[],
                    total_count=0,
                    page_id=page_id,
                )

        return results

    def extract_website_from_ads(self, ads: list[Ad]) -> str | None:
        """
        Extrait l'URL du site web depuis les annonces.

        Args:
            ads: Liste d'annonces.

        Returns:
            URL extraite ou None.
        """
        for ad in ads:
            domain = ad.extracted_domain
            if domain:
                return f"https://{domain}"
        return None

    def extract_currency_from_ads(self, ads: list[Ad]) -> str | None:
        """
        Extrait la devise depuis les annonces.

        Args:
            ads: Liste d'annonces.

        Returns:
            Code devise ou None.
        """
        for ad in ads:
            if ad.currency:
                return ad.currency.code
        return None

    def is_available(self) -> bool:
        """
        Verifie si le service est disponible.

        Returns:
            True si le service est operationnel.
        """
        try:
            # Verifier que le client a un token
            token = getattr(self._client, "access_token", None)
            return bool(token)
        except Exception:
            return False

    def get_token_info(self) -> dict[str, Any]:
        """
        Retourne les informations sur les tokens API.

        Returns:
            Dictionnaire avec infos sur les tokens.
        """
        try:
            from app.meta_api import get_token_rotator

            rotator = get_token_rotator()
            if rotator:
                return {
                    "token_count": rotator.token_count,
                    "current_index": getattr(rotator, "_current_index", 0),
                    "has_proxies": rotator.has_proxy_tokens(),
                    "parallel_workers": rotator.get_parallel_workers_count(),
                }
            return {
                "token_count": 1,
                "current_index": 0,
                "has_proxies": False,
                "parallel_workers": 1,
            }
        except ImportError:
            return {"token_count": 1, "current_index": 0}
