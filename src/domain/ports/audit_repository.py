"""
Port AuditRepository - Interface pour le journal d'audit.

Definit le contrat pour l'enregistrement des actions utilisateur.
Chaque action sensible (login, modification, export) est tracee.

Responsabilite unique:
----------------------
Enregistrer et recuperer les logs d'audit.

Actions tracees:
----------------
- Authentification (login, logout, echecs)
- Modifications (pages, settings, users)
- Exports de donnees
- Operations d'administration
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class AuditRepository(ABC):
    """
    Interface Repository pour les logs d'audit.

    Contrat pour la tracabilite des actions.
    Implementee par SqlAlchemyAuditRepository.
    """

    @abstractmethod
    def log(
        self,
        user_id: Optional[UUID],
        username: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Enregistre une action dans le journal.

        Args:
            user_id: UUID de l'utilisateur (None si systeme).
            username: Nom d'utilisateur (pour historique).
            action: Type d'action (login_success, page_updated, etc).
            resource_type: Type de ressource concernee.
            resource_id: Identifiant de la ressource.
            details: Details supplementaires (dict).
            ip_address: Adresse IP du client.
        """
        ...

    @abstractmethod
    def find_by_user(
        self,
        user_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Recupere les logs d'un utilisateur."""
        ...

    @abstractmethod
    def find_by_action(
        self,
        action: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Recupere les logs d'un type d'action."""
        ...
