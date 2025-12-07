"""
Websites Router - Endpoints d'analyse de sites web.

Responsabilite unique:
----------------------
Exposer les endpoints d'analyse de sites e-commerce.
Delegue la logique metier aux Use Cases.

Endpoints:
----------
- POST /websites/analyze: Analyser un site
- POST /websites/analyze/batch: Analyser plusieurs sites
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from src.presentation.api.websites.schemas import (
    AnalyzeWebsiteRequest,
    AnalyzeBatchRequest,
    WebsiteAnalysisResponse,
    AnalyzeBatchResponse,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.entities.page import Page
from src.application.use_cases.analyze_website import (
    AnalyzeWebsiteUseCase,
    AnalyzeWebsiteRequest as UseCaseRequest,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/websites", tags=["Websites"])


# ============ Dependencies ============

def get_analyze_use_case() -> AnalyzeWebsiteUseCase:
    """Retourne le AnalyzeWebsiteUseCase."""
    from src.infrastructure.adapters.website_analyzer import WebsiteAnalyzer

    analyzer = WebsiteAnalyzer()
    return AnalyzeWebsiteUseCase(website_analyzer=analyzer)


# ============ Endpoints ============

@router.post(
    "/analyze",
    response_model=WebsiteAnalysisResponse,
    summary="Analyser un site web",
    description="Analyse un site e-commerce (CMS, produits, theme).",
)
def analyze_website(
    data: AnalyzeWebsiteRequest,
    user: User = Depends(get_current_user),
    use_case: AnalyzeWebsiteUseCase = Depends(get_analyze_use_case),
):
    """
    Analyse un site web unique.

    Detecte le CMS, compte les produits, extrait les metadonnees.
    """
    logger.info(
        "website_analysis_started",
        user_id=str(user.id),
        url=data.url,
    )

    # Creer une Page temporaire pour l'analyse
    from src.domain.value_objects import WebsiteUrl

    try:
        page = Page.create(
            page_id="temp",
            name="Analysis",
            website=WebsiteUrl(data.url),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL invalide: {str(e)}",
        )

    result = use_case.analyze_single(page, country_code=data.country_code)

    logger.info(
        "website_analysis_completed",
        user_id=str(user.id),
        url=data.url,
        cms=result.analysis.cms.name if result.analysis.is_success else None,
        success=result.analysis.is_success,
    )

    return WebsiteAnalysisResponse(
        url=data.url,
        is_success=result.analysis.is_success,
        cms=result.analysis.cms.name if result.analysis.is_success else None,
        theme=result.analysis.theme,
        product_count=result.analysis.product_count,
        currency=result.analysis.currency,
        error=result.analysis.error,
        analyzed_at=datetime.now(),
    )


@router.post(
    "/analyze/batch",
    response_model=AnalyzeBatchResponse,
    summary="Analyser plusieurs sites",
    description="Analyse un batch de sites e-commerce.",
)
def analyze_websites_batch(
    data: AnalyzeBatchRequest,
    user: User = Depends(get_current_user),
    use_case: AnalyzeWebsiteUseCase = Depends(get_analyze_use_case),
):
    """
    Analyse plusieurs sites en batch.
    """
    logger.info(
        "batch_analysis_started",
        user_id=str(user.id),
        url_count=len(data.urls),
    )

    # Creer les Pages temporaires
    from src.domain.value_objects import WebsiteUrl

    pages = []
    for i, url in enumerate(data.urls):
        try:
            page = Page.create(
                page_id=f"temp_{i}",
                name=f"Analysis_{i}",
                website=WebsiteUrl(url),
            )
            pages.append(page)
        except ValueError:
            # URL invalide, ignorer
            continue

    if not pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune URL valide fournie",
        )

    request = UseCaseRequest(
        pages=pages,
        country_code=data.country_code,
        max_concurrent=data.max_concurrent,
    )

    response = use_case.execute(request)

    results = []
    for result in response.results:
        url = result.page.website.value if result.page.website else ""
        results.append(WebsiteAnalysisResponse(
            url=url,
            is_success=result.analysis.is_success,
            cms=result.analysis.cms.name if result.analysis.is_success else None,
            theme=result.analysis.theme,
            product_count=result.analysis.product_count,
            currency=result.analysis.currency,
            error=result.analysis.error,
            analyzed_at=datetime.now(),
        ))

    logger.info(
        "batch_analysis_completed",
        user_id=str(user.id),
        analyzed=response.analyzed_count,
        success=response.success_count,
        errors=response.error_count,
    )

    return AnalyzeBatchResponse(
        results=results,
        analyzed_count=response.analyzed_count,
        success_count=response.success_count,
        error_count=response.error_count,
        cms_distribution=response.cms_distribution,
    )
