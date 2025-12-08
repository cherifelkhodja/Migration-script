"""
Repository pour les operations sur les pages.

Multi-tenancy:
--------------
Toutes les fonctions acceptent un parametre optionnel user_id (UUID).
- Si user_id est fourni: les donnees sont filtrees/associees a cet utilisateur
- Si user_id est None: les donnees sont considerees comme systeme/partagees
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from uuid import UUID

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.sql import false as sql_false

from src.infrastructure.persistence.models import (
    PageRecherche,
    SuiviPage,
    AdsRecherche,
    WinningAds,
)
from src.infrastructure.persistence.repositories.utils import get_etat_from_ads_count


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


def _parse_product_count(value) -> int:
    """Convertit product_count en entier (0 si N/A, None, ou invalide)."""
    if value is None or value == "N/A":
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def save_pages_recherche(
    db,
    pages_final: Dict,
    web_results: Dict,
    countries: List[str],
    languages: List[str],
    thresholds: Dict = None,
    search_log_id: int = None,
    user_id: Optional[UUID] = None
) -> tuple:
    """
    Sauvegarde ou met a jour les pages dans liste_page_recherche.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
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

            # Filtrer par user_id pour trouver la page existante
            query = session.query(PageRecherche).filter(PageRecherche.page_id == str(pid))
            if user_id is not None:
                query = query.filter(PageRecherche.user_id == user_id)
            else:
                query = query.filter(PageRecherche.user_id.is_(None))
            existing_page = query.first()

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
                new_product_count = _parse_product_count(web.get("product_count"))
                if new_product_count > 0:
                    existing_page.nombre_produits = new_product_count
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
                    user_id=user_id,  # Multi-tenancy
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
                    nombre_produits=_parse_product_count(web.get("product_count")),
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


def save_suivi_page(
    db,
    pages_final: Dict,
    web_results: Dict,
    min_ads: int = 10,
    user_id: Optional[UUID] = None
) -> int:
    """
    Sauvegarde l'historique des pages dans suivi_page.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
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
                user_id=user_id,  # Multi-tenancy
                page_id=str(pid),
                nom_site=data.get("page_name", ""),
                nombre_ads_active=ads_count,
                date_scan=scan_time,
            )
            session.add(suivi)
            count += 1

    return count


def save_ads_recherche(
    db,
    pages_final: Dict,
    page_ads: Dict,
    countries: List[str] = None,
    min_ads_liste: int = 1,
    user_id: Optional[UUID] = None
) -> int:
    """
    Sauvegarde les annonces dans ads_recherche.

    Args:
        db: DatabaseManager instance
        pages_final: Dict des pages finales (page_id -> page_data)
        page_ads: Dict des ads par page (page_id -> list of ads)
        countries: Liste des pays (optionnel, pour compatibilité)
        min_ads_liste: Seuil minimum d'ads pour sauvegarder (optionnel)
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Nombre d'annonces sauvegardées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for page_id, ads in page_ads.items():
            page_id_str = str(page_id)

            # Ne sauvegarder que les ads des pages finales
            if page_id_str not in pages_final:
                continue

            # Vérifier le seuil minimum
            if len(ads) < min_ads_liste:
                continue

            for ad in ads:
                # Parser ad_creation_time
                ad_creation = None
                if ad.get("ad_creation_time"):
                    try:
                        ad_creation_str = ad["ad_creation_time"]
                        if isinstance(ad_creation_str, str):
                            ad_creation = datetime.fromisoformat(
                                ad_creation_str.replace("Z", "+00:00")
                            )
                        else:
                            ad_creation = ad_creation_str
                    except (ValueError, AttributeError):
                        pass

                ad_record = AdsRecherche(
                    user_id=user_id,  # Multi-tenancy
                    ad_id=str(ad.get("id", "")),
                    page_id=page_id_str,
                    page_name=ad.get("page_name", ""),
                    ad_creative_bodies=str(ad.get("ad_creative_bodies", [])),
                    ad_creative_link_captions=str(ad.get("ad_creative_link_captions", [])),
                    ad_creative_link_titles=str(ad.get("ad_creative_link_titles", [])),
                    ad_creation_time=ad_creation,
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    eu_total_reach=ad.get("eu_total_reach"),
                    date_scan=scan_time,
                )
                session.add(ad_record)
                count += 1

    return count


