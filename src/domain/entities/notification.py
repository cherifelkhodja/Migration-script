"""
Notification Entity - Entite de notification.

Responsabilite unique:
----------------------
Representer une notification utilisateur.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum


class NotificationType(Enum):
    """Types de notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

    # Business notifications
    SEARCH_COMPLETED = "search_completed"
    WINNING_ADS_FOUND = "winning_ads_found"
    SCAN_COMPLETED = "scan_completed"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    PAYMENT_FAILED = "payment_failed"
    EXPORT_READY = "export_ready"


@dataclass
class Notification:
    """
    Entite Notification.

    Represente une notification pour un utilisateur.

    Attributes:
        id: Identifiant unique.
        user_id: ID de l'utilisateur destinataire.
        type: Type de notification.
        title: Titre court.
        message: Message complet.
        data: Donnees additionnelles (JSON).
        is_read: True si lue.
        created_at: Date de creation.
        read_at: Date de lecture.
    """

    user_id: UUID
    type: NotificationType
    title: str
    message: str
    id: UUID = field(default_factory=uuid4)
    data: Optional[dict] = None
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    read_at: Optional[datetime] = None

    def mark_as_read(self) -> None:
        """Marque la notification comme lue."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now()

    def mark_as_unread(self) -> None:
        """Marque la notification comme non lue."""
        self.is_read = False
        self.read_at = None

    @classmethod
    def create(
        cls,
        user_id: UUID,
        type: NotificationType,
        title: str,
        message: str,
        data: Optional[dict] = None,
    ) -> "Notification":
        """
        Factory pour creer une notification.

        Args:
            user_id: ID utilisateur.
            type: Type de notification.
            title: Titre.
            message: Message.
            data: Donnees additionnelles.

        Returns:
            Nouvelle notification.
        """
        return cls(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=data,
        )

    @classmethod
    def search_completed(
        cls,
        user_id: UUID,
        keywords: list[str],
        pages_found: int,
        ads_found: int,
    ) -> "Notification":
        """Notification de recherche terminee."""
        return cls.create(
            user_id=user_id,
            type=NotificationType.SEARCH_COMPLETED,
            title="Recherche terminee",
            message=f"Recherche pour '{', '.join(keywords)}': {pages_found} pages, {ads_found} ads trouvees.",
            data={
                "keywords": keywords,
                "pages_found": pages_found,
                "ads_found": ads_found,
            },
        )

    @classmethod
    def winning_ads_found(
        cls,
        user_id: UUID,
        count: int,
    ) -> "Notification":
        """Notification de winning ads detectees."""
        return cls.create(
            user_id=user_id,
            type=NotificationType.WINNING_ADS_FOUND,
            title="Winning Ads detectees",
            message=f"{count} nouvelles winning ads ont ete detectees.",
            data={"count": count},
        )

    @classmethod
    def payment_failed(
        cls,
        user_id: UUID,
        reason: str,
    ) -> "Notification":
        """Notification d'echec de paiement."""
        return cls.create(
            user_id=user_id,
            type=NotificationType.PAYMENT_FAILED,
            title="Echec de paiement",
            message=f"Votre paiement a echoue: {reason}. Veuillez mettre a jour vos informations.",
            data={"reason": reason},
        )

    @classmethod
    def export_ready(
        cls,
        user_id: UUID,
        export_type: str,
        download_url: str,
    ) -> "Notification":
        """Notification d'export pret."""
        return cls.create(
            user_id=user_id,
            type=NotificationType.EXPORT_READY,
            title="Export pret",
            message=f"Votre export {export_type} est pret au telechargement.",
            data={
                "export_type": export_type,
                "download_url": download_url,
            },
        )
