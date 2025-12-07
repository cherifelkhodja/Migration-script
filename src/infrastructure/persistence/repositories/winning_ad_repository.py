"""
Repository pour la gestion des Winning Ads.

Une "Winning Ad" est une publicite performante identifiee selon des criteres
de reach (portee) et d'age (duree de diffusion). Plus une ad est jeune avec
un reach eleve, plus elle est consideree comme performante.

Logique metier:
---------------
Les criteres de qualification sont bases sur la relation age/reach:
- Une ad de 4 jours doit avoir au moins 15,000 de reach
- Une ad de 30 jours doit avoir au moins 500,000 de reach
- Entre ces bornes, le seuil augmente progressivement

Ce modele identifie les publicites qui "performent" car elles atteignent
rapidement une large audience, signe d'une creative efficace.

Exemple:
    Une ad de 7 jours avec 50,000 de reach est winning car elle depasse
    le seuil de 40,000 requis pour son age.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.dialects.postgresql import insert

from src.infrastructure.persistence.models import WinningAds, PageRecherche


def _apply_user_filter(query, model, user_id: Optional[UUID]):
    """Applique le filtre user_id a une query."""
    if user_id is not None:
        return query.filter(model.user_id == user_id)
    return query


# Criteres de qualification Winning Ad: (age_max_jours, reach_minimum)
# Logique: Plus l'ad est jeune, moins elle a besoin de reach pour etre qualifiee
# Ces seuils sont calibres sur les donnees Meta Ads europeennes
DEFAULT_WINNING_CRITERIA = [
    (4, 15_000),    # 4 jours  -> 15K minimum (ads tres recentes, forte traction)
    (5, 20_000),    # 5 jours  -> 20K
    (6, 30_000),    # 6 jours  -> 30K
    (7, 40_000),    # 7 jours  -> 40K (1 semaine)
    (8, 50_000),    # 8 jours  -> 50K
    (9, 60_000),    # 9 jours  -> 60K
    (10, 75_000),   # 10 jours -> 75K
    (11, 85_000),   # 11 jours -> 85K
    (12, 100_000),  # 12 jours -> 100K
    (13, 120_000),  # 13 jours -> 120K
    (14, 140_000),  # 14 jours -> 140K (2 semaines)
    (15, 160_000),  # 15 jours -> 160K
    (20, 250_000),  # 20 jours -> 250K
    (25, 350_000),  # 25 jours -> 350K
    (30, 500_000),  # 30 jours -> 500K (1 mois, seuil max)
]


def is_winning_ad(
    ad: Dict,
    scan_date: datetime,
    criteria: List[Tuple[int, int]] = None
) -> Tuple[bool, int, int, str]:
    """
    Determine si une annonce est qualifiee comme "Winning Ad".

    L'algorithme compare l'age de l'ad (depuis ad_creation_time) avec
    son reach (eu_total_reach) selon une matrice de criteres. Une ad est
    winning si elle atteint le seuil de reach requis pour son age.

    Args:
        ad: Dictionnaire de donnees de l'annonce Meta contenant:
            - ad_creation_time: Date ISO de creation de l'annonce
            - eu_total_reach: Nombre de personnes atteintes (EU)
        scan_date: Date de reference pour calculer l'age de l'ad
        criteria: Liste optionnelle de tuples (age_max, reach_min).
                  Si None, utilise DEFAULT_WINNING_CRITERIA.

    Returns:
        Tuple de 4 elements:
            - is_winning (bool): True si l'ad est qualifiee
            - age_days (int): Age de l'ad en jours
            - reach (int): Reach de l'ad
            - matched_criteria (str): Description du critere matche (ex: "7j/50,000")
                                      ou chaine vide si non qualifiee

    Example:
        >>> ad = {"ad_creation_time": "2024-01-01", "eu_total_reach": 50000}
        >>> is_winning, age, reach, criteria = is_winning_ad(ad, datetime(2024, 1, 8))
        >>> is_winning  # True car 7 jours avec 50K >= seuil de 40K
        True
    """
    if criteria is None:
        criteria = DEFAULT_WINNING_CRITERIA

    # Extraction et validation de la date de creation
    # Note: L'API Meta retourne ad_creation_time (pas ad_delivery_start_time)
    start_str = ad.get("ad_creation_time", "")
    if not start_str:
        return (False, 0, 0, "")

    # Parsing de la date (format ISO avec ou sans timezone)
    try:
        if isinstance(start_str, str):
            start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        else:
            start_date = start_str
        # Normalisation: suppression du timezone pour comparaison
        start_date = start_date.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return (False, 0, 0, "")

    # Calcul de l'age en jours
    age_days = (scan_date - start_date).days
    if age_days < 0:
        age_days = 0  # Protection contre les dates futures

    # Extraction et validation du reach
    reach = ad.get("eu_total_reach", 0) or 0
    if isinstance(reach, str):
        try:
            reach = int(reach)
        except ValueError:
            reach = 0

    # Evaluation contre les criteres (ordre croissant d'age)
    # On matche le premier critere ou l'ad est eligible
    for max_age, min_reach in criteria:
        if age_days <= max_age and reach >= min_reach:
            # Format lisible: ≤4d & >15k (basé sur les seuils, pas les valeurs)
            criteria_str = f"≤{max_age}d & >{min_reach // 1000}k"
            return (True, age_days, reach, criteria_str)

    return (False, age_days, reach, "")


def save_winning_ads(
    db,
    winning_ads_data: List[Dict],
    search_log_id: int = None,
    user_id: Optional[UUID] = None
) -> Tuple[int, int, int]:
    """
    Persiste une liste de winning ads en base de donnees.

    Gere l'upsert: les ads existantes sont mises a jour si le nouveau
    reach est superieur, les nouvelles ads sont inserees.

    Args:
        db: Instance DatabaseManager avec methode get_session()
        winning_ads_data: Liste de dictionnaires contenant:
            - ad: Dict avec les donnees Meta de l'annonce
            - page_id: ID de la page Facebook associee
            - age_days: Age calcule de l'ad
            - matched_criteria: Critere de qualification matche
        search_log_id: ID optionnel du log de recherche pour tracabilite
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Tuple de 3 entiers:
            - total_saved: Nombre total d'ads traitees
            - new_count: Nombre de nouvelles ads inserees
            - updated_count: Nombre d'ads mises a jour (reach ameliore)

    Note:
        Le champ is_new est True pour les nouvelles ads, False pour les updates.
        Cela permet de distinguer les decouvertes recentes dans l'UI.
    """
    scan_time = datetime.utcnow()
    saved = 0
    new_count = 0
    updated_count = 0

    with db.get_session() as session:
        for data in winning_ads_data:
            ad = data.get("ad", {})
            ad_id = str(ad.get("id", ""))
            if not ad_id:
                continue

            page_id = str(data.get("page_id", ""))

            # Verification d'existence pour upsert (filtrer par user_id)
            query = session.query(WinningAds).filter(WinningAds.ad_id == ad_id)
            if user_id is not None:
                query = query.filter(WinningAds.user_id == user_id)
            else:
                query = query.filter(WinningAds.user_id.is_(None))
            existing = query.first()

            # Normalisation du reach
            reach = ad.get("eu_total_reach", 0) or 0
            if isinstance(reach, str):
                try:
                    reach = int(reach)
                except ValueError:
                    reach = 0

            if existing:
                # Update uniquement si le reach a augmente (ad toujours performante)
                if reach > (existing.eu_total_reach or 0):
                    existing.eu_total_reach = reach
                    existing.date_scan = scan_time
                    if search_log_id:
                        existing.search_log_id = search_log_id
                        existing.is_new = False  # Plus une decouverte
                    updated_count += 1
            else:
                # Nouvelle winning ad: insertion complete
                start_time = ad.get("ad_creation_time")
                if isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(
                            start_time.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                    except (ValueError, AttributeError):
                        start_time = None

                winning = WinningAds(
                    user_id=user_id,  # Multi-tenancy
                    ad_id=ad_id,
                    page_id=page_id,
                    page_name=ad.get("page_name", ""),
                    ad_creative_bodies=str(ad.get("ad_creative_bodies", [])),
                    ad_creative_link_captions=str(ad.get("ad_creative_link_captions", [])),
                    ad_creative_link_titles=str(ad.get("ad_creative_link_titles", [])),
                    ad_creation_time=start_time,
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    eu_total_reach=reach,
                    ad_age_days=data.get("age_days", 0),
                    matched_criteria=data.get("matched_criteria", ""),
                    date_scan=scan_time,
                    search_log_id=search_log_id,
                    is_new=True,  # Marqueur de nouvelle decouverte
                )
                session.add(winning)
                new_count += 1

            saved += 1

    return (saved, new_count, updated_count)


def cleanup_duplicate_winning_ads(db) -> int:
    """
    Supprime les doublons de winning ads en conservant l'entree la plus recente.

    Utile apres des imports multiples ou des bugs ayant cree des duplicatas.
    Conserve l'entree avec l'ID le plus eleve (donc la plus recente).

    Args:
        db: Instance DatabaseManager

    Returns:
        Nombre d'enregistrements supprimes
    """
    from sqlalchemy import text

    cleanup_sql = """
    DELETE FROM winning_ads
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM winning_ads
        GROUP BY ad_id
    )
    """

    with db.get_session() as session:
        result = session.execute(text(cleanup_sql))
        deleted = result.rowcount
        session.commit()

    return deleted


def get_winning_ads(
    db,
    limit: int = 100,
    days: int = 30,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere les winning ads les plus recentes, triees par reach decroissant.

    Args:
        db: Instance DatabaseManager
        limit: Nombre maximum de resultats (defaut: 100)
        days: Fenetre temporelle en jours (defaut: 30)
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Liste de dictionnaires avec tous les champs de winning ads
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(WinningAds).filter(
            WinningAds.date_scan >= cutoff
        )
        query = _apply_user_filter(query, WinningAds, user_id)
        ads = query.order_by(
            desc(WinningAds.eu_total_reach)
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "page_id": a.page_id,
                "page_name": a.page_name,
                "ad_creation_time": a.ad_creation_time,
                "ad_age_days": a.ad_age_days,
                "eu_total_reach": a.eu_total_reach,
                "matched_criteria": a.matched_criteria,
                "ad_creative_bodies": a.ad_creative_bodies,
                "ad_creative_link_captions": a.ad_creative_link_captions,
                "ad_creative_link_titles": a.ad_creative_link_titles,
                "ad_snapshot_url": a.ad_snapshot_url,
                "lien_site": a.lien_site,
                "date_scan": a.date_scan,
            }
            for a in ads
        ]


def get_winning_ads_filtered(
    db,
    page_id: str = None,
    ad_id: str = None,
    limit: int = 100,
    days: int = None,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere les winning ads avec filtres de classification.

    Args:
        db: Instance DatabaseManager
        page_id: Filtrer par page (optionnel)
        ad_id: Filtrer par ad_id (optionnel)
        limit: Nombre max de resultats
        days: Filtrer par periode en jours (optionnel)
        thematique: Filtrer par categorie de la page
        subcategory: Filtrer par sous-categorie de la page
        pays: Filtrer par pays de la page
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Liste des winning ads filtrees
    """
    with db.get_session() as session:
        # Si des filtres de classification sont actifs, joindre avec PageRecherche
        if thematique or subcategory or pays:
            query = session.query(WinningAds).join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            )

            if thematique:
                query = query.filter(PageRecherche.thematique == thematique)
            if subcategory:
                query = query.filter(PageRecherche.subcategory == subcategory)
            if pays:
                query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))
        else:
            query = session.query(WinningAds)

        # Appliquer le filtre user_id
        query = _apply_user_filter(query, WinningAds, user_id)

        query = query.order_by(
            WinningAds.date_scan.desc(),
            WinningAds.eu_total_reach.desc()
        )

        if page_id:
            query = query.filter(WinningAds.page_id == page_id)

        if ad_id:
            query = query.filter(WinningAds.ad_id == ad_id)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(WinningAds.date_scan >= cutoff)

        entries = query.limit(limit).all()

        return [
            {
                "id": e.id,
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
                "date_scan": e.date_scan,
            }
            for e in entries
        ]


