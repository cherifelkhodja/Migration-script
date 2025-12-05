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
    keywords = Column(Text)  # Keywords utilisés pour trouver cette page (séparés par |)
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


class Blacklist(Base):
    """Table blacklist - Pages à exclure des recherches"""
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    page_name = Column(String(255))
    raison = Column(String(255))  # Raison de la mise en blacklist
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_blacklist_page_name', 'page_name'),
    )


class WinningAds(Base):
    """Table winning_ads - Annonces performantes détectées"""
    __tablename__ = "winning_ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_age_days = Column(Integer)  # Âge de l'ad au moment du scan
    eu_total_reach = Column(Integer)  # Reach au moment du scan
    matched_criteria = Column(String(100))  # Critère validé (ex: "≤4d & >15k")
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    lien_site = Column(String(500))
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_winning_ads_page', 'page_id'),
        Index('idx_winning_ads_date', 'date_scan'),
        Index('idx_winning_ads_ad', 'ad_id', 'date_scan'),
    )


class Tag(Base):
    """Table tags - Tags personnalisés pour organiser les pages"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(20), default="#3B82F6")  # Couleur hex
    created_at = Column(DateTime, default=datetime.utcnow)


class PageTag(Base):
    """Table page_tags - Association pages <-> tags"""
    __tablename__ = "page_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_tag_unique', 'page_id', 'tag_id', unique=True),
    )


class PageNote(Base):
    """Table page_notes - Notes sur les pages"""
    __tablename__ = "page_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(Base):
    """Table favorites - Pages favorites"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class Collection(Base):
    """Table collections - Dossiers/Collections de pages"""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(20), default="#6366F1")
    icon = Column(String(10), default="📁")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollectionPage(Base):
    """Table collection_pages - Association collections <-> pages"""
    __tablename__ = "collection_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_collection_page_unique', 'collection_id', 'page_id', unique=True),
    )


