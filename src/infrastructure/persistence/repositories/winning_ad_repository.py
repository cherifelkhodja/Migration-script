"""
Repository pour les winning ads.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.dialects.postgresql import insert

from src.infrastructure.persistence.models import WinningAds, PageRecherche


def is_winning_ad(ad: Dict, scan_date: datetime, criteria: List = None) -> Tuple[bool, int, int, str]:
    """
    Verifie si une annonce est une winning ad basee sur reach + age.
    
    Returns:
        Tuple (is_winning, age_days, reach, matched_criteria_str)
    """
    if criteria is None:
        criteria = [
            (4, 15000), (5, 20000), (6, 30000), (7, 40000),
            (8, 50000), (9, 60000), (10, 75000), (11, 85000),
            (12, 100000), (13, 120000), (14, 140000), (15, 160000),
            (20, 250000), (25, 350000), (30, 500000)
        ]

    start_str = ad.get("ad_delivery_start_time", "")
    if not start_str:
        return (False, 0, 0, "")

    try:
        if isinstance(start_str, str):
            start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        else:
            start_date = start_str
        start_date = start_date.replace(tzinfo=None)
    except Exception:
        return (False, 0, 0, "")

    age_days = (scan_date - start_date).days
    if age_days < 0:
        age_days = 0

    reach = ad.get("eu_total_reach", 0) or 0
    if isinstance(reach, str):
        try:
            reach = int(reach)
        except ValueError:
            reach = 0

    for max_age, min_reach in criteria:
        if age_days <= max_age and reach >= min_reach:
            return (True, age_days, reach, f"{age_days}j/{reach:,}")

    return (False, age_days, reach, "")


def save_winning_ads(
    db,
    winning_ads_data: List[Dict],
    search_log_id: int = None
) -> Tuple[int, int, int]:
    """
    Sauvegarde les winning ads.
    
    Returns:
        Tuple (total_saved, new_count, updated_count)
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

            existing = session.query(WinningAds).filter(
                WinningAds.ad_id == ad_id
            ).first()

            reach = ad.get("eu_total_reach", 0) or 0
            if isinstance(reach, str):
                try:
                    reach = int(reach)
                except ValueError:
                    reach = 0

            if existing:
                if reach > (existing.eu_total_reach or 0):
                    existing.eu_total_reach = reach
                    existing.date_scan = scan_time
                    if search_log_id:
                        existing.search_log_id = search_log_id
                        existing.is_new = False
                    updated_count += 1
            else:
                start_time = ad.get("ad_delivery_start_time")
                if isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        start_time = None

                winning = WinningAds(
                    ad_id=ad_id,
                    page_id=page_id,
                    page_name=ad.get("page_name", ""),
                    ad_creative_bodies=str(ad.get("ad_creative_bodies", [])),
                    ad_creative_link_captions=str(ad.get("ad_creative_link_captions", [])),
                    ad_creative_link_titles=str(ad.get("ad_creative_link_titles", [])),
                    ad_delivery_start_time=start_time,
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    eu_total_reach=reach,
                    age_days=data.get("age_days", 0),
                    matched_criteria=data.get("matched_criteria", ""),
                    date_scan=scan_time,
                    search_log_id=search_log_id,
                    is_new=True,
                )
                session.add(winning)
                new_count += 1

            saved += 1

    return (saved, new_count, updated_count)


def cleanup_duplicate_winning_ads(db) -> int:
    """Supprime les doublons de winning ads."""
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


def get_winning_ads(db, limit: int = 100, days: int = 30) -> List[Dict]:
    """Recupere les winning ads recentes."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        ads = session.query(WinningAds).filter(
            WinningAds.date_scan >= cutoff
        ).order_by(
            desc(WinningAds.eu_total_reach)
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "page_id": a.page_id,
                "page_name": a.page_name,
                "eu_total_reach": a.eu_total_reach,
                "age_days": a.age_days,
                "matched_criteria": a.matched_criteria,
                "ad_snapshot_url": a.ad_snapshot_url,
                "date_scan": a.date_scan,
            }
            for a in ads
        ]


def get_winning_ads_filtered(
    db,
    limit: int = 100,
    days: int = 30,
    min_reach: int = None,
    cms_filter: List[str] = None,
    category_filter: str = None
) -> List[Dict]:
    """Recupere les winning ads avec filtres."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(WinningAds).filter(
            WinningAds.date_scan >= cutoff
        )

        if min_reach:
            query = query.filter(WinningAds.eu_total_reach >= min_reach)

        if cms_filter or category_filter:
            query = query.join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            )
            if cms_filter:
                query = query.filter(PageRecherche.cms.in_(cms_filter))
            if category_filter:
                query = query.filter(PageRecherche.thematique == category_filter)

        ads = query.order_by(
            desc(WinningAds.eu_total_reach)
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "page_id": a.page_id,
                "page_name": a.page_name,
                "eu_total_reach": a.eu_total_reach,
                "age_days": a.age_days,
                "matched_criteria": a.matched_criteria,
                "ad_snapshot_url": a.ad_snapshot_url,
                "date_scan": a.date_scan,
            }
            for a in ads
        ]


def get_winning_ads_stats(db, days: int = 30) -> Dict:
    """Statistiques des winning ads."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        total = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan >= cutoff
        ).scalar() or 0

        total_reach = session.query(func.sum(WinningAds.eu_total_reach)).filter(
            WinningAds.date_scan >= cutoff
        ).scalar() or 0

        avg_reach = session.query(func.avg(WinningAds.eu_total_reach)).filter(
            WinningAds.date_scan >= cutoff
        ).scalar() or 0

        unique_pages = session.query(func.count(func.distinct(WinningAds.page_id))).filter(
            WinningAds.date_scan >= cutoff
        ).scalar() or 0

        return {
            "total": total,
            "total_reach": int(total_reach),
            "avg_reach": int(avg_reach),
            "unique_pages": unique_pages,
        }


def get_winning_ads_by_page(db, page_id: str, limit: int = 50) -> List[Dict]:
    """Recupere les winning ads d'une page."""
    with db.get_session() as session:
        ads = session.query(WinningAds).filter(
            WinningAds.page_id == str(page_id)
        ).order_by(
            desc(WinningAds.eu_total_reach)
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "ad_id": a.ad_id,
                "eu_total_reach": a.eu_total_reach,
                "age_days": a.age_days,
                "matched_criteria": a.matched_criteria,
                "ad_snapshot_url": a.ad_snapshot_url,
                "date_scan": a.date_scan,
            }
            for a in ads
        ]
