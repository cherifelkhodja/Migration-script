"""
Notifications Schemas - Modeles Pydantic pour les endpoints notifications.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les notifications in-app.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class NotificationResponse(BaseModel):
    """Representation d'une notification."""

    id: UUID
    type: str
    title: str
    message: str
    data: Optional[dict[str, Any]] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    """Liste de notifications avec compteur."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Compteur de notifications non lues."""

    unread_count: int


class MarkReadRequest(BaseModel):
    """Requete pour marquer comme lu."""

    notification_ids: list[UUID] = Field(
        default=[],
        description="IDs a marquer comme lus (vide = tous)"
    )


class MarkReadResponse(BaseModel):
    """Reponse de marquage comme lu."""

    marked_count: int