class SavedFilter(Base):
    """Table saved_filters - Filtres de recherche sauvegardés"""
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    filter_type = Column(String(50), default="pages")  # pages, ads, winning
    filters_json = Column(Text)  # JSON des filtres
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledScan(Base):
    """Table scheduled_scans - Scans programmés"""
    __tablename__ = "scheduled_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    keywords = Column(Text)  # Keywords à rechercher
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    frequency = Column(String(20), default="daily")  # daily, weekly, monthly
    is_active = Column(Integer, default=1)  # 1=actif, 0=inactif
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    """Table user_settings - Paramètres utilisateur"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

def get_etat_from_ads_count(ads_count: int, thresholds: Dict = None) -> str:
    """
    Détermine l'état basé sur le nombre d'ads actives

    Args:
        ads_count: Nombre d'ads actives
        thresholds: Dictionnaire des seuils personnalisés (optionnel)
                   Format: {"XS": 1, "S": 10, "M": 20, "L": 35, "XL": 80, "XXL": 150}

    Returns:
        État: inactif, XS, S, M, L, XL, XXL
    """
    # Seuils par défaut
    if thresholds is None:
        thresholds = {
            "XS": 1,
            "S": 10,
            "M": 20,
            "L": 35,
            "XL": 80,
            "XXL": 150,
        }

    if ads_count == 0:
        return "inactif"
    elif ads_count < thresholds.get("S", 10):
        return "XS"
    elif ads_count < thresholds.get("M", 20):
        return "S"
    elif ads_count < thresholds.get("L", 35):
        return "M"
    elif ads_count < thresholds.get("XL", 80):
        return "L"
    elif ads_count < thresholds.get("XXL", 150):
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
    languages: List[str],
    thresholds: Dict = None
) -> int:
    """
    Sauvegarde ou met à jour les pages dans liste_page_recherche
    Si une page existe déjà, on ajoute les keywords s'ils ne sont pas déjà présents

    Args:
        db: Instance DatabaseManager
        pages_final: Dictionnaire des pages (avec _keywords set pour chaque page)
        web_results: Résultats d'analyse web
        countries: Liste des pays
        languages: Liste des langues
        thresholds: Seuils personnalisés pour les états (optionnel)

    Returns:
        Nombre de pages sauvegardées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_final.items():
            web = web_results.get(pid, {})
            ads_count = data.get("ads_active_total", 0)

            # Keywords de cette recherche (set -> liste)
            new_keywords = data.get("_keywords", set())
            if isinstance(new_keywords, set):
                new_keywords = list(new_keywords)

            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

            # Vérifier si la page existe déjà
            existing_page = session.query(PageRecherche).filter(
                PageRecherche.page_id == str(pid)
            ).first()

            if existing_page:
                # La page existe - mise à jour avec ajout des keywords
                existing_keywords_str = existing_page.keywords or ""
                existing_keywords_list = [k.strip() for k in existing_keywords_str.split("|") if k.strip()]

                # Ajouter les nouveaux keywords s'ils ne sont pas déjà présents
                for kw in new_keywords:
                    if kw and kw not in existing_keywords_list:
                        existing_keywords_list.append(kw)

                merged_keywords = " | ".join(existing_keywords_list)

                # Mise à jour des champs
                existing_page.page_name = data.get("page_name", "") or existing_page.page_name
                existing_page.lien_site = data.get("website", "") or existing_page.lien_site
                existing_page.lien_fb_ad_library = fb_link
                existing_page.keywords = merged_keywords
                existing_page.thematique = web.get("thematique", "") or existing_page.thematique
                existing_page.type_produits = web.get("type_produits", "") or existing_page.type_produits
                existing_page.moyens_paiements = web.get("payments", "") or existing_page.moyens_paiements
                existing_page.pays = ",".join(countries)
                existing_page.langue = ",".join(languages)
                existing_page.cms = data.get("cms") or web.get("cms", "") or existing_page.cms
                existing_page.template = web.get("theme", "") or existing_page.template
                existing_page.devise = data.get("currency", "") or existing_page.devise
                existing_page.etat = get_etat_from_ads_count(ads_count, thresholds)
                existing_page.nombre_ads_active = ads_count
                existing_page.nombre_produits = web.get("product_count", 0) or existing_page.nombre_produits
                existing_page.dernier_scan = scan_time
                existing_page.updated_at = scan_time
            else:
                # Nouvelle page - insertion
                keywords_str = " | ".join(new_keywords) if new_keywords else ""

                new_page = PageRecherche(
                    page_id=str(pid),
                    page_name=data.get("page_name", ""),
                    lien_site=data.get("website", ""),
                    lien_fb_ad_library=fb_link,
                    keywords=keywords_str,
                    thematique=web.get("thematique", ""),
                    type_produits=web.get("type_produits", ""),
                    moyens_paiements=web.get("payments", ""),
                    pays=",".join(countries),
                    langue=",".join(languages),
                    cms=data.get("cms") or web.get("cms", "Unknown"),
                    template=web.get("theme", ""),
                    devise=data.get("currency", ""),
                    etat=get_etat_from_ads_count(ads_count, thresholds),
                    nombre_ads_active=ads_count,
                    nombre_produits=web.get("product_count", 0),
                    dernier_scan=scan_time,
                    created_at=scan_time,
                    updated_at=scan_time,
                )
                session.add(new_page)

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
                "lien_fb_ad_library": p.lien_fb_ad_library,
                "keywords": p.keywords,
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
                "keywords": p.keywords,
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


