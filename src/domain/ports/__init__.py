"""
Ports du domaine (Hexagonal Architecture).

Les Ports sont des interfaces (Protocol) definissant les contrats
entre le domaine et le monde exterieur.

Ports disponibles:
------------------
- TenantContext: Contexte utilisateur pour multi-tenancy
- TenantAwareMixin: Mixin pour entites avec owner
- UserRepository: CRUD utilisateurs
- AuditRepository: Journal d'audit

Pattern Port/Adapter:
---------------------
    [Domain]              [Infrastructure]
    TenantContext  <-->  StreamlitTenantContext
    UserRepository <-->  SqlAlchemyUserRepository
"""

from src.domain.ports.tenant_context import TenantContext
from src.domain.ports.tenant_aware import TenantAwareMixin
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository

__all__ = [
    "TenantContext",
    "TenantAwareMixin",
    "UserRepository",
    "AuditRepository",
]
