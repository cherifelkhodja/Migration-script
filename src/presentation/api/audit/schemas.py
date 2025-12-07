"""
Audit Schemas - Modeles Pydantic pour les endpoints audit.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les logs d'audit.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class AuditLogResponse(BaseModel):
    """Representation d'un log d'audit."""

    id: int
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Liste paginee de logs d'audit."""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AuditStatsResponse(BaseModel):
    """Statistiques des logs d'audit."""

    total_logs: int
    logs_today: int
    logs_this_week: int
    action_distribution: dict[str, int]
    top_users: list[dict[str, Any]]


class AuditActionTypes(BaseModel):
    """Liste des types d'actions."""

    actions: list[str]