def get_cached_pages_info(
    db: DatabaseManager,
    page_ids: List[str],
    cache_days: int = 4
) -> Dict[str, Dict]:
    """
    Récupère les infos en cache pour les pages récemment scannées.

    Args:
        db: Instance DatabaseManager
        page_ids: Liste des page_ids à vérifier
        cache_days: Nombre de jours avant expiration du cache

    Returns:
        Dict {page_id: {cms, lien_site, nombre_produits, dernier_scan, needs_rescan}}
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=cache_days)

    with db.get_session() as session:
        pages = session.query(PageRecherche).filter(
            PageRecherche.page_id.in_(page_ids)
        ).all()

        result = {}
        for p in pages:
            # Vérifier si le scan est encore valide
            needs_rescan = True
            if p.dernier_scan and p.dernier_scan > cutoff:
                needs_rescan = False

            result[str(p.page_id)] = {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "cms": p.cms,
                "template": p.template,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "devise": p.devise,
                "dernier_scan": p.dernier_scan,
                "needs_rescan": needs_rescan,
                "needs_cms_detection": not p.cms or p.cms in ("Unknown", "Inconnu", "")
            }

        return result


def get_evolution_stats(
    db: DatabaseManager,
    period_days: int = 7
) -> List[Dict]:
    """
    Récupère les statistiques d'évolution des pages depuis le dernier scan

    Args:
        db: Instance DatabaseManager
        period_days: Nombre de jours pour la période (7, 14, 30)

    Returns:
        Liste des évolutions avec delta ads/produits et durée entre scans
    """
    from datetime import timedelta
    from sqlalchemy import func, desc

    cutoff_date = datetime.utcnow() - timedelta(days=period_days)

    with db.get_session() as session:
        # Récupérer les pages avec au moins 2 entrées dans suivi_page
        subquery = session.query(
            SuiviPage.page_id,
            func.count(SuiviPage.id).label('scan_count')
        ).filter(
            SuiviPage.date_scan >= cutoff_date
        ).group_by(SuiviPage.page_id).having(
            func.count(SuiviPage.id) >= 2
        ).subquery()

        # Pour chaque page, récupérer les 2 derniers scans
        results = []

        page_ids = session.query(subquery.c.page_id).all()

        for (page_id,) in page_ids:
            # Récupérer les 2 derniers scans pour cette page
            scans = session.query(SuiviPage).filter(
                SuiviPage.page_id == page_id
            ).order_by(desc(SuiviPage.date_scan)).limit(2).all()

            if len(scans) >= 2:
                current = scans[0]
                previous = scans[1]

                # Calculer la durée entre les scans
                duration = current.date_scan - previous.date_scan
                duration_hours = duration.total_seconds() / 3600

                # Calculer les deltas
                delta_ads = current.nombre_ads_active - previous.nombre_ads_active
                delta_produits = current.nombre_produits - previous.nombre_produits

                # Calculer le % de changement
                pct_ads = (delta_ads / previous.nombre_ads_active * 100) if previous.nombre_ads_active > 0 else 0
                pct_produits = (delta_produits / previous.nombre_produits * 100) if previous.nombre_produits > 0 else 0

                results.append({
                    "page_id": page_id,
                    "nom_site": current.nom_site,
                    "ads_actuel": current.nombre_ads_active,
                    "ads_precedent": previous.nombre_ads_active,
                    "delta_ads": delta_ads,
                    "pct_ads": round(pct_ads, 1),
                    "produits_actuel": current.nombre_produits,
                    "produits_precedent": previous.nombre_produits,
                    "delta_produits": delta_produits,
                    "pct_produits": round(pct_produits, 1),
                    "date_actuel": current.date_scan,
                    "date_precedent": previous.date_scan,
                    "duree_heures": round(duration_hours, 1),
                    "duree_jours": round(duration_hours / 24, 1)
                })

        # Trier par delta ads décroissant (les plus gros changements en premier)
        results.sort(key=lambda x: abs(x["delta_ads"]), reverse=True)

        return results


def get_page_evolution_history(
    db: DatabaseManager,
    page_id: str,
    limit: int = 50
) -> List[Dict]:
    """
    Récupère l'historique complet d'évolution d'une page

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page
        limit: Nombre max d'entrées

    Returns:
        Liste des scans avec évolution
    """
    from sqlalchemy import desc

    with db.get_session() as session:
        scans = session.query(SuiviPage).filter(
            SuiviPage.page_id == page_id
        ).order_by(desc(SuiviPage.date_scan)).limit(limit).all()

        results = []
        for i, scan in enumerate(scans):
            entry = {
                "date_scan": scan.date_scan,
                "nombre_ads_active": scan.nombre_ads_active,
                "nombre_produits": scan.nombre_produits,
                "delta_ads": 0,
                "delta_produits": 0
            }

            # Calculer le delta par rapport au scan précédent
            if i < len(scans) - 1:
                prev = scans[i + 1]
                entry["delta_ads"] = scan.nombre_ads_active - prev.nombre_ads_active
                entry["delta_produits"] = scan.nombre_produits - prev.nombre_produits

            results.append(entry)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════

def add_to_blacklist(
    db: DatabaseManager,
    page_id: str,
    page_name: str = "",
    raison: str = ""
) -> bool:
    """
    Ajoute une page à la blacklist

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page
        page_name: Nom de la page
        raison: Raison de la mise en blacklist

    Returns:
        True si ajouté, False si déjà présent
    """
    with db.get_session() as session:
        # Vérifier si déjà présent
        existing = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()

        if existing:
            return False

        entry = Blacklist(
            page_id=str(page_id),
            page_name=page_name,
            raison=raison,
            added_at=datetime.utcnow()
        )
        session.add(entry)
        return True


def remove_from_blacklist(db: DatabaseManager, page_id: str) -> bool:
    """
    Retire une page de la blacklist

    Returns:
        True si retiré, False si non trouvé
    """
    with db.get_session() as session:
        entry = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()

        if entry:
            session.delete(entry)
            return True
        return False


def get_blacklist(db: DatabaseManager) -> List[Dict]:
    """Récupère toute la blacklist"""
    with db.get_session() as session:
        entries = session.query(Blacklist).order_by(
            Blacklist.added_at.desc()
        ).all()

        return [
            {
                "page_id": e.page_id,
                "page_name": e.page_name,
                "raison": e.raison,
                "added_at": e.added_at
            }
            for e in entries
        ]


def is_in_blacklist(db: DatabaseManager, page_id: str) -> bool:
    """Vérifie si une page est dans la blacklist"""
    with db.get_session() as session:
        return session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first() is not None


def get_blacklist_ids(db: DatabaseManager) -> set:
    """Récupère tous les page_id de la blacklist"""
    with db.get_session() as session:
        entries = session.query(Blacklist.page_id).all()
        return {e.page_id for e in entries}


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DES WINNING ADS
# ═══════════════════════════════════════════════════════════════════════════════

def is_winning_ad(
    ad: Dict,
    scan_date: datetime,
    criteria: List = None
) -> tuple:
    """
    Vérifie si une annonce est une "winning ad" basé sur reach + âge

    Args:
        ad: Dictionnaire de l'annonce
        scan_date: Date du scan (pour calculer l'âge)
        criteria: Liste de tuples (max_age_days, min_reach) - optionnel

    Returns:
        Tuple (is_winning, age_days, reach, matched_criteria_str)
    """
    # Critères par défaut
    if criteria is None:
        criteria = [
            (4, 15000), (5, 20000), (6, 30000), (7, 40000),
            (8, 50000), (15, 100000), (22, 200000), (29, 400000)
        ]

    # Extraire le reach
    reach_raw = ad.get("eu_total_reach")
    if not reach_raw:
        return (False, None, None, None)

    # Parser le reach (peut être un dict avec lower_bound/upper_bound ou un int)
    if isinstance(reach_raw, dict):
        reach = reach_raw.get("lower_bound", 0)
    elif isinstance(reach_raw, str):
        try:
            reach = int(reach_raw.replace(",", "").replace(" ", ""))
        except (ValueError, AttributeError):
            return (False, None, None, None)
    else:
        try:
            reach = int(reach_raw)
        except (ValueError, TypeError):
            return (False, None, None, None)

    if reach <= 0:
        return (False, None, reach, None)

    # Calculer l'âge de l'ad
    ad_creation = ad.get("ad_creation_time")
    if not ad_creation:
        return (False, None, reach, None)

    # Parser la date de création
    if isinstance(ad_creation, str):
        try:
            ad_creation = datetime.fromisoformat(ad_creation.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return (False, None, reach, None)

    # Calculer l'âge en jours
    if ad_creation.tzinfo is not None:
        # Si ad_creation a un timezone, on enlève pour comparaison
        ad_creation = ad_creation.replace(tzinfo=None)

    age_days = (scan_date - ad_creation).days

    if age_days < 0:
        return (False, age_days, reach, None)

    # Vérifier les critères
    for max_age, min_reach in criteria:
        if age_days <= max_age and reach > min_reach:
            criteria_str = f"≤{max_age}d & >{min_reach // 1000}k"
            return (True, age_days, reach, criteria_str)

    return (False, age_days, reach, None)


def save_winning_ads(
    db: DatabaseManager,
    winning_ads_data: List[Dict],
    pages_final: Dict = None
) -> int:
    """
    Sauvegarde les winning ads dans la base de données

    Args:
        db: Instance DatabaseManager
        winning_ads_data: Liste de dictionnaires avec les données des winning ads
        pages_final: Dictionnaire des pages (optionnel, pour récupérer le website)

    Returns:
        Nombre de winning ads sauvegardées
    """
    if not winning_ads_data:
        return 0

    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for data in winning_ads_data:
            ad = data.get("ad", {})
            page_id = str(data.get("page_id", ad.get("page_id", "")))

            # Récupérer le website depuis pages_final si disponible
            website = ""
            if pages_final and page_id in pages_final:
                website = pages_final[page_id].get("website", "")

            # Parser ad_creation_time
            ad_creation = None
            if ad.get("ad_creation_time"):
                try:
                    ad_creation = datetime.fromisoformat(
                        ad["ad_creation_time"].replace("Z", "+00:00")
                    )
                    if ad_creation.tzinfo is not None:
                        ad_creation = ad_creation.replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            winning_entry = WinningAds(
                ad_id=str(ad.get("id", "")),
                page_id=page_id,
                page_name=ad.get("page_name", ""),
                ad_creation_time=ad_creation,
                ad_age_days=data.get("age_days"),
                eu_total_reach=data.get("reach"),
                matched_criteria=data.get("matched_criteria", ""),
                ad_creative_bodies=to_str_list(ad.get("ad_creative_bodies")),
                ad_creative_link_captions=to_str_list(ad.get("ad_creative_link_captions")),
                ad_creative_link_titles=to_str_list(ad.get("ad_creative_link_titles")),
                ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                lien_site=website,
                date_scan=scan_time
            )
            session.add(winning_entry)
            count += 1

    return count


def get_winning_ads(
    db: DatabaseManager,
    page_id: str = None,
    limit: int = 100,
    days: int = None
) -> List[Dict]:
    """
    Récupère les winning ads depuis la base de données

    Args:
        db: Instance DatabaseManager
        page_id: Filtrer par page (optionnel)
        limit: Nombre max de résultats
        days: Filtrer par période en jours (optionnel)

    Returns:
        Liste des winning ads
    """
    from datetime import timedelta

    with db.get_session() as session:
        query = session.query(WinningAds).order_by(
            WinningAds.date_scan.desc(),
            WinningAds.eu_total_reach.desc()
        )

        if page_id:
            query = query.filter(WinningAds.page_id == page_id)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(WinningAds.date_scan >= cutoff)

        entries = query.limit(limit).all()

        return [
            {
                "ad_id": e.ad_id,
                "page_id": e.page_id,
                "page_name": e.page_name,
                "ad_creation_time": e.ad_creation_time,
                "ad_age_days": e.ad_age_days,
                "eu_total_reach": e.eu_total_reach,
                "matched_criteria": e.matched_criteria,
                "ad_creative_bodies": e.ad_creative_bodies,
                "ad_creative_link_captions": e.ad_creative_link_captions,
                "ad_creative_link_titles": e.ad_creative_link_titles,
                "ad_snapshot_url": e.ad_snapshot_url,
                "lien_site": e.lien_site,
                "date_scan": e.date_scan
            }
            for e in entries
        ]


def get_winning_ads_stats(db: DatabaseManager, days: int = 30) -> Dict:
    """
    Récupère les statistiques des winning ads

    Args:
        db: Instance DatabaseManager
        days: Période en jours pour les stats

    Returns:
        Dictionnaire avec les statistiques
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Total winning ads
        total = session.query(WinningAds).filter(
            WinningAds.date_scan >= cutoff
        ).count()

        # Par page (top 10)
        by_page = session.query(
            WinningAds.page_id,
            WinningAds.page_name,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.page_id, WinningAds.page_name
        ).order_by(
            func.count(WinningAds.id).desc()
        ).limit(10).all()

        # Par critère
        by_criteria = session.query(
            WinningAds.matched_criteria,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.matched_criteria
        ).all()

        # Reach moyen
        avg_reach = session.query(
            func.avg(WinningAds.eu_total_reach)
        ).filter(
            WinningAds.date_scan >= cutoff
        ).scalar()

        return {
            "total": total,
            "by_page": [{"page_id": p[0], "page_name": p[1], "count": p[2]} for p in by_page],
            "by_criteria": {c[0]: c[1] for c in by_criteria if c[0]},
            "avg_reach": int(avg_reach) if avg_reach else 0
        }


def get_winning_ads_by_page(
    db: DatabaseManager,
    days: int = 30
) -> Dict[str, int]:
    """
    Récupère le nombre de winning ads par page

    Args:
        db: Instance DatabaseManager
        days: Période en jours

    Returns:
        Dict {page_id: count}
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        results = session.query(
            WinningAds.page_id,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.page_id
        ).all()

        return {r[0]: r[1] for r in results}


# ═══════════════════════════════════════════════════════════════════════════════
# TAGS - Gestion des tags personnalisés
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_tags(db: DatabaseManager) -> List[Dict]:
    """Récupère tous les tags"""
    with db.get_session() as session:
        tags = session.query(Tag).order_by(Tag.name).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]


def create_tag(db: DatabaseManager, name: str, color: str = "#3B82F6") -> Optional[int]:
    """Crée un nouveau tag"""
    with db.get_session() as session:
        existing = session.query(Tag).filter(Tag.name == name).first()
        if existing:
            return None
        tag = Tag(name=name, color=color)
        session.add(tag)
        session.flush()
        return tag.id


def delete_tag(db: DatabaseManager, tag_id: int) -> bool:
    """Supprime un tag et ses associations"""
    with db.get_session() as session:
        # Supprimer les associations
        session.query(PageTag).filter(PageTag.tag_id == tag_id).delete()
        # Supprimer le tag
        deleted = session.query(Tag).filter(Tag.id == tag_id).delete()
        return deleted > 0


def add_tag_to_page(db: DatabaseManager, page_id: str, tag_id: int) -> bool:
    """Ajoute un tag à une page"""
    with db.get_session() as session:
        existing = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).first()
        if existing:
            return False
        pt = PageTag(page_id=page_id, tag_id=tag_id)
        session.add(pt)
        return True


def remove_tag_from_page(db: DatabaseManager, page_id: str, tag_id: int) -> bool:
    """Retire un tag d'une page"""
    with db.get_session() as session:
        deleted = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).delete()
        return deleted > 0


