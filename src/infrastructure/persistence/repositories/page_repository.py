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
    WinningAds,
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


def get_evolution_stats(db, period_days: int = 7) -> List[Dict]:
    """
    Calcule les statistiques d'evolution des pages sur une periode donnee.

    Compare le dernier scan de chaque page avec le scan precedent
    pour detecter les hausses/baisses d'activite publicitaire.

    Args:
        db: Instance DatabaseManager
        period_days: Periode en jours pour l'analyse

    Returns:
        Liste de dicts avec les champs:
        - page_id, nom_site
        - delta_ads, pct_ads (evolution ads)
        - delta_produits (evolution produits)
        - ads_actuel, produits_actuel
        - date_actuel, date_precedent
        - duree_jours (jours entre les 2 scans)
    """
    from sqlalchemy import func, desc
    from collections import defaultdict

    cutoff = datetime.utcnow() - timedelta(days=period_days)

    with db.get_session() as session:
        # Recuperer tous les scans de la periode, groupes par page
        scans = session.query(SuiviPage).filter(
            SuiviPage.date_scan >= cutoff
        ).order_by(SuiviPage.page_id, desc(SuiviPage.date_scan)).all()

        # Grouper par page_id
        pages_scans = defaultdict(list)
        for scan in scans:
            pages_scans[scan.page_id].append(scan)

        evolution_list = []

        for page_id, page_scans in pages_scans.items():
            # Il faut au moins 2 scans pour calculer une evolution
            if len(page_scans) < 2:
                continue

            # Premier = plus recent, second = precedent
            current = page_scans[0]
            previous = page_scans[1]

            # Calculer les deltas
            ads_actuel = current.nombre_ads_active or 0
            ads_precedent = previous.nombre_ads_active or 0
            delta_ads = ads_actuel - ads_precedent

            produits_actuel = current.nombre_produits or 0
            produits_precedent = previous.nombre_produits or 0
            delta_produits = produits_actuel - produits_precedent

            # Pourcentage de changement
            pct_ads = 0.0
            if ads_precedent > 0:
                pct_ads = (delta_ads / ads_precedent) * 100

            # Duree entre les scans
            duree_jours = 0.0
            if current.date_scan and previous.date_scan:
                duree_jours = (current.date_scan - previous.date_scan).total_seconds() / 86400

            evolution_list.append({
                "page_id": page_id,
                "nom_site": current.nom_site or page_id,
                "delta_ads": delta_ads,
                "pct_ads": pct_ads,
                "ads_actuel": ads_actuel,
                "produits_actuel": produits_actuel,
                "delta_produits": delta_produits,
                "date_actuel": current.date_scan,
                "date_precedent": previous.date_scan,
                "duree_jours": duree_jours,
            })

        # Trier par amplitude du changement (absolu)
        evolution_list.sort(key=lambda x: abs(x["delta_ads"]), reverse=True)

        return evolution_list


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
    """Compte les pages par statut pour la migration."""
    with db.get_session() as session:
        total = session.query(func.count(PageRecherche.id)).scalar() or 0

        # Pages classifiees (ont une thematique)
        classified = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.thematique.isnot(None),
            PageRecherche.thematique != ""
        ).scalar() or 0

        # Pages avec FR dans pays
        with_fr = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.pays.ilike("%FR%")
        ).scalar() or 0

        # Pages sans FR
        without_fr = total - with_fr

        # Pages non classifiees
        unclassified = total - classified

        return {
            "total": total,
            "classified": classified,
            "with_fr": with_fr,
            "without_fr": without_fr,
            "unclassified": unclassified,
        }


def migration_add_country_to_all_pages(db, country: str) -> int:
    """
    Ajoute un pays a toutes les pages qui ne l'ont pas encore.

    Args:
        db: Instance DatabaseManager
        country: Code pays a ajouter (ex: "FR")

    Returns:
        Nombre de pages mises a jour
    """
    country = country.upper().strip()
    updated = 0

    with db.get_session() as session:
        # Trouver les pages sans ce pays
        pages = session.query(PageRecherche).filter(
            or_(
                PageRecherche.pays.is_(None),
                PageRecherche.pays == "",
                ~PageRecherche.pays.ilike(f"%{country}%")
            )
        ).all()

        for page in pages:
            existing_pays = page.pays or ""
            pays_list = [c.strip().upper() for c in existing_pays.split(",") if c.strip()]

            if country not in pays_list:
                pays_list.append(country)
                page.pays = ",".join(pays_list)
                updated += 1

    return updated


