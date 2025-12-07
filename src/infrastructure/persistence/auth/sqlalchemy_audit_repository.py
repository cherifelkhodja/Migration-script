"""
SqlAlchemyAuditRepository - Adapter SQLAlchemy pour l'audit.

Implemente le port AuditRepository avec SQLAlchemy.
Responsabilite unique: Enregistrement et lecture des logs d'audit.

Les logs ne sont jamais supprimes (compliance).
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import json

from sqlalchemy import desc

from src.domain.ports.audit_repository import AuditRepository
from src.infrastructure.persistence.models import AuditLog
from src.infrastructure.persistence.database import DatabaseManager


class SqlAlchemyAuditRepository(AuditRepository):
    """
    Repository SQLAlchemy pour les logs d'audit.

    Attributes:
        db: DatabaseManager pour les sessions.
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialise le repository.

        Args:
            db: Instance DatabaseManager.
        """
        self._db = db

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
            user_id: UUID de l'utilisateur.
            username: Nom d'utilisateur.
            action: Type d'action.
            resource_type: Type de ressource.
            resource_id: ID de la ressource.
            details: Details supplementaires.
            ip_address: Adresse IP.
        """
        with self._db.get_session() as session:
            entry = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
            )
            session.add(entry)
            session.commit()

    def find_by_user(
        self,
        user_id: UUID,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Recupere les logs d'un utilisateur."""
        since = datetime.utcnow() - timedelta(days=days)

        with self._db.get_session() as session:
            logs = session.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= since
            ).order_by(desc(AuditLog.created_at)).limit(limit).all()

            return [self._to_dict(log) for log in logs]

    def find_by_action(
        self,
        action: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Recupere les logs d'un type d'action."""
        since = datetime.utcnow() - timedelta(days=days)

        with self._db.get_session() as session:
            logs = session.query(AuditLog).filter(
                AuditLog.action == action,
                AuditLog.created_at >= since
            ).order_by(desc(AuditLog.created_at)).limit(limit).all()

            return [self._to_dict(log) for log in logs]

    def _to_dict(self, log: AuditLog) -> Dict[str, Any]:
        """Convertit un log en dictionnaire."""
        return {
            "id": log.id,
            "user_id": str(log.user_id) if log.user_id else None,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": json.loads(log.details) if log.details else None,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