def get_page_tags(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les tags d'une page"""
    with db.get_session() as session:
        results = session.query(Tag).join(
            PageTag, Tag.id == PageTag.tag_id
        ).filter(PageTag.page_id == page_id).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in results]


def get_pages_by_tag(db: DatabaseManager, tag_id: int) -> List[str]:
    """Récupère les page_ids ayant un tag spécifique"""
    with db.get_session() as session:
        results = session.query(PageTag.page_id).filter(PageTag.tag_id == tag_id).all()
        return [r[0] for r in results]


# ═══════════════════════════════════════════════════════════════════════════════
# NOTES - Gestion des notes sur les pages
# ═══════════════════════════════════════════════════════════════════════════════

def get_page_notes(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les notes d'une page"""
    with db.get_session() as session:
        notes = session.query(PageNote).filter(
            PageNote.page_id == page_id
        ).order_by(PageNote.created_at.desc()).all()
        return [{
            "id": n.id,
            "content": n.content,
            "created_at": n.created_at,
            "updated_at": n.updated_at
        } for n in notes]


def add_page_note(db: DatabaseManager, page_id: str, content: str) -> int:
    """Ajoute une note à une page"""
    with db.get_session() as session:
        note = PageNote(page_id=page_id, content=content)
        session.add(note)
        session.flush()
        return note.id


def update_page_note(db: DatabaseManager, note_id: int, content: str) -> bool:
    """Met à jour une note"""
    with db.get_session() as session:
        note = session.query(PageNote).filter(PageNote.id == note_id).first()
        if note:
            note.content = content
            note.updated_at = datetime.utcnow()
            return True
        return False


def delete_page_note(db: DatabaseManager, note_id: int) -> bool:
    """Supprime une note"""
    with db.get_session() as session:
        deleted = session.query(PageNote).filter(PageNote.id == note_id).delete()
        return deleted > 0


# ═══════════════════════════════════════════════════════════════════════════════
# FAVORITES - Gestion des favoris
# ═══════════════════════════════════════════════════════════════════════════════

def get_favorites(db: DatabaseManager) -> List[str]:
    """Récupère tous les page_ids favoris"""
    with db.get_session() as session:
        favs = session.query(Favorite.page_id).order_by(Favorite.added_at.desc()).all()
        return [f[0] for f in favs]


def is_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Vérifie si une page est en favori"""
    with db.get_session() as session:
        return session.query(Favorite).filter(Favorite.page_id == page_id).first() is not None


def add_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Ajoute une page aux favoris"""
    with db.get_session() as session:
        existing = session.query(Favorite).filter(Favorite.page_id == page_id).first()
        if existing:
            return False
        fav = Favorite(page_id=page_id)
        session.add(fav)
        return True


def remove_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Retire une page des favoris"""
    with db.get_session() as session:
        deleted = session.query(Favorite).filter(Favorite.page_id == page_id).delete()
        return deleted > 0


def toggle_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Bascule le statut favori d'une page. Retourne True si maintenant favori."""
    if is_favorite(db, page_id):
        remove_favorite(db, page_id)
        return False
    else:
        add_favorite(db, page_id)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# COLLECTIONS - Gestion des dossiers/collections
# ═══════════════════════════════════════════════════════════════════════════════

def get_collections(db: DatabaseManager) -> List[Dict]:
    """Récupère toutes les collections avec le nombre de pages"""
    from sqlalchemy import func

    with db.get_session() as session:
        collections = session.query(Collection).order_by(Collection.name).all()
        result = []
        for c in collections:
            count = session.query(func.count(CollectionPage.id)).filter(
                CollectionPage.collection_id == c.id
            ).scalar()
            result.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "color": c.color,
                "icon": c.icon,
                "page_count": count or 0,
                "created_at": c.created_at
            })
        return result


