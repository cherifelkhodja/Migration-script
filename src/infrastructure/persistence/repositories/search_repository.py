"""
Repository pour les recherches (logs, queue, historique).

Multi-tenancy:
--------------
Toutes les fonctions acceptent un parametre optionnel user_id (UUID).
- Si user_id est fourni: les donnees sont filtrees/associees a cet utilisateur
- Si user_id est None: les donnees sont considerees comme systeme/partagees
"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import UUID

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.sql import false as sql_false

from src.infrastructure.persistence.models import (
    SearchLog,
    SearchQueue,
    APICallLog,
    PageSearchHistory,
    WinningAdSearchHistory,
    PageRecherche,
    WinningAds,
)


def _apply_user_filter(query, model, user_id: Optional[UUID]):
    """
    Applique le filtre user_id a une query (isolation stricte).

    Si user_id est fourni: filtre par cet utilisateur.
    Si user_id est None: retourne un resultat vide (pas d'acces aux donnees partagees).
    """
    if user_id is not None:
        return query.filter(model.user_id == user_id)
    # Isolation stricte: si pas de user_id, retourner un resultat vide
    return query.filter(sql_false())


def create_search_log(
    db,
    keywords: str,
    countries: str,
    languages: str = "",
    min_ads: int = 1,
    selected_cms: str = "",
    user_id: Optional[UUID] = None
) -> int:
    """Cree un nouveau log de recherche."""
    with db.get_session() as session:
        log = SearchLog(
            user_id=user_id,
            keywords=keywords,
            countries=countries,
            languages=languages,
            min_ads=min_ads,
            selected_cms=selected_cms,
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(log)
        session.flush()
        return log.id


def update_search_log(db, log_id: int, **kwargs) -> bool:
    """Met a jour un log de recherche."""
    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False

        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)

        return True


def complete_search_log(
    db,
    log_id: int,
    status: str = "completed",
    error_message: str = None,
    metrics: dict = None,
    api_metrics: dict = None,
    **stats
) -> bool:
    """Complete un log de recherche avec metriques et stats API."""
    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False

        log.status = status
        log.ended_at = datetime.utcnow()
        if log.started_at:
            log.duration_seconds = (log.ended_at - log.started_at).total_seconds()
        if error_message:
            log.error_message = error_message

        # Appliquer les metriques de recherche
        if metrics:
            for key, value in metrics.items():
                if hasattr(log, key) and value is not None:
                    setattr(log, key, value)

        # Appliquer les metriques API
        if api_metrics:
            for key, value in api_metrics.items():
                # Convertir les dicts en JSON pour certains champs
                if key in ("scraper_errors_by_type", "api_details", "errors_list"):
                    if value and isinstance(value, (dict, list)):
                        setattr(log, key, json.dumps(value))
                elif hasattr(log, key) and value is not None:
                    setattr(log, key, value)

        # Appliquer les autres stats
        for key, value in stats.items():
            if hasattr(log, key):
                setattr(log, key, value)

        return True


def get_search_logs(
    db,
    limit: int = 50,
    status: str = None,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """Recupere les logs de recherche avec tous les champs."""
    with db.get_session() as session:
        query = session.query(SearchLog)
        query = _apply_user_filter(query, SearchLog, user_id)
        if status:
            query = query.filter(SearchLog.status == status)

        logs = query.order_by(desc(SearchLog.started_at)).limit(limit).all()

        return [
            {
                "id": l.id,
                "keywords": l.keywords,
                "countries": l.countries,
                "languages": l.languages,
                "min_ads": l.min_ads,
                "selected_cms": l.selected_cms,
                "status": l.status,
                "started_at": l.started_at,
                "ended_at": l.ended_at,
                "duration_seconds": l.duration_seconds,
                "error_message": l.error_message,
                "phases_data": json.loads(l.phases_data) if l.phases_data else [],
                # Stats de recherche
                "total_ads_found": l.total_ads_found,
                "total_pages_found": l.total_pages_found,
                "pages_after_filter": l.pages_after_filter,
                "pages_shopify": l.pages_shopify,
                "pages_other_cms": l.pages_other_cms,
                "winning_ads_count": l.winning_ads_count,
                "blacklisted_ads_skipped": l.blacklisted_ads_skipped,
                # Stats de sauvegarde
                "pages_saved": l.pages_saved,
                "ads_saved": l.ads_saved,
                "new_pages_count": l.new_pages_count,
                "existing_pages_updated": l.existing_pages_updated,
                "new_winning_ads_count": l.new_winning_ads_count,
                "existing_winning_ads_updated": l.existing_winning_ads_updated,
                # Stats API
                "meta_api_calls": l.meta_api_calls,
                "scraper_api_calls": l.scraper_api_calls,
                "web_requests": l.web_requests,
                "meta_api_errors": l.meta_api_errors,
                "scraper_api_errors": l.scraper_api_errors,
                "web_errors": l.web_errors,
                "rate_limit_hits": l.rate_limit_hits,
                "meta_api_avg_time": l.meta_api_avg_time,
                "scraper_api_avg_time": l.scraper_api_avg_time,
                "web_avg_time": l.web_avg_time,
                "scraper_api_cost": l.scraper_api_cost,
                "api_details": l.api_details,
                "errors_list": l.errors_list,
                "scraper_errors_by_type": l.scraper_errors_by_type,
            }
            for l in logs
        ]


def delete_search_log(db, log_id: int) -> bool:
    """Supprime un log de recherche."""
    with db.get_session() as session:
        deleted = session.query(SearchLog).filter(SearchLog.id == log_id).delete()
        return deleted > 0


def save_api_calls(db, search_log_id: int, calls: List[Dict]) -> int:
    """Sauvegarde les appels API."""
    count = 0
    with db.get_session() as session:
        for call in calls:
            api_call = APICallLog(
                search_log_id=search_log_id,
                api_type=call.get("api_type", ""),
                endpoint=call.get("endpoint", ""),
                success=call.get("success", True),
                response_time_ms=call.get("response_time_ms"),
                error_message=call.get("error_message"),
                created_at=datetime.utcnow(),
            )
            session.add(api_call)
            count += 1
    return count


# ============================================================================
# SEARCH QUEUE
# ============================================================================

def create_search_queue(
    db,
    keywords: str,
    countries: str = "FR",
    languages: str = "",
    min_ads: int = 1,
    ads_min: int = None,  # Alias for min_ads
    cms_filter: str = "",
    user_session: str = None,
    priority: int = 0,
    user_id: Optional[UUID] = None
) -> int:
    """Cree une recherche en queue."""
    # Support both min_ads and ads_min parameter names
    actual_min_ads = ads_min if ads_min is not None else min_ads
    with db.get_session() as session:
        search = SearchQueue(
            user_id=user_id,
            keywords=keywords,
            countries=countries,
            languages=languages,
            min_ads=actual_min_ads,
            cms_filter=cms_filter,
            user_session=user_session,
            priority=priority,
            status="pending",
            created_at=datetime.utcnow(),
        )
        session.add(search)
        session.flush()
        return search.id


def get_search_queue(db, search_id: int) -> Optional[Dict]:
    """Recupere une recherche de la queue."""
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if not search:
            return None

        return {
            "id": search.id,
            "keywords": search.keywords,
            "countries": search.countries,
            "status": search.status,
            "progress_percent": search.progress_percent,
            "current_phase": search.current_phase,
            "phase_name": search.phase_name,
            "message": search.message,
            "created_at": search.created_at,
        }


def update_search_queue_status(db, search_id: int, status: str, **kwargs) -> bool:
    """Met a jour le statut d'une recherche."""
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if not search:
            return False

        search.status = status
        search.updated_at = datetime.utcnow()

        for key, value in kwargs.items():
            if hasattr(search, key):
                setattr(search, key, value)

        return True


def update_search_queue_progress(
    db,
    search_id: int,
    phase: int = None,
    phase_name: str = None,
    percent: int = None,
    message: str = None,
    phases_data: List = None
) -> bool:
    """Met a jour la progression d'une recherche."""
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if not search:
            return False

        if phase is not None:
            search.current_phase = phase
        if phase_name is not None:
            search.phase_name = phase_name
        if percent is not None:
            search.progress_percent = percent
        if message is not None:
            search.message = message
        if phases_data is not None:
            search.phases_data = json.dumps(phases_data)
        search.updated_at = datetime.utcnow()

        return True


def cancel_search_queue(db, search_id: int) -> bool:
    """Annule une recherche."""
    return update_search_queue_status(db, search_id, "cancelled")


def get_pending_searches(db, limit: int = 5) -> List[Dict]:
    """Recupere les recherches en attente."""
    with db.get_session() as session:
        searches = session.query(SearchQueue).filter(
            SearchQueue.status == "pending"
        ).order_by(SearchQueue.created_at).limit(limit).all()

        return [get_search_queue(db, s.id) for s in searches]


def get_queue_stats(db, user_id: Optional[UUID] = None) -> Dict:
    """Statistiques de la queue."""
    with db.get_session() as session:
        base_query = session.query(func.count(SearchQueue.id))
        if user_id is not None:
            base_query = base_query.filter(SearchQueue.user_id == user_id)

        pending = base_query.filter(
            SearchQueue.status == "pending"
        ).scalar() or 0

        running_q = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "running"
        )
        if user_id is not None:
            running_q = running_q.filter(SearchQueue.user_id == user_id)
        running = running_q.scalar() or 0

        completed_q = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "completed"
        )
        if user_id is not None:
            completed_q = completed_q.filter(SearchQueue.user_id == user_id)
        completed = completed_q.scalar() or 0

        failed_q = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "failed"
        )
        if user_id is not None:
            failed_q = failed_q.filter(SearchQueue.user_id == user_id)
        failed = failed_q.scalar() or 0

        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total": pending + running + completed + failed,
        }


