"""
Notifications Router - Endpoints de notifications in-app.

Responsabilite unique:
----------------------
Exposer les endpoints de gestion des notifications.
Delegue la logique metier au repository.

Endpoints:
----------
- GET /notifications: Lister les notifications
- GET /notifications/unread-count: Nombre de non lues
- PUT /notifications/{id}/read: Marquer comme lue
- PUT /notifications/read-all: Marquer toutes comme lues
- DELETE /notifications/{id}: Supprimer une notification
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from src.presentation.api.notifications.schemas import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.entities.notification import Notification
from src.domain.ports.notification_repository import NotificationRepository
from src.infrastructure.adapters.memory_notification_repository import (
    MemoryNotificationRepository,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Singleton du repository (en production, injecter via DI)
_notification_repo = MemoryNotificationRepository()


def get_notification_repository() -> NotificationRepository:
    """Retourne le NotificationRepository."""
    return _notification_repo


def _notification_to_response(notification: Notification) -> NotificationResponse:
    """Convertit une Notification en NotificationResponse."""
    return NotificationResponse(
        id=notification.id,
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        data=notification.data,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Lister les notifications",
    description="Retourne les notifications de l'utilisateur.",
)
def list_notifications(
    unread_only: bool = Query(False, description="Seulement les non lues"),
    limit: int = Query(50, ge=1, le=100, description="Nombre max"),
    offset: int = Query(0, ge=0, description="Offset pagination"),
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Liste les notifications de l'utilisateur connecte.
    """
    notifications = repo.find_by_user(
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = repo.count_unread(user.id)

    return NotificationListResponse(
        items=[_notification_to_response(n) for n in notifications],
        total=len(notifications),
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Nombre de notifications non lues",
    description="Retourne le compteur de notifications non lues.",
)
def get_unread_count(
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Retourne le nombre de notifications non lues.
    Utile pour afficher un badge dans l'UI.
    """
    count = repo.count_unread(user.id)
    return UnreadCountResponse(unread_count=count)


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Recuperer une notification",
    description="Retourne une notification par son ID.",
)
def get_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Recupere une notification specifique.
    """
    notification = repo.get_by_id(notification_id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification non trouvee",
        )

    # Verifier que la notification appartient a l'utilisateur
    if notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    return _notification_to_response(notification)


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Marquer comme lue",
    description="Marque une notification comme lue.",
)
def mark_as_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Marque une notification comme lue.
    """
    notification = repo.get_by_id(notification_id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification non trouvee",
        )

    if notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    repo.mark_as_read(notification_id)

    # Recharger pour avoir read_at
    notification = repo.get_by_id(notification_id)

    logger.info(
        "notification_read",
        user_id=str(user.id),
        notification_id=str(notification_id),
    )

    return _notification_to_response(notification)


@router.put(
    "/read-all",
    response_model=MarkReadResponse,
    summary="Marquer toutes comme lues",
    description="Marque toutes les notifications comme lues.",
)
def mark_all_as_read(
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Marque toutes les notifications de l'utilisateur comme lues.
    """
    count = repo.mark_all_as_read(user.id)

    logger.info(
        "all_notifications_read",
        user_id=str(user.id),
        count=count,
    )

    return MarkReadResponse(marked_count=count)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notification",
    description="Supprime une notification.",
)
def delete_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repository),
):
    """
    Supprime une notification.
    """
    notification = repo.get_by_id(notification_id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification non trouvee",
        )

    if notification.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    repo.delete(notification_id)

    logger.info(
        "notification_deleted",
        user_id=str(user.id),
        notification_id=str(notification_id),
    )
