"""
Gestionnaire de base de donnees PostgreSQL.

Contient la classe DatabaseManager et les fonctions de gestion
(migrations, health check, maintenance).
"""
import os
from datetime import datetime
from typing import Dict
from contextlib import contextmanager

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker, Session

from src.infrastructure.persistence.models import (
    Base,
    PageRecherche,
    SuiviPage,
    AdsRecherche,
    WinningAds,
    Blacklist,
    Tag,
    Favorite,
    Collection,
    SearchLog,
    PageSearchHistory,
    WinningAdSearchHistory,
    APICallLog,
)


class DatabaseManager:
    """Gestionnaire de connexion a la base de donnees avec connection pooling optimise"""

    def __init__(self, database_url: str = None):
        """
        Initialise la connexion a la base de donnees avec pool de connexions.

        Args:
            database_url: URL de connexion PostgreSQL
        """
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
        """Cree toutes les tables si elles n'existent pas"""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Context manager pour les sessions avec gestion automatique des transactions"""
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
        """Retourne les statistiques du pool de connexions"""
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

    Args:
        db: Instance DatabaseManager

    Returns:
        True si succes
    """
    try:
        Base.metadata.create_all(db.engine)

        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if "page_search_history" not in existing_tables:
            print("[ensure_tables_exist] Creation de la table page_search_history...")
            PageSearchHistory.__table__.create(db.engine, checkfirst=True)

        if "winning_ad_search_history" not in existing_tables:
            print("[ensure_tables_exist] Creation de la table winning_ad_search_history...")
            WinningAdSearchHistory.__table__.create(db.engine, checkfirst=True)

        _run_migrations(db)

        return True
    except Exception as e:
        print(f"Erreur creation tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_migrations(db: DatabaseManager):
    """Execute les migrations pour ajouter les colonnes manquantes"""
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


def get_database_stats(db: DatabaseManager) -> Dict:
    """Retourne des statistiques sur la base de donnees."""
    stats = {}

    with db.get_session() as session:
        stats["tables"] = {
            "pages": session.query(PageRecherche).count(),
            "suivi": session.query(SuiviPage).count(),
            "ads": session.query(AdsRecherche).count(),
            "winning_ads": session.query(WinningAds).count(),
            "blacklist": session.query(Blacklist).count(),
            "search_logs": session.query(SearchLog).count(),
            "api_logs": session.query(APICallLog).count(),
            "favorites": session.query(Favorite).count(),
            "collections": session.query(Collection).count(),
            "tags": session.query(Tag).count(),
        }

        oldest_page = session.query(func.min(PageRecherche.created_at)).scalar()
        newest_page = session.query(func.max(PageRecherche.created_at)).scalar()
        oldest_winning = session.query(func.min(WinningAds.date_scan)).scalar()
        newest_winning = session.query(func.max(WinningAds.date_scan)).scalar()

        stats["dates"] = {
            "oldest_page": oldest_page.isoformat() if oldest_page else None,
            "newest_page": newest_page.isoformat() if newest_page else None,
            "oldest_winning_ad": oldest_winning.isoformat() if oldest_winning else None,
            "newest_winning_ad": newest_winning.isoformat() if newest_winning else None,
        }

        stats["pool"] = db.get_pool_status()

    return stats


def health_check(db: DatabaseManager) -> Dict:
    """Verifie la sante de la base de donnees."""
    result = {
        "status": "healthy",
        "database": "unknown",
        "pool": None,
        "tables_exist": False,
        "errors": []
    }

    try:
        with db.get_session() as session:
            session.execute(text("SELECT 1"))
        result["database"] = "connected"

        with db.get_session() as session:
            session.query(PageRecherche).limit(1).all()
            session.query(WinningAds).limit(1).all()
            session.query(SearchLog).limit(1).all()
        result["tables_exist"] = True

        result["pool"] = db.get_pool_status()

        with db.get_session() as session:
            total_rows = (
                session.query(PageRecherche).count() +
                session.query(WinningAds).count() +
                session.query(SearchLog).count() +
                session.query(APICallLog).count()
            )
            if total_rows > 1000000:
                result["warnings"] = ["Database has over 1M rows, consider cleanup"]

    except Exception as e:
        result["status"] = "unhealthy"
        result["errors"].append(str(e))

    return result


def vacuum_database(db: DatabaseManager) -> bool:
    """Execute un VACUUM ANALYZE sur la base de donnees."""
    try:
        with db.engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("VACUUM ANALYZE"))
        return True
    except Exception as e:
        print(f"Erreur VACUUM: {e}")
        return False
