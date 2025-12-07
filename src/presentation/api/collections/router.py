"""
Collections Router - Endpoints CRUD pour les collections.

Responsabilite unique:
----------------------
Exposer les endpoints de gestion des collections de pages.

Endpoints:
----------
- GET /collections: Lister les collections
- GET /collections/{id}: Recuperer une collection
- POST /collections: Creer une collection
- PUT /collections/{id}: Mettre a jour une collection
- DELETE /collections/{id}: Supprimer une collection
- POST /collections/{id}/pages: Ajouter une page
- DELETE /collections/{id}/pages/{page_id}: Retirer une page
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.presentation.api.collections.schemas import (
    CollectionResponse,
    CollectionDetailResponse,
    CollectionListResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
    AddPageToCollectionRequest,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.entities.collection import Collection
from src.application.ports.repositories.collection_repository import CollectionRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


# ============ Dependencies ============

def get_collection_repository() -> CollectionRepository:
    """Retourne le CollectionRepository."""
    from src.infrastructure.persistence.repositories.collection_repository import (
        SqlAlchemyCollectionRepository,
    )
    from src.infrastructure.persistence.database import get_db_session

    session = get_db_session()
    return SqlAlchemyCollectionRepository(session)


def _collection_to_response(collection: Collection) -> CollectionResponse:
    """Convertit une Collection en CollectionResponse."""
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        page_count=len(collection.page_ids) if collection.page_ids else 0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def _collection_to_detail(collection: Collection) -> CollectionDetailResponse:
    """Convertit une Collection en CollectionDetailResponse."""
    return CollectionDetailResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        page_ids=[str(pid) for pid in collection.page_ids] if collection.page_ids else [],
        page_count=len(collection.page_ids) if collection.page_ids else 0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


# ============ Endpoints ============

@router.get(
    "",
    response_model=CollectionListResponse,
    summary="Lister les collections",
    description="Retourne toutes les collections.",
)
def list_collections(
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Liste toutes les collections.
    """
    collections = repo.find_all()
    items = [_collection_to_response(c) for c in collections]

    return CollectionListResponse(
        items=items,
        total=len(items),
    )


@router.get(
    "/{collection_id}",
    response_model=CollectionDetailResponse,
    summary="Recuperer une collection",
    description="Retourne une collection avec ses pages.",
)
def get_collection(
    collection_id: int,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Recupere une collection par son ID.
    """
    collection = repo.get_by_id(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection non trouvee",
        )

    return _collection_to_detail(collection)


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Creer une collection",
    description="Cree une nouvelle collection.",
)
def create_collection(
    data: CreateCollectionRequest,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Cree une nouvelle collection.
    """
    # Verifier si le nom existe deja
    existing = repo.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une collection avec ce nom existe deja",
        )

    collection = Collection(
        name=data.name,
        description=data.description,
    )

    saved = repo.save(collection)

    logger.info(
        "collection_created",
        user_id=str(user.id),
        collection_id=saved.id,
        name=data.name,
    )

    return _collection_to_response(saved)


@router.put(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Mettre a jour une collection",
    description="Met a jour une collection existante.",
)
def update_collection(
    collection_id: int,
    data: UpdateCollectionRequest,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Met a jour une collection.
    """
    collection = repo.get_by_id(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection non trouvee",
        )

    if data.name is not None:
        # Verifier unicite du nom
        existing = repo.get_by_name(data.name)
        if existing and existing.id != collection_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une collection avec ce nom existe deja",
            )
        collection.name = data.name

    if data.description is not None:
        collection.description = data.description

    updated = repo.save(collection)

    logger.info(
        "collection_updated",
        user_id=str(user.id),
        collection_id=collection_id,
    )

    return _collection_to_response(updated)


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une collection",
    description="Supprime une collection.",
)
def delete_collection(
    collection_id: int,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Supprime une collection.
    """
    deleted = repo.delete(collection_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection non trouvee",
        )

    logger.info(
        "collection_deleted",
        user_id=str(user.id),
        collection_id=collection_id,
    )


@router.post(
    "/{collection_id}/pages",
    response_model=CollectionDetailResponse,
    summary="Ajouter une page",
    description="Ajoute une page a une collection.",
)
def add_page_to_collection(
    collection_id: int,
    data: AddPageToCollectionRequest,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Ajoute une page a une collection.
    """
    from src.domain.value_objects import PageId

    collection = repo.get_by_id(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection non trouvee",
        )

    success = repo.add_page_to_collection(collection_id, PageId(data.page_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'ajouter la page",
        )

    # Recharger la collection
    collection = repo.get_by_id(collection_id)

    logger.info(
        "page_added_to_collection",
        user_id=str(user.id),
        collection_id=collection_id,
        page_id=data.page_id,
    )

    return _collection_to_detail(collection)


@router.delete(
    "/{collection_id}/pages/{page_id}",
    response_model=CollectionDetailResponse,
    summary="Retirer une page",
    description="Retire une page d'une collection.",
)
def remove_page_from_collection(
    collection_id: int,
    page_id: str,
    user: User = Depends(get_current_user),
    repo: CollectionRepository = Depends(get_collection_repository),
):
    """
    Retire une page d'une collection.
    """
    from src.domain.value_objects import PageId

    collection = repo.get_by_id(collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection non trouvee",
        )

    success = repo.remove_page_from_collection(collection_id, PageId(page_id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de retirer la page",
        )

    # Recharger la collection
    collection = repo.get_by_id(collection_id)

    logger.info(
        "page_removed_from_collection",
        user_id=str(user.id),
        collection_id=collection_id,
        page_id=page_id,
    )

    return _collection_to_detail(collection)