def get_all_pages(
    db,
    limit: int = 1000,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere toutes les pages.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    with db.get_session() as session:
        query = session.query(PageRecherche)
        query = _apply_user_filter(query, PageRecherche, user_id)
        pages = query.order_by(
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


def get_page_history(
    db,
    page_id: str,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere l'historique d'une page.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    with db.get_session() as session:
        query = session.query(SuiviPage).filter(
            SuiviPage.page_id == str(page_id)
        )
        query = _apply_user_filter(query, SuiviPage, user_id)
        history = query.order_by(desc(SuiviPage.date_scan)).all()

        return [
            {
                "date_scan": h.date_scan,
                "nombre_ads_active": h.nombre_ads_active,
                "nombre_produits": h.nombre_produits,
                "nom_site": h.nom_site,
            }
            for h in history
        ]


def get_page_evolution_history(
    db,
    page_id: str,
    limit: int = 30,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere l'historique d'evolution d'une page pour les graphiques analytics.

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page Facebook
        limit: Nombre max d'entrees a retourner
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Liste de dicts avec date_scan, nombre_ads_active, nombre_produits
    """
    with db.get_session() as session:
        query = session.query(SuiviPage).filter(
            SuiviPage.page_id == str(page_id)
        )
        query = _apply_user_filter(query, SuiviPage, user_id)
        history = query.order_by(desc(SuiviPage.date_scan)).limit(limit).all()

        return [
            {
                "date_scan": h.date_scan,
                "nombre_ads_active": h.nombre_ads_active or 0,
                "nombre_produits": h.nombre_produits or 0,
            }
            for h in history
        ]


def get_evolution_stats(
    db,
    period_days: int = 7,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Calcule les statistiques d'evolution des pages sur une periode donnee.

    Compare le dernier scan de chaque page avec le scan precedent
    pour detecter les hausses/baisses d'activite publicitaire.

    Args:
        db: Instance DatabaseManager
        period_days: Periode en jours pour l'analyse
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

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
        query = session.query(SuiviPage).filter(
            SuiviPage.date_scan >= cutoff
        )
        query = _apply_user_filter(query, SuiviPage, user_id)
        scans = query.order_by(SuiviPage.page_id, desc(SuiviPage.date_scan)).all()

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


def get_all_countries(db, user_id: Optional[UUID] = None) -> List[str]:
    """
    Recupere tous les pays distincts.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    with db.get_session() as session:
        query = session.query(PageRecherche.pays)
        query = _apply_user_filter(query, PageRecherche, user_id)
        results = query.distinct().all()
        countries = set()
        for r in results:
            if r.pays:
                for c in r.pays.split(","):
                    c = c.strip().upper()
                    if c:
                        countries.add(c)
        return sorted(list(countries))


def get_all_subcategories(
    db,
    category: str = None,
    user_id: Optional[UUID] = None
) -> List[str]:
    """
    Recupere toutes les sous-categories.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    with db.get_session() as session:
        query = session.query(PageRecherche.subcategory).filter(
            PageRecherche.subcategory != None,
            PageRecherche.subcategory != ""
        )
        query = _apply_user_filter(query, PageRecherche, user_id)
        if category:
            query = query.filter(PageRecherche.thematique == category)
        results = query.distinct().all()
        return sorted([r.subcategory for r in results if r.subcategory])


def add_country_to_page(
    db,
    page_id: str,
    country: str,
    user_id: Optional[UUID] = None
) -> bool:
    """
    Ajoute un pays a une page.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    country = country.upper().strip()
    with db.get_session() as session:
        query = session.query(PageRecherche).filter(
            PageRecherche.page_id == str(page_id)
        )
        query = _apply_user_filter(query, PageRecherche, user_id)
        page = query.first()

        if not page:
            return False

        existing_pays = page.pays or ""
        pays_list = [c.strip().upper() for c in existing_pays.split(",") if c.strip()]

        if country not in pays_list:
            pays_list.append(country)
            page.pays = ",".join(pays_list)
            return True
        return False


def get_pages_count(db, user_id: Optional[UUID] = None) -> Dict:
    """
    Compte les pages par statut pour la migration.

    Args:
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.
    """
    with db.get_session() as session:
        base_query = session.query(func.count(PageRecherche.id))
        if user_id is not None:
            base_query = base_query.filter(PageRecherche.user_id == user_id)

        total = base_query.scalar() or 0

        # Pages classifiees (ont une thematique)
        classified_query = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.thematique.isnot(None),
            PageRecherche.thematique != ""
        )
        if user_id is not None:
            classified_query = classified_query.filter(PageRecherche.user_id == user_id)
        classified = classified_query.scalar() or 0

        # Pages avec FR dans pays
        with_fr_query = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.pays.ilike("%FR%")
        )
        if user_id is not None:
            with_fr_query = with_fr_query.filter(PageRecherche.user_id == user_id)
        with_fr = with_fr_query.scalar() or 0

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
    user_id: Optional[UUID] = None,
) -> Dict:
    """
    Statistiques du suivi avec filtres.

    Permet de filtrer les statistiques par thematique, sous-categorie et pays.

    Args:
        db: Instance DatabaseManager
        thematique: Filtre par thematique (ex: "E-commerce")
        subcategory: Filtre par sous-categorie
        pays: Filtre par pays (recherche partielle)
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dict avec total_pages, etats (distribution), cms (distribution)
    """
    with db.get_session() as session:
        query = session.query(PageRecherche)
        query = _apply_user_filter(query, PageRecherche, user_id)

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
    user_id: Optional[UUID] = None,
) -> Dict[str, Dict]:
    """
    Recupere les infos cachees des pages (scan recent).

    Utilise pour optimiser les recherches en evitant de re-scanner
    les pages deja scannees recemment.

    Args:
        db: Instance DatabaseManager
        page_ids: Liste des IDs de pages a verifier
        cache_days: Nombre de jours pour considerer le cache valide
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

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
        query = session.query(PageRecherche).filter(
            PageRecherche.page_id.in_([str(pid) for pid in page_ids])
        )
        query = _apply_user_filter(query, PageRecherche, user_id)
        pages = query.all()

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


def get_dashboard_trends(db, days: int = 7, user_id: Optional[UUID] = None) -> Dict:
    """
    Calcule les tendances pour le dashboard.

    Compare la periode actuelle avec la periode precedente pour
    afficher les deltas et tendances.

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours pour la comparaison
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

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
        current_pages_query = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.created_at >= current_start
        )
        if user_id is not None:
            current_pages_query = current_pages_query.filter(PageRecherche.user_id == user_id)
        current_pages = current_pages_query.scalar() or 0

        previous_pages_query = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.created_at >= previous_start,
            PageRecherche.created_at < current_start
        )
        if user_id is not None:
            previous_pages_query = previous_pages_query.filter(PageRecherche.user_id == user_id)
        previous_pages = previous_pages_query.scalar() or 0

        pages_delta = current_pages - previous_pages

        # Winning ads
        current_winning_query = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan >= current_start
        )
        if user_id is not None:
            current_winning_query = current_winning_query.filter(WinningAds.user_id == user_id)
        current_winning = current_winning_query.scalar() or 0

        previous_winning_query = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan >= previous_start,
            WinningAds.date_scan < current_start
        )
        if user_id is not None:
            previous_winning_query = previous_winning_query.filter(WinningAds.user_id == user_id)
        previous_winning = previous_winning_query.scalar() or 0

        winning_delta = current_winning - previous_winning

        # Evolution: pages en hausse/baisse
        try:
            evolution = get_evolution_stats(db, period_days=days, user_id=user_id)
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