def get_interrupted_searches(db) -> List:
    """
    Retourne les recherches interrompues (status='running' depuis longtemps).

    Returns:
        Liste des SearchQueue interrompues.
    """
    with db.get_session() as session:
        threshold = datetime.utcnow() - timedelta(minutes=30)
        interrupted = session.query(SearchQueue).filter(
            SearchQueue.status == "running",
            or_(
                SearchQueue.updated_at < threshold,
                SearchQueue.updated_at.is_(None)
            )
        ).all()
        return interrupted


def restart_search_queue(db, search_id: int) -> bool:
    """
    Relance une recherche interrompue specifique.

    Args:
        db: DatabaseManager
        search_id: ID de la recherche a relancer

    Returns:
        True si la recherche a ete relancee, False sinon.
    """
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if search and search.status in ("running", "failed"):
            search.status = "pending"
            search.updated_at = datetime.utcnow()
            return True
        return False


def recover_interrupted_searches(db) -> int:
    """
    Recupere les recherches interrompues (status='running' mais worker arrete).
    Les remet en 'pending' pour retraitement.

    Returns:
        Nombre de recherches recuperees.
    """
    with db.get_session() as session:
        # Recherches 'running' depuis plus de 30 minutes = probablement interrompues
        threshold = datetime.utcnow() - timedelta(minutes=30)

        interrupted = session.query(SearchQueue).filter(
            SearchQueue.status == "running",
            or_(
                SearchQueue.updated_at < threshold,
                SearchQueue.updated_at.is_(None)
            )
        ).all()

        count = 0
        for search in interrupted:
            search.status = "pending"
            search.message = "Recherche interrompue - relancee automatiquement"
            search.updated_at = datetime.utcnow()
            count += 1

        return count


