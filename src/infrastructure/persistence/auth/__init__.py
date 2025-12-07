"""
Module de persistance pour l'authentification.

Adapters SQLAlchemy implementant les ports du domaine:
- SqlAlchemyUserRepository: Persistance des utilisateurs
- SqlAlchemyAuditRepository: Journal d'audit

Separation des responsabilites:
-------------------------------
Chaque repository a une responsabilite unique.
L'authentification est geree par les use cases.
"""

from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)

__all__ = [
    "SqlAlchemyUserRepository",
    "SqlAlchemyAuditRepository",
]