def get_archive_stats(db, user_id: Optional[UUID] = None) -> Dict:
    """
    Retourne les statistiques pour l'archivage.

    Args:
        db: Instance DatabaseManager
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dict avec les stats d'archivage (clés plates pour compatibilité UI)
    """
    from src.infrastructure.persistence.models import (
        SuiviPageArchive, AdsRechercheArchive, WinningAdsArchive
    )

    cutoff_90 = datetime.utcnow() - timedelta(days=90)

    with db.get_session() as session:
        # Compter les suivi_page totaux et archivables
        suivi_total_q = session.query(func.count(SuiviPage.id))
        if user_id is not None:
            suivi_total_q = suivi_total_q.filter(SuiviPage.user_id == user_id)
        suivi_total = suivi_total_q.scalar() or 0

        suivi_archivable_q = session.query(func.count(SuiviPage.id)).filter(
            SuiviPage.date_scan < cutoff_90
        )
        if user_id is not None:
            suivi_archivable_q = suivi_archivable_q.filter(SuiviPage.user_id == user_id)
        suivi_archivable = suivi_archivable_q.scalar() or 0

        # Compter les ads totales et archivables
        ads_total_q = session.query(func.count(AdsRecherche.id))
        if user_id is not None:
            ads_total_q = ads_total_q.filter(AdsRecherche.user_id == user_id)
        ads_total = ads_total_q.scalar() or 0

        ads_archivable_q = session.query(func.count(AdsRecherche.id)).filter(
            AdsRecherche.date_scan < cutoff_90
        )
        if user_id is not None:
            ads_archivable_q = ads_archivable_q.filter(AdsRecherche.user_id == user_id)
        ads_archivable = ads_archivable_q.scalar() or 0

        # Compter les winning ads totales et archivables
        winning_total_q = session.query(func.count(WinningAds.id))
        if user_id is not None:
            winning_total_q = winning_total_q.filter(WinningAds.user_id == user_id)
        winning_total = winning_total_q.scalar() or 0

        winning_archivable_q = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan < cutoff_90
        )
        if user_id is not None:
            winning_archivable_q = winning_archivable_q.filter(WinningAds.user_id == user_id)
        winning_archivable = winning_archivable_q.scalar() or 0

        # Compter les entrées déjà archivées
        try:
            suivi_archive_q = session.query(func.count(SuiviPageArchive.id))
            if user_id is not None:
                suivi_archive_q = suivi_archive_q.filter(SuiviPageArchive.user_id == user_id)
            suivi_archive = suivi_archive_q.scalar() or 0
        except Exception:
            suivi_archive = 0

        try:
            ads_archive_q = session.query(func.count(AdsRechercheArchive.id))
            if user_id is not None:
                ads_archive_q = ads_archive_q.filter(AdsRechercheArchive.user_id == user_id)
            ads_archive = ads_archive_q.scalar() or 0
        except Exception:
            ads_archive = 0

        try:
            winning_archive_q = session.query(func.count(WinningAdsArchive.id))
            if user_id is not None:
                winning_archive_q = winning_archive_q.filter(WinningAdsArchive.user_id == user_id)
            winning_archive = winning_archive_q.scalar() or 0
        except Exception:
            winning_archive = 0

        return {
            # Totaux actuels
            "suivi_page": suivi_total,
            "liste_ads_recherche": ads_total,
            "winning_ads": winning_total,
            # Archivables (>90 jours)
            "suivi_page_archivable": suivi_archivable,
            "liste_ads_recherche_archivable": ads_archivable,
            "winning_ads_archivable": winning_archivable,
            # Déjà archivés
            "suivi_page_archive": suivi_archive,
            "liste_ads_recherche_archive": ads_archive,
            "winning_ads_archive": winning_archive,
        }


