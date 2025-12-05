"""
Module pour le tracking des appels API
Centralise le monitoring de tous les appels Meta API, ScraperAPI et requêtes web
"""
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class APICall:
    """Représente un appel API"""
    api_type: str  # meta_api, scraper_api, web_request
    endpoint: str
    method: str = "GET"
    keyword: str = ""
    page_id: str = ""
    site_url: str = ""
    status_code: int = 0
    success: bool = True
    error_type: str = ""
    error_message: str = ""
    response_time_ms: float = 0
    response_size: int = 0
    items_returned: int = 0
    called_at: datetime = field(default_factory=datetime.utcnow)


class APITracker:
    """
    Tracker centralisé pour tous les appels API.
    Thread-safe pour supporter le multithreading.
    """

    # Coût par requête ScraperAPI (en $)
    SCRAPER_API_COST_PER_REQUEST = 0.0005  # ~$0.50 pour 1000 requêtes

    def __init__(self, search_log_id: int = None, db=None):
        """
        Args:
            search_log_id: ID du SearchLog associé (optionnel)
            db: DatabaseManager pour sauvegarder les appels (optionnel)
        """
        self.search_log_id = search_log_id
        self.db = db
        self.calls: List[APICall] = []
        self._lock = Lock()

        # Compteurs agrégés
        self._meta_api_calls = 0
        self._meta_api_errors = 0
        self._meta_api_times: List[float] = []

        self._scraper_api_calls = 0
        self._scraper_api_errors = 0
        self._scraper_api_times: List[float] = []

        self._web_requests = 0
        self._web_errors = 0
        self._web_times: List[float] = []

        self._rate_limit_hits = 0

        # Détails par mot-clé
        self._keyword_stats: Dict[str, Dict] = {}

    def track_meta_api_call(
        self,
        endpoint: str,
        keyword: str = "",
        status_code: int = 200,
        success: bool = True,
        error_type: str = "",
        error_message: str = "",
        response_time_ms: float = 0,
        items_returned: int = 0,
        response_size: int = 0
    ):
        """Track un appel à l'API Meta"""
        with self._lock:
            self._meta_api_calls += 1
            if not success:
                self._meta_api_errors += 1
            if error_type == "rate_limit":
                self._rate_limit_hits += 1
            self._meta_api_times.append(response_time_ms)

            # Stats par mot-clé
            if keyword:
                if keyword not in self._keyword_stats:
                    self._keyword_stats[keyword] = {
                        "calls": 0, "ads_found": 0, "errors": 0, "time_ms": 0
                    }
                self._keyword_stats[keyword]["calls"] += 1
                self._keyword_stats[keyword]["ads_found"] += items_returned
                self._keyword_stats[keyword]["time_ms"] += response_time_ms
                if not success:
                    self._keyword_stats[keyword]["errors"] += 1

            call = APICall(
                api_type="meta_api",
                endpoint=endpoint,
                keyword=keyword,
                status_code=status_code,
                success=success,
                error_type=error_type,
                error_message=error_message,
                response_time_ms=response_time_ms,
                items_returned=items_returned,
                response_size=response_size
            )
            self.calls.append(call)

    def track_scraper_api_call(
        self,
        url: str,
        site_url: str = "",
        status_code: int = 200,
        success: bool = True,
        error_type: str = "",
        error_message: str = "",
        response_time_ms: float = 0,
        response_size: int = 0
    ):
        """Track un appel via ScraperAPI"""
        with self._lock:
            self._scraper_api_calls += 1
            if not success:
                self._scraper_api_errors += 1
            self._scraper_api_times.append(response_time_ms)

            call = APICall(
                api_type="scraper_api",
                endpoint=url,
                site_url=site_url,
                status_code=status_code,
                success=success,
                error_type=error_type,
                error_message=error_message,
                response_time_ms=response_time_ms,
                response_size=response_size
            )
            self.calls.append(call)

    def track_web_request(
        self,
        url: str,
        site_url: str = "",
        page_id: str = "",
        status_code: int = 200,
        success: bool = True,
        error_type: str = "",
        error_message: str = "",
        response_time_ms: float = 0,
        response_size: int = 0,
        items_returned: int = 0
    ):
        """Track une requête web directe (sans proxy)"""
        with self._lock:
            self._web_requests += 1
            if not success:
                self._web_errors += 1
            self._web_times.append(response_time_ms)

            call = APICall(
                api_type="web_request",
                endpoint=url,
                site_url=site_url,
                page_id=page_id,
                status_code=status_code,
                success=success,
                error_type=error_type,
                error_message=error_message,
                response_time_ms=response_time_ms,
                response_size=response_size,
                items_returned=items_returned
            )
            self.calls.append(call)

    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des statistiques"""
        with self._lock:
            return {
                # Compteurs
                "meta_api_calls": self._meta_api_calls,
                "scraper_api_calls": self._scraper_api_calls,
                "web_requests": self._web_requests,
                "total_calls": self._meta_api_calls + self._scraper_api_calls + self._web_requests,

                # Erreurs
                "meta_api_errors": self._meta_api_errors,
                "scraper_api_errors": self._scraper_api_errors,
                "web_errors": self._web_errors,
                "rate_limit_hits": self._rate_limit_hits,

                # Temps moyens
                "meta_api_avg_time": sum(self._meta_api_times) / len(self._meta_api_times) if self._meta_api_times else 0,
                "scraper_api_avg_time": sum(self._scraper_api_times) / len(self._scraper_api_times) if self._scraper_api_times else 0,
                "web_avg_time": sum(self._web_times) / len(self._web_times) if self._web_times else 0,

                # Coût
                "scraper_api_cost": self._scraper_api_calls * self.SCRAPER_API_COST_PER_REQUEST,

                # Détails par mot-clé
                "keyword_stats": dict(self._keyword_stats)
            }

    def get_api_metrics_for_log(self) -> Dict[str, Any]:
        """Retourne les métriques formatées pour SearchLog"""
        summary = self.get_summary()
        return {
            "meta_api_calls": summary["meta_api_calls"],
            "scraper_api_calls": summary["scraper_api_calls"],
            "web_requests": summary["web_requests"],
            "meta_api_errors": summary["meta_api_errors"],
            "scraper_api_errors": summary["scraper_api_errors"],
            "web_errors": summary["web_errors"],
            "rate_limit_hits": summary["rate_limit_hits"],
            "meta_api_avg_time": round(summary["meta_api_avg_time"], 2),
            "scraper_api_avg_time": round(summary["scraper_api_avg_time"], 2),
            "web_avg_time": round(summary["web_avg_time"], 2),
            "scraper_api_cost": round(summary["scraper_api_cost"], 4),
            "api_details": summary["keyword_stats"]
        }

    def save_calls_to_db(self):
        """Sauvegarde tous les appels en base de données"""
        if not self.db or not self.search_log_id:
            return

        try:
            from app.database import save_api_calls
            save_api_calls(self.db, self.search_log_id, self.calls)
        except Exception as e:
            print(f"Erreur sauvegarde API calls: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TRACKER GLOBAL (singleton-like pour la session courante)
# ═══════════════════════════════════════════════════════════════════════════════

_current_tracker: Optional[APITracker] = None


def get_current_tracker() -> Optional[APITracker]:
    """Retourne le tracker courant"""
    global _current_tracker
    return _current_tracker


def set_current_tracker(tracker: APITracker):
    """Définit le tracker courant"""
    global _current_tracker
    _current_tracker = tracker


def clear_current_tracker():
    """Efface le tracker courant"""
    global _current_tracker
    _current_tracker = None


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCORATEUR POUR TRACKING AUTOMATIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def track_api_call(api_type: str, get_keyword=None, get_url=None):
    """
    Décorateur pour tracker automatiquement les appels API

    Args:
        api_type: Type d'API (meta_api, scraper_api, web_request)
        get_keyword: Fonction pour extraire le mot-clé des args
        get_url: Fonction pour extraire l'URL des args
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracker = get_current_tracker()
            start_time = time.time()

            keyword = get_keyword(*args, **kwargs) if get_keyword else ""
            url = get_url(*args, **kwargs) if get_url else ""

            try:
                result = func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000

                if tracker:
                    if api_type == "meta_api":
                        items = len(result) if isinstance(result, list) else 0
                        tracker.track_meta_api_call(
                            endpoint="ads_archive",
                            keyword=keyword,
                            success=True,
                            response_time_ms=response_time,
                            items_returned=items
                        )
                    elif api_type == "scraper_api":
                        tracker.track_scraper_api_call(
                            url=url,
                            success=True,
                            response_time_ms=response_time
                        )
                    elif api_type == "web_request":
                        tracker.track_web_request(
                            url=url,
                            success=True,
                            response_time_ms=response_time
                        )

                return result

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                error_type = "rate_limit" if "613" in str(e) or "rate limit" in str(e).lower() else "error"

                if tracker:
                    if api_type == "meta_api":
                        tracker.track_meta_api_call(
                            endpoint="ads_archive",
                            keyword=keyword,
                            success=False,
                            error_type=error_type,
                            error_message=str(e)[:200],
                            response_time_ms=response_time
                        )
                    elif api_type == "scraper_api":
                        tracker.track_scraper_api_call(
                            url=url,
                            success=False,
                            error_type=error_type,
                            error_message=str(e)[:200],
                            response_time_ms=response_time
                        )
                    elif api_type == "web_request":
                        tracker.track_web_request(
                            url=url,
                            success=False,
                            error_type=error_type,
                            error_message=str(e)[:200],
                            response_time_ms=response_time
                        )
                raise

        return wrapper
    return decorator