def get_suivi_stats_filtered(
    db,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None,
) -> Dict:
    """
    Statistiques du suivi avec filtres.

    Permet de filtrer les statistiques par thematique, sous-categorie et pays.

    Args:
        db: Instance DatabaseManager
        thematique: Filtre par thematique (ex: "E-commerce")
        subcategory: Filtre par sous-categorie
        pays: Filtre par pays (recherche partielle)

    Returns:
        Dict avec total_pages, etats (distribution), cms (distribution)
    """
    with db.get_session() as session:
        query = session.query(PageRecherche)

        if thematique:
            query = query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            query = query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))

        pages = query.all()
        total_pages = len(pages)

        # Compter par etat et CMS
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
    db,
    page_ids: List[str],
    cache_days: int = 1,
) -> Dict[str, Dict]:
    """
    Recupere les infos cachees des pages (scan recent).

    Utilise pour optimiser les recherches en evitant de re-scanner
    les pages deja scannees recemment.

    Args:
        db: Instance DatabaseManager
        page_ids: Liste des IDs de pages a verifier
        cache_days: Nombre de jours pour considerer le cache valide

    Returns:
        Dict[page_id] = {
            "lien_site": str,
            "cms": str,
            "etat": str,
            "nombre_ads_active": int,
            "thematique": str,
            "needs_rescan": bool
        }
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


def get_dashboard_trends(db, days: int = 7) -> Dict:
    """
    Calcule les tendances pour le dashboard.

    Compare la periode actuelle avec la periode precedente pour
    afficher les deltas et tendances.

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours pour la comparaison

    Returns:
        Dict avec:
        - pages: {current, previous, delta}
        - winning_ads: {current, previous, delta}
        - evolution: {rising, falling}
    """
    from src.infrastructure.persistence.models import WinningAds

    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    with db.get_session() as session:
        # Pages: compter les nouvelles pages
        current_pages = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.created_at >= current_start
        ).scalar() or 0

        previous_pages = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.created_at >= previous_start,
            PageRecherche.created_at < current_start
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

        # Evolution: pages en hausse/baisse
        try:
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


def get_archive_stats(db) -> Dict:
    """
    Retourne les statistiques pour l'archivage.

    Args:
        db: Instance DatabaseManager

    Returns:
        Dict avec les stats d'archivage (pages, ads, winning_ads)
    """
    cutoff_90 = datetime.utcnow() - timedelta(days=90)

    with db.get_session() as session:
        # Compter les pages anciennes (sans activite recente)
        pages_old = session.query(func.count(PageRecherche.id)).filter(
            or_(
                PageRecherche.dernier_scan.is_(None),
                PageRecherche.dernier_scan < cutoff_90
            )
        ).scalar() or 0

        # Compter les ads anciennes
        ads_old = session.query(func.count(AdsRecherche.id)).filter(
            AdsRecherche.date_scan < cutoff_90
        ).scalar() or 0

        # Compter les winning ads anciennes
        winning_old = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan < cutoff_90
        ).scalar() or 0

        # Totaux
        total_pages = session.query(func.count(PageRecherche.id)).scalar() or 0
        total_ads = session.query(func.count(AdsRecherche.id)).scalar() or 0
        total_winning = session.query(func.count(WinningAds.id)).scalar() or 0

        return {
            "pages": {"total": total_pages, "archivable": pages_old},
            "ads": {"total": total_ads, "archivable": ads_old},
            "winning_ads": {"total": total_winning, "archivable": winning_old},
        }


def archive_old_data(db, days_threshold: int = 90) -> Dict[str, int]:
    """
    Archive les donnees plus anciennes que le seuil specifie.

    Note: Pour simplifier, cette fonction supprime les anciennes entrees.
    Une implementation complete devrait deplacer vers des tables d'archive.

    Args:
        db: Instance DatabaseManager
        days_threshold: Nombre de jours avant archivage

    Returns:
        Dict avec le nombre d'entrees archivees par type
    """
    cutoff = datetime.utcnow() - timedelta(days=days_threshold)
    result = {"ads": 0, "winning_ads": 0, "suivi": 0}

    with db.get_session() as session:
        # Supprimer les anciennes ads
        ads_deleted = session.query(AdsRecherche).filter(
            AdsRecherche.date_scan < cutoff
        ).delete(synchronize_session=False)
        result["ads"] = ads_deleted

        # Supprimer les anciens suivis
        suivi_deleted = session.query(SuiviPage).filter(
            SuiviPage.date_scan < cutoff
        ).delete(synchronize_session=False)
        result["suivi"] = suivi_deleted

        # Supprimer les anciennes winning ads
        winning_deleted = session.query(WinningAds).filter(
            WinningAds.date_scan < cutoff
        ).delete(synchronize_session=False)
        result["winning_ads"] = winning_deleted

    return result
