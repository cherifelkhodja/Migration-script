"""
Ads Router - Endpoints de recherche d'annonces.

Responsabilite unique:
----------------------
Exposer les endpoints de recherche et winning ads.
Delegue la logique metier aux Use Cases.

Endpoints:
----------
- POST /ads/search: Rechercher des annonces
- GET /ads/winning: Lister les winning ads
- POST /ads/winning/detect: Detecter les winning ads
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from src.presentation.api.ads.schemas import (
    SearchAdsRequest,
    SearchAdsResponse,
    PageWithAdsResponse,
    AdResponse,
    WinningAdResponse,
    WinningAdsListResponse,
    DetectWinningRequest,
    DetectWinningResponse,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.application.use_cases.search_ads import (
    SearchAdsUseCase,
    SearchAdsRequest as UseCaseSearchRequest,
)
from src.application.use_cases.detect_winning_ads import (
    DetectWinningAdsUseCase,
    DetectWinningAdsRequest as UseCaseDetectRequest,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ads", tags=["Ads"])


# ============ Dependencies ============

def get_search_use_case() -> SearchAdsUseCase:
    """Retourne le SearchAdsUseCase."""
    from src.infrastructure.adapters.meta_ads_service import MetaAdsService

    ads_service = MetaAdsService()
    return SearchAdsUseCase(ads_service=ads_service)


def get_winning_use_case() -> DetectWinningAdsUseCase:
    """Retourne le DetectWinningAdsUseCase."""
    from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
        SqlAlchemyWinningAdRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    repo = SqlAlchemyWinningAdRepository(session)
    return DetectWinningAdsUseCase(winning_ad_repository=repo)


# ============ Endpoints ============

@router.post(
    "/search",
    response_model=SearchAdsResponse,
    summary="Rechercher des annonces",
    description="Recherche des annonces Meta par mots-cles.",
)
def search_ads(
    data: SearchAdsRequest,
    user: User = Depends(get_current_user),
    use_case: SearchAdsUseCase = Depends(get_search_use_case),
):
    """
    Recherche des annonces Meta Ads.

    Retourne les pages avec leurs annonces groupees.
    """
    logger.info(
        "ads_search_started",
        user_id=str(user.id),
        keywords=data.keywords,
        countries=data.countries,
    )

    request = UseCaseSearchRequest(
        keywords=data.keywords,
        countries=data.countries,
        languages=data.languages,
        min_ads=data.min_ads,
        cms_filter=data.cms_filter,
        exclude_blacklisted=data.exclude_blacklisted,
    )

    response = use_case.execute(request)

    # Convertir en schema de reponse
    pages = []
    for page_with_ads in response.pages:
        ads = [
            AdResponse(
                id=str(ad.id),
                page_id=str(ad.page_id),
                page_name=ad.page_name,
                ad_creative_link_title=ad.ad_creative_link_title,
                ad_delivery_start_time=ad.ad_delivery_start_time,
                eu_total_reach=ad.eu_total_reach,
                snapshot_url=ad.snapshot_url,
            )
            for ad in page_with_ads.ads
        ]

        pages.append(PageWithAdsResponse(
            page_id=str(page_with_ads.page.page_id),
            page_name=page_with_ads.page.name,
            ads_count=page_with_ads.ads_count,
            ads=ads,
            keywords_found=list(page_with_ads.keywords_found),
        ))

    logger.info(
        "ads_search_completed",
        user_id=str(user.id),
        pages_found=len(pages),
        total_ads=response.total_ads_found,
        duration_ms=response.search_duration_ms,
    )

    return SearchAdsResponse(
        pages=pages,
        total_ads_found=response.total_ads_found,
        unique_ads_count=response.unique_ads_count,
        pages_count=response.pages_count,
        search_duration_ms=response.search_duration_ms,
        keywords_stats=response.keywords_stats,
    )


@router.get(
    "/winning",
    response_model=WinningAdsListResponse,
    summary="Lister les winning ads",
    description="Retourne les winning ads detectees avec pagination.",
)
def list_winning_ads(
    page: int = Query(1, ge=1, description="Numero de page"),
    page_size: int = Query(20, ge=1, le=100, description="Taille de page"),
    user: User = Depends(get_current_user),
):
    """
    Liste les winning ads avec pagination.
    """
    from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
        SqlAlchemyWinningAdRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    repo = SqlAlchemyWinningAdRepository(session)

    offset = (page - 1) * page_size
    winning_ads = repo.find_all(limit=page_size, offset=offset)
    total = repo.count()

    items = [
        WinningAdResponse(
            id=wa.id,
            ad_id=str(wa.ad_id),
            page_id=str(wa.page_id),
            page_name=wa.page_name,
            reach=wa.reach,
            days_active=wa.days_active,
            winning_score=wa.winning_score,
            matched_criteria=wa.matched_criteria,
            detected_at=wa.detected_at,
            snapshot_url=wa.snapshot_url,
        )
        for wa in winning_ads
    ]

    total_pages = (total + page_size - 1) // page_size

    return WinningAdsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get(
    "/winning/{ad_id}",
    response_model=WinningAdResponse,
    summary="Recuperer une winning ad",
    description="Retourne une winning ad par son ID.",
)
def get_winning_ad(
    ad_id: int,
    user: User = Depends(get_current_user),
):
    """
    Recupere une winning ad par son ID.
    """
    from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
        SqlAlchemyWinningAdRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    repo = SqlAlchemyWinningAdRepository(session)

    winning_ad = repo.get_by_id(ad_id)
    if not winning_ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Winning ad non trouvee",
        )

    return WinningAdResponse(
        id=winning_ad.id,
        ad_id=str(winning_ad.ad_id),
        page_id=str(winning_ad.page_id),
        page_name=winning_ad.page_name,
        reach=winning_ad.reach,
        days_active=winning_ad.days_active,
        winning_score=winning_ad.winning_score,
        matched_criteria=winning_ad.matched_criteria,
        detected_at=winning_ad.detected_at,
        snapshot_url=winning_ad.snapshot_url,
    )


@router.delete(
    "/winning/{ad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une winning ad",
    description="Supprime une winning ad par son ID.",
)
def delete_winning_ad(
    ad_id: int,
    user: User = Depends(get_current_user),
):
    """
    Supprime une winning ad.
    """
    from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
        SqlAlchemyWinningAdRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    repo = SqlAlchemyWinningAdRepository(session)

    deleted = repo.delete(ad_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Winning ad non trouvee",
        )