def get_winning_ads_stats(db, days: int = 30, user_id: Optional[UUID] = None) -> Dict:
    """
    Calcule les statistiques agregees des winning ads.

    Args:
        db: Instance DatabaseManager
        days: Fenetre temporelle en jours
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dictionnaire avec:
            - total: Nombre total de winning ads
            - total_reach: Somme des reach (portee cumulee)
            - avg_reach: Reach moyen par ad
            - unique_pages: Nombre de pages distinctes avec winning ads
            - by_page: Top 10 pages avec le plus de winning ads
            - by_criteria: Repartition par critere de qualification
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        base_filter = [WinningAds.date_scan >= cutoff]
        if user_id is not None:
            base_filter.append(WinningAds.user_id == user_id)

        total = session.query(func.count(WinningAds.id)).filter(
            *base_filter
        ).scalar() or 0

        total_reach = session.query(func.sum(WinningAds.eu_total_reach)).filter(
            *base_filter
        ).scalar() or 0

        avg_reach = session.query(func.avg(WinningAds.eu_total_reach)).filter(
            *base_filter
        ).scalar() or 0

        unique_pages = session.query(
            func.count(func.distinct(WinningAds.page_id))
        ).filter(
            *base_filter
        ).scalar() or 0

        # Top 10 pages avec le plus de winning ads
        by_page = session.query(
            WinningAds.page_id,
            WinningAds.page_name,
            func.count(WinningAds.id).label('count')
        ).filter(
            *base_filter
        ).group_by(
            WinningAds.page_id, WinningAds.page_name
        ).order_by(
            func.count(WinningAds.id).desc()
        ).limit(10).all()

        # Repartition par critere de qualification
        by_criteria = session.query(
            WinningAds.matched_criteria,
            func.count(WinningAds.id).label('count')
        ).filter(
            *base_filter
        ).group_by(
            WinningAds.matched_criteria
        ).all()

        return {
            "total": total,
            "total_reach": int(total_reach),
            "avg_reach": int(avg_reach),
            "unique_pages": unique_pages,
            "by_page": [{"page_id": p[0], "page_name": p[1], "count": p[2]} for p in by_page],
            "by_criteria": {c[0]: c[1] for c in by_criteria if c[0]},
        }


def get_winning_ads_by_page(
    db,
    page_id: str,
    limit: int = 50,
    user_id: Optional[UUID] = None
) -> List[Dict]:
    """
    Recupere toutes les winning ads d'une page specifique.

    Utile pour analyser la performance publicitaire d'un annonceur.

    Args:
        db: Instance DatabaseManager
        page_id: Identifiant Facebook de la page
        limit: Nombre maximum de resultats
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Liste des winning ads de la page, triees par reach decroissant
    """
    with db.get_session() as session:
        query = session.query(WinningAds).filter(
            WinningAds.page_id == str(page_id)
        )
        query = _apply_user_filter(query, WinningAds, user_id)
        ads = query.order_by(
            desc(WinningAds.eu_total_reach)
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "eu_total_reach": a.eu_total_reach,
                "ad_age_days": a.ad_age_days,
                "matched_criteria": a.matched_criteria,
                "ad_snapshot_url": a.ad_snapshot_url,
                "date_scan": a.date_scan,
            }
            for a in ads
        ]


def get_winning_ads_count_by_page(
    db,
    days: int = 30,
    user_id: Optional[UUID] = None
) -> Dict[str, int]:
    """
    Compte les winning ads par page sur une periode donnee.

    Retourne un dictionnaire {page_id: count} pour calculer les scores
    de performance des pages.

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours a considerer
        user_id: UUID de l'utilisateur (multi-tenancy). Si None, donnees partagees.

    Returns:
        Dict mapping page_id vers le nombre de winning ads
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(
            WinningAds.page_id,
            func.count(WinningAds.id).label("count")
        ).filter(
            WinningAds.date_scan >= cutoff
        )
        query = _apply_user_filter(query, WinningAds, user_id)
        results = query.group_by(
            WinningAds.page_id
        ).all()

        return {str(r.page_id): r.count for r in results}


