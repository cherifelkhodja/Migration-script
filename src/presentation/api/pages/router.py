"""
Pages Router - Endpoints CRUD pour les pages/shops.

Responsabilite unique:
----------------------
Exposer les endpoints de gestion des pages Meta.
Delegue la logique metier aux repositories.

Endpoints:
----------
- GET /pages: Lister les pages
- GET /pages/{page_id}: Recuperer une page
- POST /pages: Creer une page
- PUT /pages/{page_id}: Mettre a jour une page
- DELETE /pages/{page_id}: Supprimer une page
- GET /pages/stats: Statistiques
- PUT /pages/{page_id}/classification: Classifier une page
- PUT /pages/{page_id}/favorite: Toggle favori
- PUT /pages/{page_id}/blacklist: Toggle blacklist
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from src.presentation.api.pages.schemas import (
    PageResponse,
    PageListResponse,
    CreatePageRequest,
    UpdatePageRequest,
    UpdateClassificationRequest,
    PageStatsResponse,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.entities.page import Page
from src.application.ports.repositories.page_repository import PageRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/pages", tags=["Pages"])


# ============ Dependencies ============

def get_page_repository() -> PageRepository:
    """Retourne le PageRepository."""
    from src.infrastructure.persistence.sqlalchemy_page_repository import (
        SqlAlchemyPageRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    return SqlAlchemyPageRepository(session)


def _page_to_response(page: Page) -> PageResponse:
    """Convertit une Page en PageResponse."""
    return PageResponse(
        page_id=str(page.page_id),
        name=page.name,
        website=page.website.value if page.website else None,
        cms=page.cms.name if page.cms else None,
        theme=page.theme,
        etat=page.etat.value if page.etat else None,
        active_ads_count=page.active_ads_count,
        product_count=page.product_count,
        category=page.category,
        subcategory=page.subcategory,
        currency=page.currency,
        is_favorite=page.is_favorite,
        is_blacklisted=page.is_blacklisted,
        keywords=list(page.keywords) if page.keywords else [],
        created_at=page.created_at,
        updated_at=page.updated_at,
        last_scan_at=page.last_scan_at,
    )


# ============ Endpoints ============

@router.get(
    "",
    response_model=PageListResponse,
    summary="Lister les pages",
    description="Retourne les pages avec pagination et filtres.",
)
def list_pages(
    page: int = Query(1, ge=1, description="Numero de page"),
    page_size: int = Query(20, ge=1, le=100, description="Taille de page"),
    etat: Optional[str] = Query(None, description="Filtrer par etat (L,XL,XXL)"),
    cms: Optional[str] = Query(None, description="Filtrer par CMS"),
    category: Optional[str] = Query(None, description="Filtrer par categorie"),
    is_favorite: Optional[bool] = Query(None, description="Filtrer par favoris"),
    is_blacklisted: Optional[bool] = Query(None, description="Filtrer par blacklist"),
    query: Optional[str] = Query(None, description="Recherche textuelle"),
    order_by: str = Query("updated_at", description="Champ de tri"),
    descending: bool = Query(True, description="Tri descendant"),
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Liste les pages avec pagination et filtres.
    """
    offset = (page - 1) * page_size

    # Construire les filtres
    filters = {}
    if etat:
        filters["etat"] = etat.split(",")
    if cms:
        filters["cms"] = cms.split(",")
    if category:
        filters["category"] = category
    if is_favorite is not None:
        filters["is_favorite"] = is_favorite
    if is_blacklisted is not None:
        filters["is_blacklisted"] = is_blacklisted

    # Recherche ou liste
    if query:
        pages = repo.search(query, filters=filters, limit=page_size, offset=offset)
        total = repo.count(filters={**filters, "query": query})
    else:
        pages = repo.find_all(
            limit=page_size,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
        total = repo.count(filters=filters if filters else None)

    items = [_page_to_response(p) for p in pages]
    total_pages = (total + page_size - 1) // page_size

    return PageListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get(
    "/stats",
    response_model=PageStatsResponse,
    summary="Statistiques des pages",
    description="Retourne les statistiques globales des pages.",
)
def get_pages_stats(
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Recupere les statistiques globales des pages.
    """
    stats = repo.get_statistics()
    etat_dist = repo.get_etat_distribution()
    cms_dist = repo.get_cms_distribution()
    cat_dist = repo.get_category_distribution()

    return PageStatsResponse(
        total_pages=stats.get("total", 0),
        total_with_website=stats.get("with_website", 0),
        total_with_cms=stats.get("with_cms", 0),
        total_favorites=stats.get("favorites", 0),
        total_blacklisted=stats.get("blacklisted", 0),
        etat_distribution=etat_dist,
        cms_distribution=cms_dist,
        category_distribution=cat_dist,
    )


@router.get(
    "/{page_id}",
    response_model=PageResponse,
    summary="Recuperer une page",
    description="Retourne une page par son ID.",
)
def get_page(
    page_id: str,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Recupere une page par son ID.
    """
    from src.domain.value_objects import PageId

    page = repo.get_by_id(PageId(page_id))
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    return _page_to_response(page)


@router.post(
    "",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Creer une page",
    description="Cree une nouvelle page.",
)
def create_page(
    data: CreatePageRequest,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Cree une nouvelle page.
    """
    from src.domain.value_objects import PageId, WebsiteUrl

    # Verifier si existe deja
    if repo.exists(PageId(data.page_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une page avec cet ID existe deja",
        )

    website = None
    if data.website:
        try:
            website = WebsiteUrl(data.website)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL invalide: {str(e)}",
            )

    page = Page.create(
        page_id=data.page_id,
        name=data.name,
        website=website,
    )

    saved = repo.save(page)

    logger.info(
        "page_created",
        user_id=str(user.id),
        page_id=data.page_id,
    )

    return _page_to_response(saved)


@router.put(
    "/{page_id}",
    response_model=PageResponse,
    summary="Mettre a jour une page",
    description="Met a jour une page existante.",
)
def update_page(
    page_id: str,
    data: UpdatePageRequest,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Met a jour une page.
    """
    from src.domain.value_objects import PageId, WebsiteUrl

    page = repo.get_by_id(PageId(page_id))
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    if data.name is not None:
        page.name = data.name

    if data.website is not None:
        try:
            page.website = WebsiteUrl(data.website) if data.website else None
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL invalide: {str(e)}",
            )

    if data.category is not None:
        page.category = data.category

    if data.subcategory is not None:
        page.subcategory = data.subcategory

    if data.is_favorite is not None:
        page.is_favorite = data.is_favorite

    if data.is_blacklisted is not None:
        page.is_blacklisted = data.is_blacklisted

    updated = repo.update(page)

    logger.info(
        "page_updated",
        user_id=str(user.id),
        page_id=page_id,
    )

    return _page_to_response(updated)


@router.delete(
    "/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une page",
    description="Supprime une page.",
)
def delete_page(
    page_id: str,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Supprime une page.
    """
    from src.domain.value_objects import PageId

    deleted = repo.delete(PageId(page_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    logger.info(
        "page_deleted",
        user_id=str(user.id),
        page_id=page_id,
    )


@router.put(
    "/{page_id}/classification",
    response_model=PageResponse,
    summary="Classifier une page",
    description="Met a jour la classification d'une page.",
)
def classify_page(
    page_id: str,
    data: UpdateClassificationRequest,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Met a jour la classification d'une page.
    """
    from src.domain.value_objects import PageId

    success = repo.update_classification(
        page_id=PageId(page_id),
        category=data.category,
        subcategory=data.subcategory,
        confidence=data.confidence,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    page = repo.get_by_id(PageId(page_id))

    logger.info(
        "page_classified",
        user_id=str(user.id),
        page_id=page_id,
        category=data.category,
    )

    return _page_to_response(page)


@router.put(
    "/{page_id}/favorite",
    response_model=PageResponse,
    summary="Toggle favori",
    description="Ajoute ou retire une page des favoris.",
)
def toggle_favorite(
    page_id: str,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Toggle le statut favori d'une page.
    """
    from src.domain.value_objects import PageId

    page = repo.get_by_id(PageId(page_id))
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    page.is_favorite = not page.is_favorite
    updated = repo.update(page)

    logger.info(
        "page_favorite_toggled",
        user_id=str(user.id),
        page_id=page_id,
        is_favorite=page.is_favorite,
    )

    return _page_to_response(updated)


@router.put(
    "/{page_id}/blacklist",
    response_model=PageResponse,
    summary="Toggle blacklist",
    description="Ajoute ou retire une page de la blacklist.",
)
def toggle_blacklist(
    page_id: str,
    user: User = Depends(get_current_user),
    repo: PageRepository = Depends(get_page_repository),
):
    """
    Toggle le statut blacklist d'une page.
    """
    from src.domain.value_objects import PageId

    page = repo.get_by_id(PageId(page_id))
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page non trouvee",
        )

    page.is_blacklisted = not page.is_blacklisted
    updated = repo.update(page)

    logger.info(
        "page_blacklist_toggled",
        user_id=str(user.id),
        page_id=page_id,
        is_blacklisted=page.is_blacklisted,
    )

    return _page_to_response(updated)