def create_collection(
    db: DatabaseManager,
    name: str,
    description: str = "",
    color: str = "#6366F1",
    icon: str = "📁"
) -> int:
    """Crée une nouvelle collection"""
    with db.get_session() as session:
        coll = Collection(name=name, description=description, color=color, icon=icon)
        session.add(coll)
        session.flush()
        return coll.id


def update_collection(
    db: DatabaseManager,
    collection_id: int,
    name: str = None,
    description: str = None,
    color: str = None,
    icon: str = None
) -> bool:
    """Met à jour une collection"""
    with db.get_session() as session:
        coll = session.query(Collection).filter(Collection.id == collection_id).first()
        if not coll:
            return False
        if name is not None:
            coll.name = name
        if description is not None:
            coll.description = description
        if color is not None:
            coll.color = color
        if icon is not None:
            coll.icon = icon
        coll.updated_at = datetime.utcnow()
        return True


def delete_collection(db: DatabaseManager, collection_id: int) -> bool:
    """Supprime une collection et ses associations"""
    with db.get_session() as session:
        session.query(CollectionPage).filter(CollectionPage.collection_id == collection_id).delete()
        deleted = session.query(Collection).filter(Collection.id == collection_id).delete()
        return deleted > 0


def add_page_to_collection(db: DatabaseManager, collection_id: int, page_id: str) -> bool:
    """Ajoute une page à une collection"""
    with db.get_session() as session:
        existing = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).first()
        if existing:
            return False
        cp = CollectionPage(collection_id=collection_id, page_id=page_id)
        session.add(cp)
        return True


