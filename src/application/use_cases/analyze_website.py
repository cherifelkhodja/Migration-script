"""
Use Case: Analyse de sites web.
"""

from dataclasses import dataclass

from src.application.ports.services.website_analyzer_service import (
    WebsiteAnalysisResult,
    WebsiteAnalyzerService,
)
from src.domain.entities.page import Page


@dataclass
class AnalyzeWebsiteRequest:
    """
    Requete d'analyse de site web.

    Attributes:
        pages: Pages a analyser.
        country_code: Code pays pour le sitemap.
        skip_if_cached: Passer si deja en cache.
        max_concurrent: Nombre max de requetes paralleles.
    """

    pages: list[Page]
    country_code: str = "FR"
    skip_if_cached: bool = True
    max_concurrent: int = 5


@dataclass
class PageAnalysisResult:
    """
    Resultat d'analyse d'une page.

    Attributes:
        page: Page analysee (mise a jour).
        analysis: Resultat de l'analyse web.
        from_cache: Si le resultat vient du cache.
    """

    page: Page
    analysis: WebsiteAnalysisResult
    from_cache: bool = False


@dataclass
class AnalyzeWebsiteResponse:
    """
    Reponse de l'analyse.

    Attributes:
        results: Resultats par page.
        analyzed_count: Nombre de sites analyses.
        cached_count: Nombre de sites en cache.
        error_count: Nombre d'erreurs.
        cms_distribution: Distribution par CMS.
    """

    results: list[PageAnalysisResult]
    analyzed_count: int
    cached_count: int
    error_count: int
    cms_distribution: dict[str, int]

    @property
    def success_count(self) -> int:
        return self.analyzed_count - self.error_count


class AnalyzeWebsiteUseCase:
    """
    Use Case: Analyse de sites web.

    Ce use case orchestre l'analyse des sites e-commerce
    (detection CMS, comptage produits, extraction metadonnees).

    Example:
        >>> analyzer = AnalyzeWebsiteUseCase(web_service)
        >>> request = AnalyzeWebsiteRequest(pages=my_pages)
        >>> response = analyzer.execute(request)
        >>> print(f"{response.success_count} sites analyses")
    """

    def __init__(
        self,
        website_analyzer: WebsiteAnalyzerService,
    ) -> None:
        """
        Initialise le use case.

        Args:
            website_analyzer: Service d'analyse de sites.
        """
        self._analyzer = website_analyzer

    def execute(
        self,
        request: AnalyzeWebsiteRequest,
    ) -> AnalyzeWebsiteResponse:
        """
        Execute l'analyse des sites.

        Args:
            request: Requete avec les pages a analyser.

        Returns:
            Reponse avec les resultats d'analyse.
        """
        results: list[PageAnalysisResult] = []
        cms_distribution: dict[str, int] = {}
        error_count = 0
        cached_count = 0

        # Preparer les URLs a analyser
        urls_to_analyze = []
        page_by_url = {}

        for page in request.pages:
            if not page.website:
                continue

            url = page.website.value
            urls_to_analyze.append(url)
            page_by_url[url] = page

        # Analyser en batch
        if urls_to_analyze:
            analysis_results = self._analyzer.analyze_batch(
                urls_to_analyze,
                country_code=request.country_code,
                max_concurrent=request.max_concurrent,
            )

            # Traiter les resultats
            for url, analysis in analysis_results.items():
                page = page_by_url.get(url)
                if not page:
                    continue

                # Mettre a jour la page avec les resultats
                if analysis.is_success:
                    page.update_cms(
                        analysis.cms.name,
                        theme=analysis.theme,
                    )
                    page.update_product_count(analysis.product_count)

                    if analysis.currency:
                        page.currency = analysis.currency

                    # Compter les CMS
                    cms_name = analysis.cms.name
                    cms_distribution[cms_name] = cms_distribution.get(cms_name, 0) + 1
                else:
                    error_count += 1

                results.append(PageAnalysisResult(
                    page=page,
                    analysis=analysis,
                    from_cache=False,
                ))

        return AnalyzeWebsiteResponse(
            results=results,
            analyzed_count=len(results),
            cached_count=cached_count,
            error_count=error_count,
            cms_distribution=cms_distribution,
        )

    def analyze_single(
        self,
        page: Page,
        country_code: str = "FR",
    ) -> PageAnalysisResult:
        """
        Analyse un seul site.

        Args:
            page: Page a analyser.
            country_code: Code pays.

        Returns:
            Resultat d'analyse.
        """
        if not page.website:
            return PageAnalysisResult(
                page=page,
                analysis=WebsiteAnalysisResult(
                    url="",
                    error="Pas d'URL de site",
                ),
            )

        analysis = self._analyzer.analyze(
            page.website.value,
            country_code=country_code,
        )

        if analysis.is_success:
            page.update_cms(analysis.cms.name, theme=analysis.theme)
            page.update_product_count(analysis.product_count)

        return PageAnalysisResult(
            page=page,
            analysis=analysis,
        )
