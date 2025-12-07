"""
MemoryNotificationRepository - Implementation in-memory du repository.

Responsabilite unique:
----------------------
Stocker les notifications en memoire (dev/tests).
En production, remplacer par SqlAlchemyNotificationRepository.
"""

from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional
from threading import Lock

from src.domain.entities.notification import Notification
from src.domain.ports.notification_repository import NotificationRepository


class MemoryNotificationRepository(NotificationRepository):
    """
    Implementation in-memory du NotificationRepository.

    Thread-safe avec verrou.
    Utile pour dev/tests, remplacer par SQL en production.
    """

    def __init__(self):
        """Initialise le repository."""
        self._notifications: dict[UUID, Notification] = {}
        self._lock = Lock()

    def save(self, notification: Notification) -> Notification:
        """Sauvegarde une notification."""
        with self._lock:
            self._notifications[notification.id] = notification
            return notification

    def get_by_id(self, notification_id: UUID) -> Optional[Notification]:
        """Recupere une notification par son ID."""
        return self._notifications.get(notification_id)

    def find_by_user(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Recupere les notifications d'un utilisateur."""
        with self._lock:
            user_notifs = [
                n for n in self._notifications.values()
                if n.user_id == user_id
            ]

            if unread_only:
                user_notifs = [n for n in user_notifs if not n.is_read]

            # Trier par date decroissante
            user_notifs.sort(key=lambda n: n.created_at, reverse=True)

            return user_notifs[offset:offset + limit]

    def count_unread(self, user_id: UUID) -> int:
        """Compte les notifications non lues."""
        with self._lock:
            return sum(
                1 for n in self._notifications.values()
                if n.user_id == user_id and not n.is_read
            )

    def mark_as_read(self, notification_id: UUID) -> bool:
        """Marque une notification comme lue."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification:
                notification.mark_as_read()
                return True
            return False

    def mark_all_as_read(self, user_id: UUID) -> int:
        """Marque toutes les notifications comme lues."""
        with self._lock:
            count = 0
            for notification in self._notifications.values():
                if notification.user_id == user_id and not notification.is_read:
                    notification.mark_as_read()
                    count += 1
            return count

    def delete(self, notification_id: UUID) -> bool:
        """Supprime une notification."""
        with self._lock:
            if notification_id in self._notifications:
                del self._notifications[notification_id]
                return True
            return False

    def delete_old(self, days: int = 30) -> int:
        """Supprime les notifications anciennes."""
        with self._lock:
            cutoff = datetime.now() - timedelta(days=days)
            old_ids = [
                n.id for n in self._notifications.values()
                if n.created_at < cutoff
            ]
            for notification_id in old_ids:
                del self._notifications[notification_id]
            return len(old_ids)

    def clear(self) -> None:
        """Vide le repository (pour tests)."""
        with self._lock:
            self._notifications.clear()
