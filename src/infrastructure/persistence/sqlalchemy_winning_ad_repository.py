"""
Adapter SQLAlchemy pour le repository de Winning Ads.

Implemente l'interface WinningAdRepository en utilisant SQLAlchemy
pour la persistence dans PostgreSQL.
"""

from datetime import date, datetime
from typing import Any

from src.application.ports.repositories.winning_ad_repository import WinningAdRepository
from src.domain.entities.winning_ad import WinningAd
from src.domain.value_objects import AdId, PageId, Reach


class SQLAlchemyWinningAdRepository(WinningAdRepository):
    """
    Implementation du WinningAdRepository utilisant SQLAlchemy.

    Cet adapter fait le pont entre les entites du domaine et
    la base de donnees PostgreSQL via le DatabaseManager existant.
    """

    def __init__(self, session: Any, db_manager: Any = None) -> None:
        """
        Initialise le repository.

        Args:
            session: Session SQLAlchemy.
            db_manager: DatabaseManager du module app.database.
        """
        self._session = session
        self._db = db_manager

    def get_by_ad_id(self, ad_id: AdId) -> WinningAd | None:
        """Recupere une winning ad par ID."""
        if not self._db:
            return None
        try:
            # Utiliser la fonction existante de database.py
            from app.database import get_winning_ads_filtered
            ads = get_winning_ads_filtered(self._db, ad_id=str(ad_id), limit=1)
            if ads:
                return self._row_to_winning_ad(ads[0])
        except Exception:
            pass
        return None

    def exists(self, ad_id: AdId) -> bool:
        """Verifie si une winning ad existe."""
        return self.get_by_ad_id(ad_id) is not None

    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "detected_at",
        descending: bool = True,
    ) -> list[WinningAd]:
        """Recupere toutes les winning ads."""
        if not self._db:
            return []
        try:
            from app.database import get_winning_ads
            rows = get_winning_ads(self._db, limit=limit, offset=offset)
            return [self._row_to_winning_ad(r) for r in rows]
        except Exception:
            return []

    def find_by_page(self, page_id: PageId, limit: int = 100) -> list[WinningAd]:
        """Recupere les winning ads d'une page."""
        if not self._db:
            return []
        try:
            from app.database import get_winning_ads_by_page
            rows = get_winning_ads_by_page(self._db, page_id=str(page_id), limit=limit)
            return [self._row_to_winning_ad(r) for r in rows]
        except Exception:
            return []

    def find_by_criteria(self, criteria: str, limit: int = 100) -> list[WinningAd]:
        """Recupere les winning ads par critere."""
        if not self._db:
            return []
        try:
            from app.database import get_winning_ads_filtered
            rows = get_winning_ads_filtered(self._db, critere=criteria, limit=limit)
            return [self._row_to_winning_ad(r) for r in rows]
        except Exception:
            return []

    def find_recent(self, days: int = 7, limit: int = 100) -> list[WinningAd]:
        """Recupere les winning ads recentes."""
        if not self._db:
            return []
        try:
            from app.database import get_winning_ads
            rows = get_winning_ads(self._db, days=days, limit=limit)
            return [self._row_to_winning_ad(r) for r in rows]
        except Exception:
            return []

    def find_by_search_log(self, search_log_id: int, limit: int = 100) -> list[WinningAd]:
        """Recupere les winning ads d'une recherche."""
        if not self._db:
            return []
        try:
            from app.database import get_winning_ads_filtered
            rows = get_winning_ads_filtered(
                self._db, search_log_id=search_log_id, limit=limit
            )
            return [self._row_to_winning_ad(r) for r in rows]
        except Exception:
            return []

    def count(self, filters: dict[str, Any] | None = None) -> int:
        """Compte les winning ads."""
        if not self._db:
            return 0
        try:
            from app.database import get_winning_ads_stats
            stats = get_winning_ads_stats(self._db)
            return stats.get("total", 0)
        except Exception:
            return 0

    def save(self, winning_ad: WinningAd) -> WinningAd:
        """Sauvegarde une winning ad."""
        if not self._db:
            return winning_ad
        try:
            from app.database import save_winning_ads
            ads_data = [{
                "ad_id": str(winning_ad.ad_id),
                "page_id": str(winning_ad.page_id),
                "page_name": winning_ad.page_name,
                "ad_url": winning_ad.ad_url,
                "reach_lower": winning_ad.reach.lower if winning_ad.reach else 0,
                "reach_upper": winning_ad.reach.upper if winning_ad.reach else 0,
                "duration_days": winning_ad.duration_days,
                "critere": winning_ad.criteria,
                "first_seen": winning_ad.first_seen.isoformat() if winning_ad.first_seen else None,
                "last_seen": winning_ad.last_seen.isoformat() if winning_ad.last_seen else None,
            }]
            save_winning_ads(self._db, ads_data)
        except Exception:
            pass
        return winning_ad

    def save_many(self, winning_ads: list[WinningAd]) -> tuple:
        """Sauvegarde plusieurs winning ads."""
        if not self._db or not winning_ads:
            return (0, 0)
        saved = 0
        for ad in winning_ads:
            try:
                self.save(ad)
                saved += 1
            except Exception:
                pass
        return (saved, len(winning_ads) - saved)

    def delete(self, ad_id: AdId) -> bool:
        """Supprime une winning ad."""
        # Non implemente dans le DatabaseManager actuel
        return False

    def delete_older_than(self, days: int) -> int:
        """Supprime les winning ads anciennes."""
        # Non implemente dans le DatabaseManager actuel
        return 0

    def get_statistics(self) -> dict[str, Any]:
        """Recupere les statistiques."""
        if not self._db:
            return {}
        try:
            from app.database import get_winning_ads_stats
            return get_winning_ads_stats(self._db)
        except Exception:
            return {}

    def get_criteria_distribution(self) -> dict[str, int]:
        """Distribution par critere."""
        if not self._db:
            return {}
        try:
            stats = self.get_statistics()
            return stats.get("by_critere", {})
        except Exception:
            return {}

    def get_daily_counts(self, days: int = 30) -> dict[date, int]:
        """Comptes journaliers."""
        if not self._db:
            return {}
        try:
            stats = self.get_statistics()
            daily = stats.get("daily", {})
            # Convertir les strings en dates
            result = {}
            for date_str, count in daily.items():
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    result[d] = count
                except (ValueError, TypeError):
                    pass
            return result
        except Exception:
            return {}

    def _row_to_winning_ad(self, row: Any) -> WinningAd:
        """Convertit une ligne DB en entite WinningAd."""
        # Gerer dict ou objet
        if isinstance(row, dict):
            get = row.get
        else:
            get = lambda k, d=None: getattr(row, k, d)

        ad_id = get("ad_id", "")
        page_id = get("page_id", "")
        reach_lower = get("reach_lower", 0) or 0
        reach_upper = get("reach_upper", 0) or 0

        return WinningAd(
            ad_id=AdId(str(ad_id)),
            page_id=PageId(str(page_id)),
            page_name=get("page_name", ""),
            ad_url=get("ad_url", ""),
            reach=Reach(value=reach_lower, lower_bound=reach_lower, upper_bound=reach_upper),
            duration_days=get("duration_days", 0) or 0,
            criteria=get("critere", ""),
            detected_at=get("detected_at") or datetime.utcnow(),
            first_seen=get("first_seen"),
            last_seen=get("last_seen"),
            search_log_id=get("search_log_id"),
        )