def remove_page_from_collection(db: DatabaseManager, collection_id: int, page_id: str) -> bool:
    """Retire une page d'une collection"""
    with db.get_session() as session:
        deleted = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).delete()
        return deleted > 0


def get_collection_pages(db: DatabaseManager, collection_id: int) -> List[str]:
    """Récupère les page_ids d'une collection"""
    with db.get_session() as session:
        results = session.query(CollectionPage.page_id).filter(
            CollectionPage.collection_id == collection_id
        ).all()
        return [r[0] for r in results]


def get_page_collections(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les collections d'une page"""
    with db.get_session() as session:
        results = session.query(Collection).join(
            CollectionPage, Collection.id == CollectionPage.collection_id
        ).filter(CollectionPage.page_id == page_id).all()
        return [{"id": c.id, "name": c.name, "color": c.color, "icon": c.icon} for c in results]


# ═══════════════════════════════════════════════════════════════════════════════
# SAVED FILTERS - Filtres sauvegardés
# ═══════════════════════════════════════════════════════════════════════════════

def get_saved_filters(db: DatabaseManager, filter_type: str = None) -> List[Dict]:
    """Récupère les filtres sauvegardés"""
    import json

    with db.get_session() as session:
        query = session.query(SavedFilter)
        if filter_type:
            query = query.filter(SavedFilter.filter_type == filter_type)
        filters = query.order_by(SavedFilter.name).all()
        return [{
            "id": f.id,
            "name": f.name,
            "filter_type": f.filter_type,
            "filters": json.loads(f.filters_json) if f.filters_json else {},
            "created_at": f.created_at
        } for f in filters]


def save_filter(
    db: DatabaseManager,
    name: str,
    filters: Dict,
    filter_type: str = "pages"
) -> int:
    """Sauvegarde un filtre"""
    import json

    with db.get_session() as session:
        sf = SavedFilter(
            name=name,
            filter_type=filter_type,
            filters_json=json.dumps(filters)
        )
        session.add(sf)
        session.flush()
        return sf.id


def delete_saved_filter(db: DatabaseManager, filter_id: int) -> bool:
    """Supprime un filtre sauvegardé"""
    with db.get_session() as session:
        deleted = session.query(SavedFilter).filter(SavedFilter.id == filter_id).delete()
        return deleted > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULED SCANS - Scans programmés
# ═══════════════════════════════════════════════════════════════════════════════

def get_scheduled_scans(db: DatabaseManager, active_only: bool = False) -> List[Dict]:
    """Récupère les scans programmés"""
    with db.get_session() as session:
        query = session.query(ScheduledScan)
        if active_only:
            query = query.filter(ScheduledScan.is_active == 1)
        scans = query.order_by(ScheduledScan.name).all()
        return [{
            "id": s.id,
            "name": s.name,
            "keywords": s.keywords,
            "countries": s.countries,
            "languages": s.languages,
            "frequency": s.frequency,
            "is_active": s.is_active == 1,
            "last_run": s.last_run,
            "next_run": s.next_run,
            "created_at": s.created_at
        } for s in scans]


def create_scheduled_scan(
    db: DatabaseManager,
    name: str,
    keywords: str,
    countries: str = "FR",
    languages: str = "fr",
    frequency: str = "daily"
) -> int:
    """Crée un nouveau scan programmé"""
    from datetime import timedelta

    # Calculer next_run
    now = datetime.utcnow()
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    elif frequency == "weekly":
        next_run = now + timedelta(weeks=1)
    else:  # monthly
        next_run = now + timedelta(days=30)

    with db.get_session() as session:
        scan = ScheduledScan(
            name=name,
            keywords=keywords,
            countries=countries,
            languages=languages,
            frequency=frequency,
            next_run=next_run
        )
        session.add(scan)
        session.flush()
        return scan.id


def update_scheduled_scan(
    db: DatabaseManager,
    scan_id: int,
    name: str = None,
    keywords: str = None,
    countries: str = None,
    languages: str = None,
    frequency: str = None,
    is_active: bool = None
) -> bool:
    """Met à jour un scan programmé"""
    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False
        if name is not None:
            scan.name = name
        if keywords is not None:
            scan.keywords = keywords
        if countries is not None:
            scan.countries = countries
        if languages is not None:
            scan.languages = languages
        if frequency is not None:
            scan.frequency = frequency
        if is_active is not None:
            scan.is_active = 1 if is_active else 0
        return True


def delete_scheduled_scan(db: DatabaseManager, scan_id: int) -> bool:
    """Supprime un scan programmé"""
    with db.get_session() as session:
        deleted = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).delete()
        return deleted > 0


