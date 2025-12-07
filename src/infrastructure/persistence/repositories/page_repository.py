"""
Repository pour les operations sur les pages.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from sqlalchemy import func, desc, and_, or_

from src.infrastructure.persistence.models import (
    PageRecherche,
    SuiviPage,
    AdsRecherche,
)
from src.infrastructure.persistence.repositories.utils import get_etat_from_ads_count


def save_pages_recherche(
    db,
    pages_final: Dict,
    web_results: Dict,
    countries: List[str],
    languages: List[str],
    thresholds: Dict = None,
    search_log_id: int = None
) -> tuple:
    """Sauvegarde ou met a jour les pages dans liste_page_recherche."""
    scan_time = datetime.utcnow()
    count = 0
    new_count = 0
    existing_count = 0
    new_page_ids = []
    existing_page_ids = []

    with db.get_session() as session:
        for pid, data in pages_final.items():
            web = web_results.get(pid, {})
            ads_count = data.get("ads_active_total", 0)

            new_keywords = data.get("_keywords", set())
            if isinstance(new_keywords, set):
                new_keywords = list(new_keywords)

            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

            existing_page = session.query(PageRecherche).filter(
                PageRecherche.page_id == str(pid)
            ).first()

            if existing_page:
                existing_keywords_str = existing_page.keywords or ""
                existing_keywords_list = [k.strip() for k in existing_keywords_str.split("|") if k.strip()]

                for kw in new_keywords:
                    if kw and kw not in existing_keywords_list:
                        existing_keywords_list.append(kw)

                merged_keywords = " | ".join(existing_keywords_list)

                existing_pays_str = existing_page.pays or ""
                existing_pays_list = [c.strip().upper() for c in existing_pays_str.split(",") if c.strip()]
                for c in countries:
                    c_upper = c.upper().strip()
                    if c_upper and c_upper not in existing_pays_list:
                        existing_pays_list.append(c_upper)
                merged_pays = ",".join(existing_pays_list)

                existing_lang_str = existing_page.langue or ""
                existing_lang_list = [l.strip() for l in existing_lang_str.split(",") if l.strip()]
                for lang in languages:
                    if lang and lang not in existing_lang_list:
                        existing_lang_list.append(lang)
                merged_langues = ",".join(existing_lang_list)

                existing_page.page_name = data.get("page_name", "") or existing_page.page_name
                existing_page.lien_site = data.get("website", "") or existing_page.lien_site
                existing_page.lien_fb_ad_library = fb_link
                existing_page.keywords = merged_keywords
                if web.get("gemini_category"):
                    existing_page.thematique = web.get("gemini_category", "")
                    existing_page.subcategory = web.get("gemini_subcategory", "")
                    existing_page.classification_confidence = web.get("gemini_confidence", 0.0)
                    existing_page.classified_at = scan_time
                else:
                    existing_page.thematique = web.get("thematique", "") or existing_page.thematique
                existing_page.type_produits = web.get("type_produits", "") or existing_page.type_produits
                existing_page.moyens_paiements = web.get("payments", "") or existing_page.moyens_paiements
                existing_page.pays = merged_pays
                existing_page.langue = merged_langues
                existing_page.cms = data.get("cms") or web.get("cms", "") or existing_page.cms
                existing_page.template = web.get("theme", "") or existing_page.template
                existing_page.devise = data.get("currency", "") or existing_page.devise
                existing_page.etat = get_etat_from_ads_count(ads_count, thresholds)
                existing_page.nombre_ads_active = ads_count
                existing_page.nombre_produits = web.get("product_count", 0) or existing_page.nombre_produits
                existing_page.dernier_scan = scan_time
                existing_page.updated_at = scan_time
                if web.get("site_title"):
                    existing_page.site_title = web.get("site_title", "")[:255]
                if web.get("site_description"):
                    existing_page.site_description = web.get("site_description", "")
                if web.get("site_h1"):
                    existing_page.site_h1 = web.get("site_h1", "")[:200]
                if web.get("site_keywords"):
                    existing_page.site_keywords = web.get("site_keywords", "")[:300]
                if search_log_id:
                    existing_page.last_search_log_id = search_log_id
                    existing_page.was_created_in_last_search = False
                existing_count += 1
                existing_page_ids.append(str(pid))
            else:
                keywords_str = " | ".join(new_keywords) if new_keywords else ""
                pays_str = ",".join([c.upper().strip() for c in countries if c])

                thematique_val = web.get("gemini_category") or web.get("thematique", "")
                subcategory_val = web.get("gemini_subcategory", "")
                confidence_val = web.get("gemini_confidence", 0.0) if web.get("gemini_category") else None
                classified_at_val = scan_time if web.get("gemini_category") else None

                new_page = PageRecherche(
                    page_id=str(pid),
                    page_name=data.get("page_name", ""),
                    lien_site=data.get("website", ""),
                    lien_fb_ad_library=fb_link,
                    keywords=keywords_str,
                    thematique=thematique_val,
                    subcategory=subcategory_val,
                    classification_confidence=confidence_val,
                    classified_at=classified_at_val,
                    type_produits=web.get("type_produits", ""),
                    moyens_paiements=web.get("payments", ""),
                    pays=pays_str,
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
                    last_search_log_id=search_log_id,
                    was_created_in_last_search=True,
                    site_title=web.get("site_title", "")[:255] if web.get("site_title") else None,
                    site_description=web.get("site_description", ""),
                    site_h1=web.get("site_h1", "")[:200] if web.get("site_h1") else None,
                    site_keywords=web.get("site_keywords", "")[:300] if web.get("site_keywords") else None,
                )
                session.add(new_page)
                new_count += 1
                new_page_ids.append(str(pid))

            count += 1

    return (count, new_count, existing_count)


def save_suivi_page(db, pages_final: Dict, web_results: Dict, min_ads: int = 10) -> int:
    """Sauvegarde l'historique des pages dans suivi_page."""
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_final.items():
            ads_count = data.get("ads_active_total", 0)
            if ads_count < min_ads:
                continue

            web = web_results.get(pid, {})

            suivi = SuiviPage(
                page_id=str(pid),
                page_name=data.get("page_name", ""),
                ads_active=ads_count,
                cms=data.get("cms") or web.get("cms", ""),
                thematique=web.get("thematique", ""),
                date_scan=scan_time,
                pays=data.get("country", ""),
            )
            session.add(suivi)
            count += 1

    return count


