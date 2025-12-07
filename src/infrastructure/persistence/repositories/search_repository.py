"""
Repository pour les recherches (logs, queue, historique).
"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy import func, desc, and_, or_

from src.infrastructure.persistence.models import (
    SearchLog,
    SearchQueue,
    APICallLog,
    PageSearchHistory,
    WinningAdSearchHistory,
    PageRecherche,
    WinningAds,
)


def create_search_log(
    db,
    keywords: str,
    countries: str,
    languages: str = "",
    min_ads: int = 1,
    selected_cms: str = ""
) -> int:
    """Cree un nouveau log de recherche."""
    with db.get_session() as session:
        log = SearchLog(
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
    **stats
) -> bool:
    """Complete un log de recherche."""
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

        for key, value in stats.items():
            if hasattr(log, key):
                setattr(log, key, value)

        return True


def get_search_logs(db, limit: int = 50, status: str = None) -> List[Dict]:
    """Recupere les logs de recherche."""
    with db.get_session() as session:
        query = session.query(SearchLog)
        if status:
            query = query.filter(SearchLog.status == status)

        logs = query.order_by(desc(SearchLog.started_at)).limit(limit).all()

        return [
            {
                "id": l.id,
                "keywords": l.keywords,
                "countries": l.countries,
                "status": l.status,
                "started_at": l.started_at,
                "ended_at": l.ended_at,
                "duration_seconds": l.duration_seconds,
                "total_ads_found": l.total_ads_found,
                "total_pages_found": l.total_pages_found,
                "pages_shopify": l.pages_shopify,
                "winning_ads_count": l.winning_ads_count,
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
    cms_filter: str = "",
    user_session: str = None
) -> int:
    """Cree une recherche en queue."""
    with db.get_session() as session:
        search = SearchQueue(
            keywords=keywords,
            countries=countries,
            languages=languages,
            min_ads=min_ads,
            cms_filter=cms_filter,
            user_session=user_session,
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


def get_queue_stats(db) -> Dict:
    """Statistiques de la queue."""
    with db.get_session() as session:
        pending = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "pending"
        ).scalar() or 0

        running = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "running"
        ).scalar() or 0

        completed = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "completed"
        ).scalar() or 0

        failed = session.query(func.count(SearchQueue.id)).filter(
            SearchQueue.status == "failed"
        ).scalar() or 0

        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total": pending + running + completed + failed,
        }


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

def record_page_search_history(db, page_id: str, search_log_id: int) -> bool:
    """Enregistre l'historique de recherche d'une page."""
    with db.get_session() as session:
        existing = session.query(PageSearchHistory).filter(
            PageSearchHistory.page_id == str(page_id),
            PageSearchHistory.search_log_id == search_log_id
        ).first()

        if not existing:
            history = PageSearchHistory(
                page_id=str(page_id),
                search_log_id=search_log_id,
                found_at=datetime.utcnow(),
            )
            session.add(history)

        return True


def record_pages_search_history_batch(
    db,
    page_ids: List[str],
    search_log_id: int
) -> int:
    """Enregistre l'historique pour plusieurs pages."""
    count = 0
    for page_id in page_ids:
        if record_page_search_history(db, page_id, search_log_id):
            count += 1
    return count


def record_winning_ad_search_history(
    db,
    ad_id: str,
    search_log_id: int
) -> bool:
    """Enregistre l'historique de recherche d'une winning ad."""
    with db.get_session() as session:
        existing = session.query(WinningAdSearchHistory).filter(
            WinningAdSearchHistory.ad_id == str(ad_id),
            WinningAdSearchHistory.search_log_id == search_log_id
        ).first()

        if not existing:
            history = WinningAdSearchHistory(
                ad_id=str(ad_id),
                search_log_id=search_log_id,
                found_at=datetime.utcnow(),
            )
            session.add(history)

        return True


def record_winning_ads_search_history_batch(
    db,
    ad_ids: List[str],
    search_log_id: int
) -> int:
    """Enregistre l'historique pour plusieurs winning ads."""
    count = 0
    for ad_id in ad_ids:
        if record_winning_ad_search_history(db, ad_id, search_log_id):
            count += 1
    return count