def mark_scan_executed(db: DatabaseManager, scan_id: int) -> bool:
    """Marque un scan comme exécuté et calcule le prochain run"""
    from datetime import timedelta

    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False

        now = datetime.utcnow()
        scan.last_run = now

        if scan.frequency == "daily":
            scan.next_run = now + timedelta(days=1)
        elif scan.frequency == "weekly":
            scan.next_run = now + timedelta(weeks=1)
        else:
            scan.next_run = now + timedelta(days=30)

        return True


# ═══════════════════════════════════════════════════════════════════════════════
# USER SETTINGS - Paramètres utilisateur
# ═══════════════════════════════════════════════════════════════════════════════

def get_setting(db: DatabaseManager, key: str, default: str = None) -> Optional[str]:
    """Récupère un paramètre utilisateur"""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        return setting.setting_value if setting else default


def set_setting(db: DatabaseManager, key: str, value: str) -> bool:
    """Définit un paramètre utilisateur"""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        if setting:
            setting.setting_value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = UserSettings(setting_key=key, setting_value=value)
            session.add(setting)
        return True


def get_all_settings(db: DatabaseManager) -> Dict[str, str]:
    """Récupère tous les paramètres"""
    with db.get_session() as session:
        settings = session.query(UserSettings).all()
        return {s.setting_key: s.setting_value for s in settings}


# ═══════════════════════════════════════════════════════════════════════════════
# BULK ACTIONS - Actions groupées
# ═══════════════════════════════════════════════════════════════════════════════

def bulk_add_to_blacklist(db: DatabaseManager, page_ids: List[str], raison: str = "") -> int:
    """Ajoute plusieurs pages à la blacklist"""
    count = 0
    for pid in page_ids:
        if add_to_blacklist(db, pid, raison=raison):
            count += 1
    return count


def bulk_add_to_collection(db: DatabaseManager, collection_id: int, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages à une collection"""
    count = 0
    for pid in page_ids:
        if add_page_to_collection(db, collection_id, pid):
            count += 1
    return count


def bulk_add_tag(db: DatabaseManager, tag_id: int, page_ids: List[str]) -> int:
    """Ajoute un tag à plusieurs pages"""
    count = 0
    for pid in page_ids:
        if add_tag_to_page(db, pid, tag_id):
            count += 1
    return count


def bulk_add_to_favorites(db: DatabaseManager, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages aux favoris"""
    count = 0
    for pid in page_ids:
        if add_favorite(db, pid):
            count += 1
    return count
