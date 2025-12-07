"""
NotificationRepository Port - Interface du repository de notifications.

Responsabilite unique:
----------------------
Definir le contrat pour la persistance des notifications.
"""

from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional

from src.domain.entities.notification import Notification


class NotificationRepository(ABC):
    """
    Interface pour la persistance des Notifications.

    Toutes les implementations (SQL, Redis, etc.) doivent
    respecter ce contrat.
    """

    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        """
        Sauvegarde une notification.

        Args:
            notification: Notification a sauvegarder.

        Returns:
            Notification sauvegardee.
        """
        pass

    @abstractmethod
    def get_by_id(self, notification_id: UUID) -> Optional[Notification]:
        """
        Recupere une notification par son ID.

        Args:
            notification_id: ID de la notification.

        Returns:
            Notification si trouvee, None sinon.
        """
        pass

    @abstractmethod
    def find_by_user(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """
        Recupere les notifications d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur.
            unread_only: True pour ne retourner que les non lues.
            limit: Nombre maximum.
            offset: Decalage pour pagination.

        Returns:
            Liste des notifications.
        """
        pass

    @abstractmethod
    def count_unread(self, user_id: UUID) -> int:
        """
        Compte les notifications non lues d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur.

        Returns:
            Nombre de notifications non lues.
        """
        pass

    @abstractmethod
    def mark_as_read(self, notification_id: UUID) -> bool:
        """
        Marque une notification comme lue.

        Args:
            notification_id: ID de la notification.

        Returns:
            True si mise a jour reussie.
        """
        pass

    @abstractmethod
    def mark_all_as_read(self, user_id: UUID) -> int:
        """
        Marque toutes les notifications d'un utilisateur comme lues.

        Args:
            user_id: ID de l'utilisateur.

        Returns:
            Nombre de notifications mises a jour.
        """
        pass

    @abstractmethod
    def delete(self, notification_id: UUID) -> bool:
        """
        Supprime une notification.

        Args:
            notification_id: ID de la notification.

        Returns:
            True si supprimee.
        """
        pass

    @abstractmethod
    def delete_old(self, days: int = 30) -> int:
        """
        Supprime les notifications plus anciennes que X jours.

        Args:
            days: Age maximum en jours.

        Returns:
            Nombre de notifications supprimees.
        """
        pass
