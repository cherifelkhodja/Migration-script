"""
Module de gestion de la base de données PostgreSQL
"""
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert

Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLES
# ═══════════════════════════════════════════════════════════════════════════════

class PageRecherche(Base):
    """Table liste_page_recherche - Toutes les pages analysées"""
    __tablename__ = "liste_page_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    page_name = Column(String(255))
    lien_site = Column(String(500))
    lien_fb_ad_library = Column(String(500))
    thematique = Column(String(100))
    type_produits = Column(Text)
    moyens_paiements = Column(Text)
    pays = Column(String(50))
    langue = Column(String(50))
    cms = Column(String(50))
    template = Column(String(100))
    devise = Column(String(10))
    etat = Column(String(20))  # inactif, XS, S, M, L, XL, XXL
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    dernier_scan = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_etat', 'etat'),
        Index('idx_page_cms', 'cms'),
        Index('idx_page_dernier_scan', 'dernier_scan'),
    )


class SuiviPage(Base):
    """Table suivi_page - Historique des pages avec >= 10 ads actives"""
    __tablename__ = "suivi_page"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cle_suivi = Column(String(100))
    page_id = Column(String(50), nullable=False, index=True)
    nom_site = Column(String(255))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_suivi_page_date', 'page_id', 'date_scan'),
    )


class AdsRecherche(Base):
    """Table liste_ads_recherche - Annonces des pages avec >= 20 ads"""
    __tablename__ = "liste_ads_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    eu_total_reach = Column(String(100))
    languages = Column(String(100))
    country = Column(String(50))
    publisher_platforms = Column(String(200))
    target_ages = Column(String(100))
    target_gender = Column(String(50))
    beneficiary_payers = Column(Text)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_ads_page', 'page_id'),
        Index('idx_ads_date', 'date_scan'),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA CONNEXION
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """Gestionnaire de connexion à la base de données"""

    def __init__(self, database_url: str = None):
        """
        Initialise la connexion à la base de données

        Args:
            database_url: URL de connexion PostgreSQL
        """
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/meta_ads"
            )

        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Crée toutes les tables si elles n'existent pas"""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Context manager pour les sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def get_etat_from_ads_count(ads_count: int) -> str:
    """
    Détermine l'état basé sur le nombre d'ads actives

    Args:
        ads_count: Nombre d'ads actives

    Returns:
        État: inactif, XS, S, M, L, XL, XXL
    """
    if ads_count == 0:
        return "inactif"
    elif ads_count < 10:
        return "XS"
    elif ads_count < 20:
        return "S"
    elif ads_count < 35:
        return "M"
    elif ads_count < 80:
        return "L"
    elif ads_count < 150:
        return "XL"
    else:
        return "XXL"


def to_str_list(val: Any) -> str:
    """Convertit une valeur en chaîne (pour les listes)"""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""


# ═══════════════════════════════════════════════════════════════════════════════
# OPÉRATIONS CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def save_pages_recherche(
    db: DatabaseManager,
    pages_final: Dict,
    web_results: Dict,
    countries: List[str],
    languages: List[str]
) -> int:
    """
    Sauvegarde ou met à jour les pages dans liste_page_recherche

    Args:
        db: Instance DatabaseManager
        pages_final: Dictionnaire des pages
        web_results: Résultats d'analyse web
        countries: Liste des pays
        languages: Liste des langues

    Returns:
        Nombre de pages sauvegardées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_final.items():
            web = web_results.get(pid, {})
            ads_count = data.get("ads_active_total", 0)

            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

            page_data = {
                "page_id": str(pid),
                "page_name": data.get("page_name", ""),
                "lien_site": data.get("website", ""),
                "lien_fb_ad_library": fb_link,
                "thematique": web.get("thematique", ""),
                "type_produits": web.get("type_produits", ""),
                "moyens_paiements": web.get("payments", ""),
                "pays": ",".join(countries),
                "langue": ",".join(languages),
                "cms": data.get("cms") or web.get("cms", "Unknown"),
                "template": web.get("theme", ""),
                "devise": data.get("currency", ""),
                "etat": get_etat_from_ads_count(ads_count),
                "nombre_ads_active": ads_count,
                "nombre_produits": web.get("product_count", 0),
                "dernier_scan": scan_time,
                "updated_at": scan_time,
            }

            # Upsert (insert or update)
            stmt = insert(PageRecherche).values(**page_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['page_id'],
                set_={k: v for k, v in page_data.items() if k != 'page_id'}
            )
            session.execute(stmt)
            count += 1

    return count


def save_suivi_page(
    db: DatabaseManager,
    pages_final: Dict,
    web_results: Dict,
    min_ads: int = 10
) -> int:
    """
    Sauvegarde l'historique des pages dans suivi_page

    Args:
        db: Instance DatabaseManager
        pages_final: Dictionnaire des pages
        web_results: Résultats d'analyse web
        min_ads: Nombre minimum d'ads pour être inclus

    Returns:
        Nombre d'entrées créées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_final.items():
            ads_count = data.get("ads_active_total", 0)

            if ads_count < min_ads:
                continue

            web = web_results.get(pid, {})

            suivi = SuiviPage(
                cle_suivi="",
                page_id=str(pid),
                nom_site=data.get("page_name", ""),
                nombre_ads_active=ads_count,
                nombre_produits=web.get("product_count", 0),
                date_scan=scan_time
            )
            session.add(suivi)
            count += 1

    return count


