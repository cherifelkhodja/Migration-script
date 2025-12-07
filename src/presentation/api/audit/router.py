"""
Audit Router - Endpoints de consultation des logs d'audit.

Responsabilite unique:
----------------------
Exposer les endpoints de lecture des logs d'audit.
Reserve aux administrateurs.

Endpoints:
----------
- GET /audit/logs: Lister les logs avec filtres
- GET /audit/logs/me: Mes propres logs
- GET /audit/stats: Statistiques globales (admin)
- GET /audit/actions: Liste des types d'actions
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID

from src.presentation.api.audit.schemas import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditStatsResponse,
    AuditActionTypes,
)
from src.presentation.api.dependencies import (
    get_current_user,
    get_current_admin,
    get_audit_repository,
)
from src.domain.entities.user import User
from src.domain.ports.audit_repository import AuditRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

# Liste des actions possibles
AUDIT_ACTIONS = [
    # Authentication
    "login_success",
    "login_failed",
    "logout",
    "password_changed",
    "password_reset_requested",
    "password_reset_completed",

    # Users
    "user_created",
    "user_updated",
    "user_deleted",

    # Pages
    "page_created",
    "page_updated",
    "page_deleted",
    "page_classified",
    "page_favorite_toggled",
    "page_blacklist_toggled",

    # Collections
    "collection_created",
    "collection_updated",
    "collection_deleted",
    "page_added_to_collection",
    "page_removed_from_collection",

    # Search & Jobs
    "search_executed",
    "job_created",
    "job_cancelled",
    "export_requested",

    # Billing
    "subscription_created",
    "subscription_updated",
    "subscription_cancelled",
    "payment_succeeded",
    "payment_failed",
]


def _dict_to_response(log_dict: dict) -> AuditLogResponse:
    """Convertit un dict de log en AuditLogResponse."""
    return AuditLogResponse(
        id=log_dict["id"],
        user_id=log_dict.get("user_id"),
        username=log_dict.get("username"),
        action=log_dict["action"],
        resource_type=log_dict.get("resource_type"),
        resource_id=log_dict.get("resource_id"),
        details=log_dict.get("details"),
        ip_address=log_dict.get("ip_address"),
        created_at=log_dict["created_at"],
    )


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    summary="Lister les logs d'audit (admin)",
    description="Retourne les logs d'audit avec filtres. Reserve aux admins.",
)
def list_audit_logs(
    page: int = Query(1, ge=1, description="Numero de page"),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page"),
    action: Optional[str] = Query(None, description="Filtrer par action"),
    user_id: Optional[UUID] = Query(None, description="Filtrer par utilisateur"),
    days: int = Query(30, ge=1, le=365, description="Jours d'historique"),
    admin: User = Depends(get_current_admin),
    repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Liste les logs d'audit avec filtres.
    Reserve aux administrateurs.
    """
    offset = (page - 1) * page_size
    limit = page_size

    # Recuperer les logs selon les filtres
    if action:
        logs = repo.find_by_action(action, days=days, limit=500)
    elif user_id:
        logs = repo.find_by_user(user_id, days=days, limit=500)
    else:
        # Tous les logs (via find_by_action avec action vide - fallback)
        logs = repo.find_by_action("", days=days, limit=500)
        # Note: En production, ajouter une methode find_all() au repository

    # Pagination manuelle
    total = len(logs)
    paginated_logs = logs[offset:offset + limit]
    total_pages = (total + page_size - 1) // page_size

    return AuditLogListResponse(
        items=[_dict_to_response(log) for log in paginated_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get(
    "/logs/me",
    response_model=AuditLogListResponse,
    summary="Mes logs d'audit",
    description="Retourne les logs d'audit de l'utilisateur connecte.",
)
def list_my_audit_logs(
    page: int = Query(1, ge=1, description="Numero de page"),
    page_size: int = Query(50, ge=1, le=100, description="Taille de page"),
    days: int = Query(30, ge=1, le=90, description="Jours d'historique"),
    user: User = Depends(get_current_user),
    repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Liste les logs d'audit de l'utilisateur connecte.
    Chaque utilisateur peut voir ses propres logs.
    """
    offset = (page - 1) * page_size

    logs = repo.find_by_user(user.id, days=days, limit=500)

    # Pagination
    total = len(logs)
    paginated_logs = logs[offset:offset + page_size]
    total_pages = (total + page_size - 1) // page_size

    return AuditLogListResponse(
        items=[_dict_to_response(log) for log in paginated_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get(
    "/stats",
    response_model=AuditStatsResponse,
    summary="Statistiques d'audit (admin)",
    description="Retourne les statistiques des logs d'audit.",
)
def get_audit_stats(
    admin: User = Depends(get_current_admin),
    repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Retourne les statistiques globales des logs d'audit.
    Reserve aux administrateurs.
    """
    # Recuperer les logs des 30 derniers jours
    logs_30d = repo.find_by_action("", days=30, limit=10000)

    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # Calculer les stats
    logs_today = sum(1 for log in logs_30d if log["created_at"] >= today)
    logs_this_week = sum(1 for log in logs_30d if log["created_at"] >= week_ago)

    # Distribution par action
    action_counts = {}
    for log in logs_30d:
        action = log["action"]
        action_counts[action] = action_counts.get(action, 0) + 1

    # Top utilisateurs
    user_counts = {}
    for log in logs_30d:
        username = log.get("username") or "system"
        user_counts[username] = user_counts.get(username, 0) + 1

    top_users = sorted(
        [{"username": k, "count": v} for k, v in user_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return AuditStatsResponse(
        total_logs=len(logs_30d),
        logs_today=logs_today,
        logs_this_week=logs_this_week,
        action_distribution=action_counts,
        top_users=top_users,
    )


@router.get(
    "/actions",
    response_model=AuditActionTypes,
    summary="Types d'actions",
    description="Retourne la liste des types d'actions disponibles.",
)
def get_action_types(
    user: User = Depends(get_current_user),
):
    """
    Retourne la liste des types d'actions possibles.
    Utile pour filtrer les logs.
    """
    return AuditActionTypes(actions=AUDIT_ACTIONS)
