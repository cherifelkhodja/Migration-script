"""
Module Facade pour la gestion de la base de donnees PostgreSQL.

Ce module constitue le point d'entree principal pour l'acces aux donnees.
Il fournit DatabaseManager et re-exporte tous les modeles et fonctions
des modules specialises pour maintenir la compatibilite ascendante.

Architecture Hexagonale:
------------------------
Ce module fait partie de la couche Infrastructure (Adapters) et implemente
les ports de persistence definis par le domaine.

    src/infrastructure/persistence/
    ├── database.py          <- CE FICHIER (Facade)
    ├── models/              <- Modeles SQLAlchemy (entites ORM)
    │   ├── base.py          Base declarative
    │   ├── page.py          PageRecherche, SuiviPage
    │   ├── ad.py            AdsRecherche, WinningAds
    │   └── ...
    └── repositories/        <- Fonctions d'acces aux donnees
        ├── page_repository.py
        ├── winning_ad_repository.py
        ├── settings_repository.py
        └── ...

Pattern Facade:
---------------
Ce module applique le pattern Facade pour:
1. Simplifier l'acces aux nombreuses fonctions de persistence
2. Masquer la complexite de l'architecture interne
3. Maintenir la compatibilite avec le code existant

Usage recommande:
-----------------
Pour le nouveau code, importez directement depuis les sous-modules:
    from src.infrastructure.persistence.models import PageRecherche
    from src.infrastructure.persistence.repositories import save_winning_ads

Pour le code existant, ce module reste le point d'entree principal:
    from src.infrastructure.persistence.database import (
        DatabaseManager, PageRecherche, save_winning_ads
    )

Connection Pooling:
-------------------
DatabaseManager utilise un pool de connexions SQLAlchemy optimise:
- pool_size=5: Connexions maintenues en permanence
- max_overflow=10: Connexions temporaires supplementaires
- pool_recycle=1800: Recyclage toutes les 30 min (evite timeout)
- pool_pre_ping=True: Verification avant utilisation
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, text, func, desc, and_, or_
from sqlalchemy.orm import sessionmaker, Session

# Models (re-exports pour compatibilite)
from src.infrastructure.persistence.models import (
    Base, PageRecherche, SuiviPage, SuiviPageArchive, AdsRecherche,
    WinningAds, AdsRechercheArchive, WinningAdsArchive, Tag, PageTag,
    PageNote, Favorite, Collection, CollectionPage, Blacklist, SavedFilter,
    ScheduledScan, SearchLog, PageSearchHistory, WinningAdSearchHistory,
    SearchQueue, APICallLog, UserSettings, ClassificationTaxonomy,
    MetaToken, TokenUsageLog, AppSettings, APICache,
)

# Repository functions (re-exports pour compatibilite)
from src.infrastructure.persistence.repositories import (
    get_database_stats, health_check, vacuum_database,
    get_etat_from_ads_count, to_str_list,
    SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT,
    get_app_setting, set_app_setting, get_all_app_settings,
    get_setting, set_setting, get_all_settings,
    add_to_blacklist, remove_from_blacklist, get_blacklist, is_in_blacklist,
    get_blacklist_ids, bulk_add_to_blacklist,
    get_all_tags, create_tag, delete_tag, add_tag_to_page, remove_tag_from_page,
    get_page_tags, get_pages_by_tag, bulk_add_tag,
    get_page_notes, add_page_note, update_page_note, delete_page_note,
    get_favorites, is_favorite, add_favorite, remove_favorite,
    toggle_favorite, bulk_add_to_favorites,
    get_collections, create_collection, update_collection, delete_collection,
    add_page_to_collection, remove_page_from_collection,
    get_collection_pages, get_page_collections, bulk_add_to_collection,
    get_saved_filters, save_filter, delete_saved_filter,
    get_scheduled_scans, create_scheduled_scan, update_scheduled_scan,
    delete_scheduled_scan, mark_scan_executed,
    generate_cache_key, get_cached_response, set_cached_response,
    get_cache_stats, clear_expired_cache, clear_all_cache,
    get_all_taxonomy, get_taxonomy_by_category, get_taxonomy_categories,
    add_taxonomy_entry, update_taxonomy_entry, delete_taxonomy_entry,
    init_default_taxonomy, build_taxonomy_prompt, get_unclassified_pages,
    get_pages_for_classification, update_page_classification,
    update_pages_classification_batch, get_classification_stats,
    add_meta_token, get_all_meta_tokens, get_active_meta_tokens,
    get_active_meta_tokens_with_proxies, update_meta_token, delete_meta_token,
    record_token_usage, clear_rate_limit, reset_token_stats, log_token_usage,
    get_token_usage_logs, get_token_stats_detailed, verify_meta_token, verify_all_tokens,
    save_pages_recherche, save_suivi_page, save_ads_recherche,
    get_all_pages, get_page_history, get_page_evolution_history, get_evolution_stats, get_all_countries, get_all_subcategories,
    add_country_to_page, get_pages_count,
    is_winning_ad, save_winning_ads, cleanup_duplicate_winning_ads,
    get_winning_ads, get_winning_ads_filtered, get_winning_ads_stats, get_winning_ads_by_page,
    create_search_log, update_search_log, complete_search_log, get_search_logs,
    delete_search_log, save_api_calls, create_search_queue, get_search_queue,
    update_search_queue_status, update_search_queue_progress, cancel_search_queue,
    get_pending_searches, get_queue_stats, recover_interrupted_searches,
    record_page_search_history, record_pages_search_history_batch,
    record_winning_ad_search_history, record_winning_ads_search_history_batch,
    get_search_history_stats,
)


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA CONNEXION
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """
    Gestionnaire central de connexion a la base de donnees PostgreSQL.

    Cette classe encapsule la configuration SQLAlchemy et fournit un
    context manager pour les sessions avec gestion automatique des
    transactions (commit/rollback).

    Attributes:
        engine: Moteur SQLAlchemy avec pool de connexions
        SessionLocal: Factory de sessions configuree

    Configuration du pool:
        - pool_size=5: 5 connexions permanentes
        - max_overflow=10: Jusqu'a 15 connexions totales
        - pool_timeout=30: Timeout de 30s pour obtenir une connexion
        - pool_recycle=1800: Recyclage toutes les 30 minutes
        - pool_pre_ping=True: Test de connexion avant utilisation

    Example:
        >>> db = DatabaseManager()
        >>> with db.get_session() as session:
        ...     pages = session.query(PageRecherche).all()
        # Commit automatique si pas d'exception
        # Rollback automatique en cas d'erreur
    """

    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/meta_ads"
            )

        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self):
        """Cree toutes les tables si elles n'existent pas."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Context manager pour les sessions avec gestion automatique des transactions."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pool_status(self) -> Dict:
        """Retourne les statistiques du pool de connexions."""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalidatedcount() if hasattr(pool, 'invalidatedcount') else 0
        }