def get_search_history_stats(db, days: int = 30) -> Dict:
    """Statistiques de l'historique de recherche."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        total_searches = session.query(func.count(SearchLog.id)).filter(
            SearchLog.started_at >= cutoff
        ).scalar() or 0

        completed = session.query(func.count(SearchLog.id)).filter(
            SearchLog.started_at >= cutoff,
            SearchLog.status == "completed"
        ).scalar() or 0

        total_pages = session.query(func.count(func.distinct(PageSearchHistory.page_id))).filter(
            PageSearchHistory.found_at >= cutoff
        ).scalar() or 0

        total_winning = session.query(func.count(func.distinct(WinningAdSearchHistory.ad_id))).filter(
            WinningAdSearchHistory.found_at >= cutoff
        ).scalar() or 0

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


def get_search_logs_stats(db, days: int = 30) -> Dict:
    """
    Statistiques des logs de recherche.

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours a considerer

    Returns:
        Dict avec les statistiques des recherches
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Total searches
        total_searches = session.query(func.count(SearchLog.id)).filter(
            SearchLog.started_at >= cutoff
        ).scalar() or 0

        # By status
        by_status = {}
        for status in ["completed", "failed", "running", "preview"]:
            count = session.query(func.count(SearchLog.id)).filter(
                SearchLog.started_at >= cutoff,
                SearchLog.status == status
            ).scalar() or 0
            by_status[status] = count

        # Average duration
        avg_duration = session.query(func.avg(SearchLog.duration_seconds)).filter(
            SearchLog.started_at >= cutoff,
            SearchLog.duration_seconds.isnot(None)
        ).scalar() or 0

        # Total pages found
        total_pages = session.query(func.sum(SearchLog.total_pages_found)).filter(
            SearchLog.started_at >= cutoff
        ).scalar() or 0

        # API stats (if columns exist)
        total_meta_api = 0
        total_scraper_api = 0
        total_web_requests = 0
        total_rate_limits = 0

        try:
            total_meta_api = session.query(func.sum(SearchLog.meta_api_calls)).filter(
                SearchLog.started_at >= cutoff
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_scraper_api = session.query(func.sum(SearchLog.scraper_api_calls)).filter(
                SearchLog.started_at >= cutoff
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_web_requests = session.query(func.sum(SearchLog.web_requests)).filter(
                SearchLog.started_at >= cutoff
            ).scalar() or 0
        except Exception:
            pass

        try:
            total_rate_limits = session.query(func.sum(SearchLog.rate_limit_hits)).filter(
                SearchLog.started_at >= cutoff
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


def get_pages_for_search(db, search_log_id: int, limit: int = 100) -> List[Dict]:
    """
    Recupere les pages trouvees lors d'une recherche specifique.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du log de recherche
        limit: Nombre maximum de resultats

    Returns:
        Liste des pages avec leurs informations
    """
    with db.get_session() as session:
        # Joindre PageSearchHistory avec PageRecherche
        results = session.query(PageRecherche).join(
            PageSearchHistory,
            PageRecherche.page_id == PageSearchHistory.page_id
        ).filter(
            PageSearchHistory.search_log_id == search_log_id
        ).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "thematique": p.thematique,
                "subcategory": getattr(p, 'subcategory', None),
                "pays": p.pays,
            }
            for p in results
        ]


def get_winning_ads_for_search(db, search_log_id: int, limit: int = 100) -> List[Dict]:
    """
    Recupere les winning ads trouvees lors d'une recherche specifique.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du log de recherche
        limit: Nombre maximum de resultats

    Returns:
        Liste des winning ads avec leurs informations
    """
    with db.get_session() as session:
        # Joindre WinningAdSearchHistory avec WinningAds
        results = session.query(WinningAds).join(
            WinningAdSearchHistory,
            WinningAds.ad_id == WinningAdSearchHistory.ad_id
        ).filter(
            WinningAdSearchHistory.search_log_id == search_log_id
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "page_id": a.page_id,
                "eu_total_reach": a.eu_total_reach,
                "age_days": a.ad_age_days,
                "matched_criteria": a.matched_criteria,
                "ad_snapshot_url": a.ad_snapshot_url,
                "date_scan": a.date_scan,
            }
            for a in results
        ]
