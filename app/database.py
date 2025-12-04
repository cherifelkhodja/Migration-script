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