def ensure_tables_exist(db: DatabaseManager) -> bool:
    """
    S'assure que toutes les tables existent dans la base de donnees.
    Cree les tables manquantes si necessaire.
    """
    try:
        Base.metadata.create_all(db.engine)

        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if "page_search_history" not in existing_tables:
            PageSearchHistory.__table__.create(db.engine, checkfirst=True)

        if "winning_ad_search_history" not in existing_tables:
            WinningAdSearchHistory.__table__.create(db.engine, checkfirst=True)

        _run_migrations(db)
        return True
    except Exception as e:
        print(f"Erreur creation tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_migrations(db: DatabaseManager):
    """Execute les migrations pour ajouter les colonnes manquantes."""
    migrations = [
        ("search_logs", "meta_api_calls", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_calls INTEGER DEFAULT 0"),
        ("search_logs", "scraper_api_calls", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_calls INTEGER DEFAULT 0"),
        ("search_logs", "web_requests", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_requests INTEGER DEFAULT 0"),
        ("search_logs", "meta_api_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_errors INTEGER DEFAULT 0"),
        ("search_logs", "scraper_api_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_errors INTEGER DEFAULT 0"),
        ("search_logs", "web_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_errors INTEGER DEFAULT 0"),
        ("search_logs", "rate_limit_hits", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS rate_limit_hits INTEGER DEFAULT 0"),
        ("search_logs", "meta_api_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "scraper_api_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "web_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "scraper_api_cost", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_cost FLOAT DEFAULT 0"),
        ("search_logs", "api_details", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS api_details TEXT"),
        ("search_logs", "errors_list", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS errors_list TEXT"),
        ("search_logs", "scraper_errors_by_type", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_errors_by_type TEXT"),
        ("search_logs", "new_pages_count", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS new_pages_count INTEGER DEFAULT 0"),
        ("search_logs", "existing_pages_updated", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS existing_pages_updated INTEGER DEFAULT 0"),
        ("search_logs", "new_winning_ads_count", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS new_winning_ads_count INTEGER DEFAULT 0"),
        ("search_logs", "existing_winning_ads_updated", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS existing_winning_ads_updated INTEGER DEFAULT 0"),
        ("liste_page_recherche", "last_search_log_id", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS last_search_log_id INTEGER"),
        ("liste_page_recherche", "was_created_in_last_search", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS was_created_in_last_search BOOLEAN DEFAULT TRUE"),
        ("winning_ads", "search_log_id", "ALTER TABLE winning_ads ADD COLUMN IF NOT EXISTS search_log_id INTEGER"),
        ("winning_ads", "is_new", "ALTER TABLE winning_ads ADD COLUMN IF NOT EXISTS is_new BOOLEAN DEFAULT TRUE"),
        ("liste_page_recherche", "subcategory", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100)"),
        ("liste_page_recherche", "classification_confidence", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS classification_confidence FLOAT"),
        ("liste_page_recherche", "classified_at", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS classified_at TIMESTAMP"),
        ("liste_page_recherche", "pays_resize", "ALTER TABLE liste_page_recherche ALTER COLUMN pays TYPE VARCHAR(255)"),
        ("liste_page_recherche", "site_title", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_title VARCHAR(255)"),
        ("liste_page_recherche", "site_description", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_description TEXT"),
        ("liste_page_recherche", "site_h1", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_h1 VARCHAR(200)"),
        ("liste_page_recherche", "site_keywords", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_keywords VARCHAR(300)"),
        ("meta_tokens", "proxy_url", "ALTER TABLE meta_tokens ADD COLUMN IF NOT EXISTS proxy_url VARCHAR(255)"),
        ("search_queue", "updated_at", "ALTER TABLE search_queue ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"),
        # Multi-tenancy owner_id columns
        ("tags", "owner_id", "ALTER TABLE tags ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("collections", "owner_id", "ALTER TABLE collections ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("favorites", "owner_id", "ALTER TABLE favorites ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("blacklist", "owner_id", "ALTER TABLE blacklist ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("saved_filters", "owner_id", "ALTER TABLE saved_filters ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("scheduled_scans", "owner_id", "ALTER TABLE scheduled_scans ADD COLUMN IF NOT EXISTS owner_id UUID"),
        ("scheduled_scans", "languages", "ALTER TABLE scheduled_scans ADD COLUMN IF NOT EXISTS languages VARCHAR(100) DEFAULT 'fr'"),
    ]

    index_migrations = [
        "CREATE INDEX IF NOT EXISTS idx_page_cms_etat ON liste_page_recherche (cms, etat)",
        "CREATE INDEX IF NOT EXISTS idx_page_etat_ads ON liste_page_recherche (etat, nombre_ads_active)",
        "CREATE INDEX IF NOT EXISTS idx_page_created ON liste_page_recherche (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_page_thematique ON liste_page_recherche (thematique)",
        "CREATE INDEX IF NOT EXISTS idx_winning_ads_page_date ON winning_ads (page_id, date_scan)",
        "CREATE INDEX IF NOT EXISTS idx_winning_ads_reach ON winning_ads (eu_total_reach)",
        "CREATE INDEX IF NOT EXISTS idx_search_log_status_date ON search_logs (status, started_at)",
        "CREATE INDEX IF NOT EXISTS idx_page_last_search ON liste_page_recherche (last_search_log_id)",
        "CREATE INDEX IF NOT EXISTS idx_winning_search ON winning_ads (search_log_id)",
    ]

    cleanup_duplicates_sql = """
    DELETE FROM winning_ads
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM winning_ads
        GROUP BY ad_id
    )
    """

    unique_constraint_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_winning_ads_ad_id'
        ) THEN
            ALTER TABLE winning_ads ADD CONSTRAINT uq_winning_ads_ad_id UNIQUE (ad_id);
        END IF;
    END $$;
    """

    with db.get_session() as session:
        for table, column, sql in migrations:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception:
                session.rollback()

        for sql in index_migrations:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception:
                session.rollback()

        try:
            result = session.execute(text(cleanup_duplicates_sql))
            deleted = result.rowcount
            session.commit()
            if deleted > 0:
                print(f"[Migration] Supprime {deleted} doublons de winning_ads")
        except Exception:
            session.rollback()

        try:
            session.execute(text(unique_constraint_sql))
            session.commit()
        except Exception:
            session.rollback()


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS SPECIFIQUES NON MIGREES
# ═══════════════════════════════════════════════════════════════════════════════

def get_suivi_stats(db: DatabaseManager) -> Dict:
    """Statistiques globales du suivi des pages."""
    with db.get_session() as session:
        total = session.query(func.count(SuiviPage.id)).scalar() or 0
        unique_pages = session.query(func.count(func.distinct(SuiviPage.page_id))).scalar() or 0

        today = datetime.utcnow().date()
        scans_today = session.query(func.count(SuiviPage.id)).filter(
            func.date(SuiviPage.date_scan) == today
        ).scalar() or 0

        return {
            "total_records": total,
            "unique_pages": unique_pages,
            "scans_today": scans_today,
        }


def search_pages(
    db: DatabaseManager,
    search_term: str = None,
    cms_filter: List[str] = None,
    etat_filter: List[str] = None,
    country_filter: List[str] = None,
    category_filter: str = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """Recherche de pages avec filtres."""
    with db.get_session() as session:
        query = session.query(PageRecherche)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    PageRecherche.page_name.ilike(search_pattern),
                    PageRecherche.page_id.ilike(search_pattern),
                    PageRecherche.keywords.ilike(search_pattern),
                    PageRecherche.lien_site.ilike(search_pattern),
                )
            )

        if cms_filter:
            query = query.filter(PageRecherche.cms.in_(cms_filter))

        if etat_filter:
            query = query.filter(PageRecherche.etat.in_(etat_filter))

        if country_filter:
            conditions = [PageRecherche.pays.ilike(f"%{c}%") for c in country_filter]
            query = query.filter(or_(*conditions))

        if category_filter:
            query = query.filter(PageRecherche.thematique == category_filter)

        pages = query.order_by(desc(PageRecherche.nombre_ads_active)).offset(offset).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "thematique": p.thematique,
                "pays": p.pays,
                "dernier_scan": p.dernier_scan,
            }
            for p in pages
        ]


def get_winning_ads_stats_filtered(
    db: DatabaseManager,
    days: int = 30,
    cms_filter: List[str] = None,
    category_filter: str = None,
) -> Dict:
    """Statistiques des winning ads avec filtres."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(WinningAds).filter(WinningAds.date_scan >= cutoff)

        if cms_filter or category_filter:
            query = query.join(PageRecherche, WinningAds.page_id == PageRecherche.page_id)
            if cms_filter:
                query = query.filter(PageRecherche.cms.in_(cms_filter))
            if category_filter:
                query = query.filter(PageRecherche.thematique == category_filter)

        total = query.count()
        total_reach = session.query(func.sum(WinningAds.eu_total_reach)).filter(
            WinningAds.id.in_([w.id for w in query])
        ).scalar() or 0

        return {
            "total": total,
            "total_reach": int(total_reach),
            "avg_reach": int(total_reach / total) if total > 0 else 0,
        }


def get_suivi_stats_filtered(
    db: DatabaseManager,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None,
) -> Dict:
    """Statistiques du suivi avec filtres."""
    with db.get_session() as session:
        # Base query sur PageRecherche pour avoir les filtres
        query = session.query(PageRecherche)

        if thematique:
            query = query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            query = query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))

        pages = query.all()
        total_pages = len(pages)

        # Compter par etat
        etats = {}
        cms_stats = {}
        for p in pages:
            etat = p.etat or "inactif"
            etats[etat] = etats.get(etat, 0) + 1

            cms = p.cms or "Inconnu"
            cms_stats[cms] = cms_stats.get(cms, 0) + 1

        return {
            "total_pages": total_pages,
            "etats": etats,
            "cms": cms_stats,
        }


def get_cached_pages_info(
    db: DatabaseManager,
    page_ids: List[str],
    cache_days: int = 1,
) -> Dict[str, Dict]:
    """
    Recupere les infos cachees des pages (scan recent).

    Returns:
        Dict[page_id] = {"lien_site": X, "cms": X, "needs_rescan": bool}
    """
    if not page_ids:
        return {}

    cutoff = datetime.utcnow() - timedelta(days=cache_days)

    with db.get_session() as session:
        pages = session.query(PageRecherche).filter(
            PageRecherche.page_id.in_([str(pid) for pid in page_ids])
        ).all()

        result = {}
        for p in pages:
            needs_rescan = True
            if p.dernier_scan and p.dernier_scan >= cutoff:
                needs_rescan = False

            result[str(p.page_id)] = {
                "lien_site": p.lien_site,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "thematique": p.thematique,
                "needs_rescan": needs_rescan,
            }

        return result


def get_dashboard_trends(db: DatabaseManager, days: int = 7) -> Dict:
    """
    Calcule les tendances pour le dashboard.

    Compare la periode actuelle avec la periode precedente.
    """
    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    with db.get_session() as session:
        # Pages: compter les nouvelles pages
        current_pages = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.date_ajout >= current_start
        ).scalar() or 0

        previous_pages = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.date_ajout >= previous_start,
            PageRecherche.date_ajout < current_start
        ).scalar() or 0

        pages_delta = current_pages - previous_pages

        # Winning ads
        current_winning = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan >= current_start
        ).scalar() or 0

        previous_winning = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan >= previous_start,
            WinningAds.date_scan < current_start
        ).scalar() or 0

        winning_delta = current_winning - previous_winning

        # Evolution: pages en hausse/baisse (via get_evolution_stats)
        try:
            from src.infrastructure.persistence.repositories import get_evolution_stats
            evolution = get_evolution_stats(db, period_days=days)
            rising = sum(1 for e in evolution if e.get("pct_ads", 0) >= 20)
            falling = sum(1 for e in evolution if e.get("pct_ads", 0) <= -20)
        except Exception:
            rising = 0
            falling = 0

        return {
            "pages": {
                "current": current_pages,
                "previous": previous_pages,
                "delta": pages_delta,
            },
            "winning_ads": {
                "current": current_winning,
                "previous": previous_winning,
                "delta": winning_delta,
            },
            "evolution": {
                "rising": rising,
                "falling": falling,
            },
        }


def update_search_log_phases(db: DatabaseManager, log_id: int, phases_completed: List) -> bool:
    """Met a jour les phases completees d'un log de recherche."""
    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False

        # Stocker les phases en JSON si le champ existe
        try:
            import json
            log.phases_data = json.dumps(phases_completed)
        except Exception:
            pass

        return True


def get_search_log_detail(db: DatabaseManager, log_id: int) -> Optional[Dict]:
    """Detail complet d'un log de recherche."""
    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return None

        return {
            "id": log.id,
            "keywords": log.keywords,
            "countries": log.countries,
            "status": log.status,
            "started_at": log.started_at,
            "finished_at": log.finished_at,
            "pages_found": log.pages_found,
            "ads_found": log.ads_found,
            "winning_ads_found": log.winning_ads_found,
            "error_message": log.error_message,
        }


def cleanup_old_data(
    db: DatabaseManager,
    days: int = 90,
    archive: bool = False,
) -> Dict:
    """Nettoie les anciennes donnees."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = {"suivi_page": 0, "ads_recherche": 0}

    with db.get_session() as session:
        if archive:
            old_suivi = session.query(SuiviPage).filter(SuiviPage.date_scan < cutoff).all()
            for s in old_suivi:
                archive_entry = SuiviPageArchive(
                    page_id=s.page_id,
                    page_name=s.page_name,
                    ads_active=s.ads_active,
                    cms=s.cms,
                    thematique=s.thematique,
                    date_scan=s.date_scan,
                    pays=s.pays,
                )
                session.add(archive_entry)

        deleted["suivi_page"] = session.query(SuiviPage).filter(
            SuiviPage.date_scan < cutoff
        ).delete()

        deleted["ads_recherche"] = session.query(AdsRecherche).filter(
            AdsRecherche.date_scan < cutoff
        ).delete()

    return deleted


# Note: Ce module re-exporte les modeles et fonctions depuis les modules specialises
# pour compatibilite ascendante. Les nouveaux imports doivent utiliser:
# - src.infrastructure.persistence.models pour les modeles
# - src.infrastructure.persistence.repositories pour les fonctions