def save_ads_recherche(
    db: DatabaseManager,
    pages_for_ads: Dict,
    page_ads: Dict,
    countries: List[str],
    min_ads: int = 20
) -> int:
    """
    Sauvegarde les annonces dans liste_ads_recherche

    Args:
        db: Instance DatabaseManager
        pages_for_ads: Pages avec assez d'ads
        page_ads: Dictionnaire des annonces par page
        countries: Liste des pays
        min_ads: Nombre minimum d'ads pour être inclus

    Returns:
        Nombre d'annonces sauvegardées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_for_ads.items():
            if data.get("ads_active_total", 0) < min_ads:
                continue

            for ad in page_ads.get(pid, []):
                ad_creation = None
                if ad.get("ad_creation_time"):
                    try:
                        ad_creation = datetime.fromisoformat(
                            ad["ad_creation_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                ads_entry = AdsRecherche(
                    ad_id=str(ad.get("id", "")),
                    page_id=str(pid),
                    page_name=ad.get("page_name", ""),
                    ad_creation_time=ad_creation,
                    ad_creative_bodies=to_str_list(ad.get("ad_creative_bodies")),
                    ad_creative_link_captions=to_str_list(ad.get("ad_creative_link_captions")),
                    ad_creative_link_titles=to_str_list(ad.get("ad_creative_link_titles")),
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    eu_total_reach=str(ad.get("eu_total_reach", "")),
                    languages=to_str_list(ad.get("languages")),
                    country=",".join(countries),
                    publisher_platforms=to_str_list(ad.get("publisher_platforms")),
                    target_ages=str(ad.get("target_ages", "")),
                    target_gender=str(ad.get("target_gender", "")),
                    beneficiary_payers=to_str_list(ad.get("beneficiary_payers")),
                    date_scan=scan_time
                )
                session.add(ads_entry)
                count += 1

    return count


# ═══════════════════════════════════════════════════════════════════════════════
# REQUÊTES DE LECTURE
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_pages(db: DatabaseManager, limit: int = 1000) -> List[Dict]:
    """Récupère toutes les pages"""
    with db.get_session() as session:
        pages = session.query(PageRecherche).order_by(
            PageRecherche.nombre_ads_active.desc()
        ).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "dernier_scan": p.dernier_scan.isoformat() if p.dernier_scan else ""
            }
            for p in pages
        ]


def get_page_history(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère l'historique d'une page"""
    with db.get_session() as session:
        entries = session.query(SuiviPage).filter(
            SuiviPage.page_id == page_id
        ).order_by(SuiviPage.date_scan.desc()).all()

        return [
            {
                "page_id": e.page_id,
                "nom_site": e.nom_site,
                "nombre_ads_active": e.nombre_ads_active,
                "nombre_produits": e.nombre_produits,
                "date_scan": e.date_scan.isoformat() if e.date_scan else ""
            }
            for e in entries
        ]


def get_suivi_stats(db: DatabaseManager) -> Dict:
    """Récupère les statistiques de suivi"""
    with db.get_session() as session:
        # Nombre total de pages suivies
        total_pages = session.query(PageRecherche).count()

        # Répartition par état
        from sqlalchemy import func
        etats = session.query(
            PageRecherche.etat,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.etat).all()

        # Répartition par CMS
        cms_stats = session.query(
            PageRecherche.cms,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.cms).all()

        return {
            "total_pages": total_pages,
            "etats": {e[0]: e[1] for e in etats},
            "cms": {c[0]: c[1] for c in cms_stats}
        }


def get_suivi_history(
    db: DatabaseManager,
    page_id: str = None,
    limit: int = 100
) -> List[Dict]:
    """Récupère l'historique de suivi"""
    with db.get_session() as session:
        query = session.query(SuiviPage).order_by(SuiviPage.date_scan.desc())

        if page_id:
            query = query.filter(SuiviPage.page_id == page_id)

        entries = query.limit(limit).all()

        return [
            {
                "page_id": e.page_id,
                "nom_site": e.nom_site,
                "nombre_ads_active": e.nombre_ads_active,
                "nombre_produits": e.nombre_produits,
                "date_scan": e.date_scan
            }
            for e in entries
        ]


def search_pages(
    db: DatabaseManager,
    cms: str = None,
    etat: str = None,
    search_term: str = None,
    limit: int = 100
) -> List[Dict]:
    """Recherche des pages avec filtres"""
    with db.get_session() as session:
        query = session.query(PageRecherche)

        if cms:
            query = query.filter(PageRecherche.cms == cms)
        if etat:
            query = query.filter(PageRecherche.etat == etat)
        if search_term:
            query = query.filter(
                PageRecherche.page_name.ilike(f"%{search_term}%") |
                PageRecherche.lien_site.ilike(f"%{search_term}%")
            )

        pages = query.order_by(
            PageRecherche.nombre_ads_active.desc()
        ).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "lien_fb_ad_library": p.lien_fb_ad_library,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "template": p.template,
                "devise": p.devise,
                "dernier_scan": p.dernier_scan
            }
            for p in pages
        ]