# ============================================================================
# SEARCH HISTORY
# ============================================================================

def record_page_search_history(
    db,
    page_id: str,
    search_log_id: int,
    user_id: Optional[UUID] = None
) -> bool:
    """Enregistre l'historique de recherche d'une page."""
    with db.get_session() as session:
        query = session.query(PageSearchHistory).filter(
            PageSearchHistory.page_id == str(page_id),
            PageSearchHistory.search_log_id == search_log_id
        )
        query = _apply_user_filter(query, PageSearchHistory, user_id)
        existing = query.first()

        if not existing:
            history = PageSearchHistory(
                user_id=user_id,
                page_id=str(page_id),
                search_log_id=search_log_id,
                found_at=datetime.utcnow(),
            )
            session.add(history)

        return True


def record_pages_search_history_batch(
    db,
    page_ids: List[str],
    search_log_id: int,
    user_id: Optional[UUID] = None
) -> int:
    """Enregistre l'historique pour plusieurs pages."""
    count = 0
    for page_id in page_ids:
        if record_page_search_history(db, page_id, search_log_id, user_id=user_id):
            count += 1
    return count


def record_winning_ad_search_history(
    db,
    ad_id: str,
    search_log_id: int,
    user_id: Optional[UUID] = None
) -> bool:
    """Enregistre l'historique de recherche d'une winning ad."""
    with db.get_session() as session:
        query = session.query(WinningAdSearchHistory).filter(
            WinningAdSearchHistory.ad_id == str(ad_id),
            WinningAdSearchHistory.search_log_id == search_log_id
        )
        query = _apply_user_filter(query, WinningAdSearchHistory, user_id)
        existing = query.first()

        if not existing:
            history = WinningAdSearchHistory(
                user_id=user_id,
                ad_id=str(ad_id),
                search_log_id=search_log_id,
                found_at=datetime.utcnow(),
            )
            session.add(history)

        return True