def archive_old_data(
    db,
    days_threshold: int = 90,
    user_id: Optional[UUID] = None
) -> Dict[str, int]:
    """
    Archive les donnees plus anciennes que le seuil specifie.

    Note: Pour simplifier, cette fonction supprime les anciennes entrees.
    Une implementation complete devrait deplacer vers des tables d'archive.

    Args:
        db: Instance DatabaseManager
        days_threshold: Nombre de jours avant archivage
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dict avec le nombre d'entrees archivees par type
    """
    cutoff = datetime.utcnow() - timedelta(days=days_threshold)
    result = {"ads": 0, "winning_ads": 0, "suivi": 0}

    with db.get_session() as session:
        # Supprimer les anciennes ads
        ads_query = session.query(AdsRecherche).filter(AdsRecherche.date_scan < cutoff)
        if user_id is not None:
            ads_query = ads_query.filter(AdsRecherche.user_id == user_id)
        ads_deleted = ads_query.delete(synchronize_session=False)
        result["ads"] = ads_deleted

        # Supprimer les anciens suivis
        suivi_query = session.query(SuiviPage).filter(SuiviPage.date_scan < cutoff)
        if user_id is not None:
            suivi_query = suivi_query.filter(SuiviPage.user_id == user_id)
        suivi_deleted = suivi_query.delete(synchronize_session=False)
        result["suivi"] = suivi_deleted

        # Supprimer les anciennes winning ads
        winning_query = session.query(WinningAds).filter(WinningAds.date_scan < cutoff)
        if user_id is not None:
            winning_query = winning_query.filter(WinningAds.user_id == user_id)
        winning_deleted = winning_query.delete(synchronize_session=False)
        result["winning_ads"] = winning_deleted

    return result


def recalculate_all_page_states(
    db,
    thresholds: Dict[str, int],
    user_id: Optional[UUID] = None
) -> Dict[str, int]:
    """
    Recalcule l'etat de toutes les pages selon les nouveaux seuils.

    Cette fonction est appelee automatiquement lors d'un changement de seuils
    dans les Settings pour assurer la coherence des etats.

    Args:
        db: Instance DatabaseManager
        thresholds: Dict des seuils {XS: 1, S: 10, M: 20, L: 35, XL: 80, XXL: 150}
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dict avec statistiques du recalcul:
            - total_pages: Nombre total de pages traitees
            - updated: Nombre de pages dont l'etat a change
            - by_state: Repartition par nouvel etat
    """
    stats = {
        "total_pages": 0,
        "updated": 0,
        "by_state": {"inactif": 0, "XS": 0, "S": 0, "M": 0, "L": 0, "XL": 0, "XXL": 0}
    }

    with db.get_session() as session:
        query = session.query(PageRecherche)
        query = _apply_user_filter(query, PageRecherche, user_id)
        pages = query.all()
        stats["total_pages"] = len(pages)

        for page in pages:
            ads_count = page.nombre_ads_active or 0
            new_state = get_etat_from_ads_count(ads_count, thresholds)

            # Compter la nouvelle repartition
            stats["by_state"][new_state] = stats["by_state"].get(new_state, 0) + 1

            # Mettre a jour si l'etat a change
            if page.etat != new_state:
                page.etat = new_state
                stats["updated"] += 1

    return stats