def migrate_matched_criteria_format(db) -> Dict[str, int]:
    """
    Migre le format de matched_criteria de l'ancien format (ex: "5j/23,737")
    vers le nouveau format base sur les seuils (ex: "≤4d & >15k").

    Cette fonction est utile apres la mise a jour du code pour corriger
    les donnees existantes dans la base.

    Args:
        db: Instance DatabaseManager

    Returns:
        Dict avec statistiques de migration:
            - total: Nombre total de winning ads
            - updated: Nombre d'ads mises a jour
            - skipped: Nombre d'ads deja au bon format
    """
    stats = {"total": 0, "updated": 0, "skipped": 0}

    with db.get_session() as session:
        winning_ads = session.query(WinningAds).all()
        stats["total"] = len(winning_ads)

        for ad in winning_ads:
            # Verifier si deja au bon format (contient "≤" et "&")
            current = ad.matched_criteria or ""
            if "≤" in current and "&" in current:
                stats["skipped"] += 1
                continue

            # Recalculer le critere base sur age et reach
            age_days = ad.ad_age_days or 0
            reach = ad.eu_total_reach or 0

            # Trouver le critere correspondant
            new_criteria = None
            for max_age, min_reach in DEFAULT_WINNING_CRITERIA:
                if age_days <= max_age and reach >= min_reach:
                    new_criteria = f"≤{max_age}d & >{min_reach // 1000}k"
                    break

            if new_criteria and new_criteria != current:
                ad.matched_criteria = new_criteria
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

    return stats