def save_ads_recherche(db, all_ads: List[Dict], pages_final: Dict) -> int:
    """Sauvegarde les annonces dans ads_recherche."""
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for ad in all_ads:
            page_id = str(ad.get("page_id", ""))

            if page_id not in pages_final:
                continue

            ad_record = AdsRecherche(
                ad_id=str(ad.get("id", "")),
                page_id=page_id,
                page_name=ad.get("page_name", ""),
                ad_creative_bodies=str(ad.get("ad_creative_bodies", [])),
                ad_creative_link_captions=str(ad.get("ad_creative_link_captions", [])),
                ad_creative_link_titles=str(ad.get("ad_creative_link_titles", [])),
                ad_delivery_start_time=ad.get("ad_delivery_start_time"),
                ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                eu_total_reach=ad.get("eu_total_reach"),
                date_scan=scan_time,
            )
            session.add(ad_record)
            count += 1

    return count


def get_all_pages(db, limit: int = 1000) -> List[Dict]:
    """Recupere toutes les pages."""
    with db.get_session() as session:
        pages = session.query(PageRecherche).order_by(
            desc(PageRecherche.dernier_scan)
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
                "dernier_scan": p.dernier_scan,
            }
            for p in pages
        ]


def get_page_history(db, page_id: str) -> List[Dict]:
    """Recupere l'historique d'une page."""
    with db.get_session() as session:
        history = session.query(SuiviPage).filter(
            SuiviPage.page_id == str(page_id)
        ).order_by(desc(SuiviPage.date_scan)).all()

        return [
            {
                "date_scan": h.date_scan,
                "nombre_ads_active": h.nombre_ads_active,
                "nombre_produits": h.nombre_produits,
                "nom_site": h.nom_site,
            }
            for h in history
        ]


def get_page_evolution_history(db, page_id: str, limit: int = 30) -> List[Dict]:
    """
    Recupere l'historique d'evolution d'une page pour les graphiques analytics.

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page Facebook
        limit: Nombre max d'entrees a retourner

    Returns:
        Liste de dicts avec date_scan, nombre_ads_active, nombre_produits
    """
    with db.get_session() as session:
        history = session.query(SuiviPage).filter(
            SuiviPage.page_id == str(page_id)
        ).order_by(desc(SuiviPage.date_scan)).limit(limit).all()

        return [
            {
                "date_scan": h.date_scan,
                "nombre_ads_active": h.nombre_ads_active or 0,
                "nombre_produits": h.nombre_produits or 0,
            }
            for h in history
        ]


def get_all_countries(db) -> List[str]:
    """Recupere tous les pays distincts."""
    with db.get_session() as session:
        results = session.query(PageRecherche.pays).distinct().all()
        countries = set()
        for r in results:
            if r.pays:
                for c in r.pays.split(","):
                    c = c.strip().upper()
                    if c:
                        countries.add(c)
        return sorted(list(countries))


def get_all_subcategories(db, category: str = None) -> List[str]:
    """Recupere toutes les sous-categories."""
    with db.get_session() as session:
        query = session.query(PageRecherche.subcategory).filter(
            PageRecherche.subcategory != None,
            PageRecherche.subcategory != ""
        )
        if category:
            query = query.filter(PageRecherche.thematique == category)
        results = query.distinct().all()
        return sorted([r.subcategory for r in results if r.subcategory])


def add_country_to_page(db, page_id: str, country: str) -> bool:
    """Ajoute un pays a une page."""
    country = country.upper().strip()
    with db.get_session() as session:
        page = session.query(PageRecherche).filter(
            PageRecherche.page_id == str(page_id)
        ).first()

        if not page:
            return False

        existing_pays = page.pays or ""
        pays_list = [c.strip().upper() for c in existing_pays.split(",") if c.strip()]

        if country not in pays_list:
            pays_list.append(country)
            page.pays = ",".join(pays_list)
            return True
        return False


def get_pages_count(db) -> Dict:
    """Compte les pages par statut."""
    with db.get_session() as session:
        total = session.query(func.count(PageRecherche.id)).scalar() or 0
        by_cms = session.query(
            PageRecherche.cms,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.cms).all()

        by_etat = session.query(
            PageRecherche.etat,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.etat).all()

        return {
            "total": total,
            "by_cms": {c: n for c, n in by_cms if c},
            "by_etat": {e: n for e, n in by_etat if e},
        }