def record_winning_ads_search_history_batch(
    db,
    ad_ids: List[str],
    search_log_id: int,
    user_id: Optional[UUID] = None
) -> int:
    """Enregistre l'historique pour plusieurs winning ads."""
    count = 0
    for ad_id in ad_ids:
        if record_winning_ad_search_history(db, ad_id, search_log_id, user_id=user_id):
            count += 1
    return count


def get_search_history_stats(db, days: int = 30, user_id: Optional[UUID] = None) -> Dict:
    """Statistiques de l'historique de recherche."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        search_q = session.query(func.count(SearchLog.id)).filter(
            SearchLog.started_at >= cutoff
        )
        if user_id is not None:
            search_q = search_q.filter(SearchLog.user_id == user_id)
        total_searches = search_q.scalar() or 0

        completed_q = session.query(func.count(SearchLog.id)).filter(
            SearchLog.started_at >= cutoff,
            SearchLog.status == "completed"
        )
        if user_id is not None:
            completed_q = completed_q.filter(SearchLog.user_id == user_id)
        completed = completed_q.scalar() or 0

        pages_q = session.query(func.count(func.distinct(PageSearchHistory.page_id))).filter(
            PageSearchHistory.found_at >= cutoff
        )
        if user_id is not None:
            pages_q = pages_q.filter(PageSearchHistory.user_id == user_id)
        total_pages = pages_q.scalar() or 0

        winning_q = session.query(func.count(func.distinct(WinningAdSearchHistory.ad_id))).filter(
            WinningAdSearchHistory.found_at >= cutoff
        )
        if user_id is not None:
            winning_q = winning_q.filter(WinningAdSearchHistory.user_id == user_id)
        total_winning = winning_q.scalar() or 0

        return {
            "total_searches": total_searches,
            "completed_searches": completed,
            "unique_pages_found": total_pages,
            "unique_winning_ads": total_winning,
        }


def update_search_log_phases(db, log_id: int, phases_completed: list) -> bool:
    """
    Met a jour les phases completees d'un log de recherche.

    Permet de tracker la progression d'une recherche en sauvegardant
    les phases completees (ex: "Recherche", "Detection CMS", etc.)

    Args:
        db: Instance DatabaseManager
        log_id: ID du log de recherche
        phases_completed: Liste des phases completees

    Returns:
        True si mise a jour reussie, False sinon
    """
    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False

        # Stocker les phases en JSON
        try:
            log.phases_data = json.dumps(phases_completed)
        except Exception:
            pass

        return True


def get_search_logs_stats(db, days: int = 30, user_id: Optional[UUID] = None) -> Dict:
    """
    Statistiques des logs de recherche.

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours a considerer
        user_id: UUID de l'utilisateur pour multi-tenancy

    Returns:
        Dict avec les statistiques des recherches
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    def apply_user_filter(query):
        if user_id is not None:
            return query.filter(SearchLog.user_id == user_id)
        return query

    with db.get_session() as session:
        # Total searches
        total_searches = apply_user_filter(
            session.query(func.count(SearchLog.id)).filter(
                SearchLog.started_at >= cutoff
            )
        ).scalar() or 0

        # By status
        by_status = {}
        for status in ["completed", "failed", "running", "preview"]:
            count = apply_user_filter(
                session.query(func.count(SearchLog.id)).filter(
                    SearchLog.started_at >= cutoff,
                    SearchLog.status == status
                )
            ).scalar() or 0
            by_status[status] = count

        # Average duration
        avg_duration = apply_user_filter(
            session.query(func.avg(SearchLog.duration_seconds)).filter(
                SearchLog.started_at >= cutoff,
                SearchLog.duration_seconds.isnot(None)
            )
        ).scalar() or 0

        # Total pages found
        total_pages = apply_user_filter(
            session.query(func.sum(SearchLog.total_pages_found)).filter(
                SearchLog.started_at >= cutoff
            )
        ).scalar() or 0

        # API stats (if columns exist)
        total_meta_api = 0
        total_scraper_api = 0
        total_web_requests = 0
        total_rate_limits = 0

        try:
            total_meta_api = apply_user_filter(
                session.query(func.sum(SearchLog.meta_api_calls)).filter(
                    SearchLog.started_at >= cutoff
                )
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_scraper_api = apply_user_filter(
                session.query(func.sum(SearchLog.scraper_api_calls)).filter(
                    SearchLog.started_at >= cutoff
                )
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_web_requests = apply_user_filter(
                session.query(func.sum(SearchLog.web_requests)).filter(
                    SearchLog.started_at >= cutoff
                )
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_rate_limits = apply_user_filter(
                session.query(func.sum(SearchLog.rate_limit_hits)).filter(
                    SearchLog.started_at >= cutoff
                )
            ).scalar() or 0
        except Exception:
            pass

        return {
            "total_searches": total_searches,
            "by_status": by_status,
            "avg_duration_seconds": float(avg_duration) if avg_duration else 0,
            "total_pages_found": int(total_pages) if total_pages else 0,
            "total_meta_api_calls": int(total_meta_api) if total_meta_api else 0,
            "total_scraper_api_calls": int(total_scraper_api) if total_scraper_api else 0,
            "total_web_requests": int(total_web_requests) if total_web_requests else 0,
            "total_rate_limit_hits": int(total_rate_limits) if total_rate_limits else 0,
        }


def get_pages_for_search(db, search_log_id: int, limit: int = 100, user_id: Optional[UUID] = None) -> List[Dict]:
    """
    Recupere les pages trouvees lors d'une recherche specifique.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du log de recherche
        limit: Nombre maximum de resultats
        user_id: UUID de l'utilisateur (multi-tenancy)

    Returns:
        Liste des pages avec leurs informations
    """
    # Isolation stricte
    if user_id is None:
        return []

    with db.get_session() as session:
        # Joindre PageSearchHistory avec PageRecherche (filtrer les deux par user_id)
        results = session.query(
            PageRecherche,
            PageSearchHistory.was_new,
            PageSearchHistory.ads_count_at_discovery,
            PageSearchHistory.keyword_matched
        ).join(
            PageSearchHistory,
            and_(
                PageRecherche.page_id == PageSearchHistory.page_id,
                PageRecherche.user_id == PageSearchHistory.user_id
            )
        ).filter(
            PageSearchHistory.search_log_id == search_log_id,
            PageSearchHistory.user_id == user_id
        ).limit(limit).all()

        return [
            {
                "page_id": p.PageRecherche.page_id,
                "page_name": p.PageRecherche.page_name,
                "lien_site": p.PageRecherche.lien_site,
                "cms": p.PageRecherche.cms,
                "etat": p.PageRecherche.etat,
                "nombre_ads_active": p.PageRecherche.nombre_ads_active,
                "thematique": p.PageRecherche.thematique,
                "subcategory": getattr(p.PageRecherche, 'subcategory', None),
                "pays": p.PageRecherche.pays,
                "was_new": p.was_new,
                "ads_count_at_discovery": p.ads_count_at_discovery,
                "keyword_matched": p.keyword_matched,
            }
            for p in results
        ]


def get_winning_ads_for_search(db, search_log_id: int, limit: int = 100, user_id: Optional[UUID] = None) -> List[Dict]:
    """
    Recupere les winning ads trouvees lors d'une recherche specifique.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du log de recherche
        limit: Nombre maximum de resultats
        user_id: UUID de l'utilisateur (multi-tenancy)

    Returns:
        Liste des winning ads avec leurs informations
    """
    # Isolation stricte
    if user_id is None:
        return []

    with db.get_session() as session:
        # Joindre WinningAdSearchHistory avec WinningAds (filtrer les deux par user_id)
        results = session.query(
            WinningAds,
            WinningAdSearchHistory.was_new,
            WinningAdSearchHistory.reach_at_discovery,
            WinningAdSearchHistory.age_days_at_discovery,
            WinningAdSearchHistory.matched_criteria.label('history_criteria')
        ).join(
            WinningAdSearchHistory,
            and_(
                WinningAds.ad_id == WinningAdSearchHistory.ad_id,
                WinningAds.user_id == WinningAdSearchHistory.user_id
            )
        ).filter(
            WinningAdSearchHistory.search_log_id == search_log_id,
            WinningAdSearchHistory.user_id == user_id
        ).limit(limit).all()

        return [
            {
                "id": a.WinningAds.id,
                "ad_id": a.WinningAds.ad_id,
                "page_id": a.WinningAds.page_id,
                "page_name": a.WinningAds.page_name,
                "lien_site": a.WinningAds.lien_site,
                "eu_total_reach": a.WinningAds.eu_total_reach,
                "ad_age_days": a.WinningAds.ad_age_days,
                "matched_criteria": a.WinningAds.matched_criteria,
                "ad_snapshot_url": a.WinningAds.ad_snapshot_url,
                "date_scan": a.WinningAds.date_scan,
                "was_new": a.was_new,
                "reach_at_discovery": a.reach_at_discovery,
                "age_days_at_discovery": a.age_days_at_discovery,
            }
            for a in results
        ]
