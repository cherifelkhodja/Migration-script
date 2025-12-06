"""
Module pour l'interaction avec l'API Meta Ads Archive
"""
import json
import time
import re
import requests
from collections import Counter
from typing import List, Dict, Tuple, Optional, Callable
from threading import Lock

# Supprimer les warnings SSL pour Railway
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from app.config import (
        ADS_ARCHIVE, TIMEOUT, LIMIT_SEARCH, LIMIT_COUNT, LIMIT_MIN,
        FIELDS_ADS_COMPLETE,
        META_DELAY_BETWEEN_PAGES, META_DELAY_ON_ERROR
    )
    from app.api_tracker import get_current_tracker
except ImportError:
    from config import (
        ADS_ARCHIVE, TIMEOUT, LIMIT_SEARCH, LIMIT_COUNT, LIMIT_MIN,
        FIELDS_ADS_COMPLETE
    )
    META_DELAY_BETWEEN_PAGES = 0.3
    META_DELAY_ON_ERROR = 2.0
    try:
        from api_tracker import get_current_tracker
    except ImportError:
        def get_current_tracker():
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN ROTATOR - Gestion de plusieurs tokens Meta API
# ═══════════════════════════════════════════════════════════════════════════════

class TokenRotator:
    """
    Gère la rotation entre plusieurs tokens Meta API avec leurs proxies.
    - Chaque token a son proxy associé
    - Un token fait toute la pagination d'une recherche
    - Rotation entre les recherches (keywords)
    Thread-safe.
    """

    def __init__(self, tokens_with_proxies: List[Dict] = None, tokens: List[str] = None, db=None):
        """
        Args:
            tokens_with_proxies: Liste de dicts [{"id": 1, "token": "...", "proxy": "http://...", "name": "..."}]
            tokens: Liste de tokens (fallback si tokens_with_proxies non fourni)
            db: DatabaseManager pour enregistrer les stats (optionnel)
        """
        self._lock = Lock()
        self._db = db

        # Initialiser les tokens avec proxies et IDs
        if tokens_with_proxies:
            self._token_data = [
                {
                    "id": t.get("id"),  # ID depuis la base de données
                    "token": t["token"].strip(),
                    "proxy": t.get("proxy") or None,
                    "name": t.get("name", f"Token #{i+1}")
                }
                for i, t in enumerate(tokens_with_proxies)
                if t.get("token") and t["token"].strip()
            ]
        elif tokens:
            # Fallback: tokens sans proxies ni IDs
            self._token_data = [
                {"id": None, "token": t.strip(), "proxy": None, "name": f"Token #{i+1}"}
                for i, t in enumerate(tokens)
                if t and t.strip()
            ]
        else:
            self._token_data = []

        self._current_index = 0
        self._rate_limited = {}  # {token: timestamp_until_available}
        self._call_counts = {t["token"]: 0 for t in self._token_data}

    @property
    def token_count(self) -> int:
        """Nombre de tokens disponibles"""
        return len(self._token_data)

    @property
    def tokens(self) -> List[str]:
        """Liste des tokens (pour compatibilité)"""
        return [t["token"] for t in self._token_data]

    def get_current_token(self) -> str:
        """Retourne le token courant"""
        with self._lock:
            if not self._token_data:
                return ""
            return self._token_data[self._current_index]["token"]

    def get_current_proxy(self) -> Optional[str]:
        """Retourne le proxy associé au token courant"""
        with self._lock:
            if not self._token_data:
                return None
            return self._token_data[self._current_index].get("proxy")

    def get_current_token_id(self) -> Optional[int]:
        """Retourne l'ID du token courant (depuis la base de données)"""
        with self._lock:
            if not self._token_data:
                return None
            return self._token_data[self._current_index].get("id")

    def get_current_token_name(self) -> str:
        """Retourne le nom du token courant"""
        with self._lock:
            if not self._token_data:
                return "Unknown"
            return self._token_data[self._current_index].get("name", "Unknown")

    def get_current_token_full_info(self) -> Dict:
        """Retourne toutes les infos du token courant (id, token, proxy, name)"""
        with self._lock:
            if not self._token_data:
                return {"id": None, "token": "", "proxy": None, "name": "Unknown"}
            return self._token_data[self._current_index].copy()

    def get_current_token_and_proxy(self) -> Tuple[str, Optional[str]]:
        """Retourne le token et son proxy"""
        with self._lock:
            if not self._token_data:
                return "", None
            data = self._token_data[self._current_index]
            return data["token"], data.get("proxy")

    def get_token_info(self) -> Dict:
        """Retourne les infos sur l'état des tokens"""
        with self._lock:
            now = time.time()
            current_data = self._token_data[self._current_index] if self._token_data else {}
            return {
                "total_tokens": len(self._token_data),
                "current_index": self._current_index + 1,
                "current_token_masked": self._mask_token(current_data.get("token", "")),
                "current_proxy": current_data.get("proxy", "Aucun"),
                "current_name": current_data.get("name", ""),
                "call_counts": {
                    self._mask_token(t["token"]): self._call_counts.get(t["token"], 0)
                    for t in self._token_data
                },
                "rate_limited": {
                    self._mask_token(t): round(ts - now, 1)
                    for t, ts in self._rate_limited.items()
                    if ts > now
                }
            }

    def _mask_token(self, token: str) -> str:
        """Masque un token pour l'affichage"""
        if not token or len(token) <= 10:
            return "***"
        return f"{token[:6]}...{token[-4:]}"

    def rotate_to_next(self, reason: str = "new_search") -> bool:
        """
        Passe au prochain token disponible (non rate-limited).
        Appelé entre les recherches (keywords), pas pendant la pagination.

        Returns:
            True si rotation effectuée, False si un seul token ou tous rate-limited
        """
        with self._lock:
            if len(self._token_data) <= 1:
                return False

            now = time.time()
            old_idx = self._current_index

            # Chercher le prochain token non rate-limited
            for i in range(1, len(self._token_data) + 1):
                next_idx = (self._current_index + i) % len(self._token_data)
                next_token = self._token_data[next_idx]["token"]
                if next_token not in self._rate_limited or self._rate_limited[next_token] <= now:
                    self._current_index = next_idx
                    new_name = self._token_data[next_idx].get("name", f"#{next_idx + 1}")
                    print(f"🔄 Token rotation ({reason}): #{old_idx + 1} → #{next_idx + 1} ({new_name})")
                    return True

            print("⚠️ Tous les tokens sont rate-limited, conserve le token actuel")
            return False

    def rotate(self, reason: str = "manual") -> bool:
        """Alias pour rotate_to_next (compatibilité)"""
        return self.rotate_to_next(reason)

    def get_tokens_with_proxies(self) -> List[Dict]:
        """
        Retourne la liste des tokens qui ont un proxy configuré.
        Utilisé pour déterminer le niveau de parallélisation possible.
        """
        with self._lock:
            return [t for t in self._token_data if t.get("proxy")]

    def has_proxy_tokens(self) -> bool:
        """Vérifie si au moins un token a un proxy configuré"""
        with self._lock:
            return any(t.get("proxy") for t in self._token_data)

    def get_parallel_workers_count(self) -> int:
        """
        Retourne le nombre de workers parallèles possibles.
        - Si des tokens ont des proxies: nombre de tokens avec proxy
        - Sinon: 1 (séquentiel)
        """
        with self._lock:
            proxied_count = sum(1 for t in self._token_data if t.get("proxy"))
            return max(1, proxied_count)

    def get_token_data_at_index(self, index: int) -> Dict:
        """
        Retourne les données d'un token à un index spécifique.
        Utilisé pour assigner un token dédié à chaque worker parallèle.
        """
        with self._lock:
            if not self._token_data:
                return {"id": None, "token": "", "proxy": None, "name": "Unknown"}
            # Wrap around si index dépasse
            safe_index = index % len(self._token_data)
            return self._token_data[safe_index].copy()

    def get_all_token_data(self) -> List[Dict]:
        """Retourne une copie de toutes les données de tokens"""
        with self._lock:
            return [t.copy() for t in self._token_data]

    def mark_rate_limited(self, cooldown_seconds: int = 60, error_message: str = None) -> bool:
        """
        Marque le token courant comme rate-limited et tourne.

        Args:
            cooldown_seconds: Temps avant que le token soit réutilisable
            error_message: Message d'erreur à enregistrer

        Returns:
            True si un autre token est disponible
        """
        with self._lock:
            if not self._token_data:
                return False

            current = self._token_data[self._current_index]["token"]
            self._rate_limited[current] = time.time() + cooldown_seconds

            # Enregistrer en BDD
            self._record_to_db(current, success=False, is_rate_limit=True,
                              error_message=error_message, rate_limit_seconds=cooldown_seconds)

            # Chercher un token non rate-limited
            now = time.time()
            for i in range(1, len(self._token_data) + 1):
                idx = (self._current_index + i) % len(self._token_data)
                token = self._token_data[idx]["token"]
                if token not in self._rate_limited or self._rate_limited[token] <= now:
                    old_idx = self._current_index
                    self._current_index = idx
                    new_name = self._token_data[idx].get("name", f"#{idx + 1}")
                    print(f"🔄 Token #{old_idx + 1} rate-limited, switch vers #{idx + 1} ({new_name})")
                    return True

            # Tous les tokens sont rate-limited
            print("⚠️ Tous les tokens sont rate-limited!")
            return False

    def record_call(self, success: bool = True, error_message: str = None):
        """
        Enregistre un appel pour le token courant.
        NE FAIT PAS de rotation - le même token doit faire toute la pagination.

        Args:
            success: Si l'appel a réussi
            error_message: Message d'erreur éventuel
        """
        with self._lock:
            if not self._token_data:
                return

            token = self._token_data[self._current_index]["token"]
            self._call_counts[token] = self._call_counts.get(token, 0) + 1

            # Enregistrer en BDD (seulement succès, les erreurs sont gérées par mark_rate_limited)
            if success:
                self._record_to_db(token, success=True)

    def _record_to_db(self, token: str, success: bool = True, is_rate_limit: bool = False,
                      error_message: str = None, rate_limit_seconds: int = 60):
        """Enregistre l'utilisation d'un token en base de données"""
        if not self._db:
            return
        try:
            from app.database import record_token_usage
            record_token_usage(
                self._db,
                token=token,
                success=success,
                error_message=error_message,
                is_rate_limit=is_rate_limit,
                rate_limit_seconds=rate_limit_seconds
            )
        except Exception as e:
            print(f"Erreur enregistrement token usage: {e}")


# Singleton global pour le rotator
_token_rotator: Optional[TokenRotator] = None
_token_db = None  # DatabaseManager pour les stats


def get_token_rotator() -> Optional[TokenRotator]:
    """Retourne le rotator global"""
    global _token_rotator
    return _token_rotator


def init_token_rotator(tokens: List[str] = None, tokens_with_proxies: List[Dict] = None, db=None) -> TokenRotator:
    """
    Initialise le rotator global avec les tokens.

    Args:
        tokens: Liste simple de tokens (sans proxy)
        tokens_with_proxies: Liste de dicts [{"token": "...", "proxy": "http://...", "name": "..."}]
        db: DatabaseManager pour les stats
    """
    global _token_rotator, _token_db
    _token_db = db

    if tokens_with_proxies:
        _token_rotator = TokenRotator(tokens_with_proxies=tokens_with_proxies, db=db)
        print(f"✅ TokenRotator initialisé avec {_token_rotator.token_count} token(s) + proxies")
    else:
        _token_rotator = TokenRotator(tokens=tokens or [], db=db)
        print(f"✅ TokenRotator initialisé avec {_token_rotator.token_count} token(s)")

    return _token_rotator


def clear_token_rotator():
    """Efface le rotator global"""
    global _token_rotator, _token_db
    _token_rotator = None
    _token_db = None


class MetaAdsClient:
    """Client pour interagir avec l'API Meta Ads Archive"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._current_keyword = ""  # Pour tracking

    def _get_current_token(self) -> str:
        """Retourne le token à utiliser (du rotator si disponible)"""
        rotator = get_token_rotator()
        if rotator and rotator.token_count > 0:
            return rotator.get_current_token()
        return self.access_token

    def _get_api(self, url: str, params: dict) -> dict:
        """Appel API avec retry automatique, gestion du rate limiting et proxy"""
        params = params.copy()

        tracker = get_current_tracker()
        rotator = get_token_rotator()
        max_retries = 5

        for attempt in range(max_retries):
            # Utiliser le token et proxy du rotator si disponible
            current_token = self._get_current_token()
            params["access_token"] = current_token

            # Récupérer le proxy associé au token (si configuré)
            # NOTE: ScraperAPI ne doit PAS être utilisé pour Meta API (interdit)
            # ScraperAPI est uniquement pour le scraping web (sites e-commerce)
            proxies = None
            proxy_url = None
            if rotator:
                proxy_url = rotator.get_current_proxy()

            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}

            start_time = time.time()
            try:
                # verify=False pour éviter les erreurs SSL sur Railway
                r = requests.get(url, params=params, timeout=TIMEOUT, proxies=proxies, verify=False)
                response_time = (time.time() - start_time) * 1000

                # Parse response
                try:
                    data = r.json()
                except (ValueError, json.JSONDecodeError):
                    data = {}

                response_size = len(r.text) if r.text else 0

                # Check for rate limit error in JSON response (code 613)
                if "error" in data:
                    error_code = data["error"].get("code")
                    error_msg = data["error"].get("message", "")

                    if error_code == 613 or "rate limit" in error_msg.lower():
                        # Track rate limit hit
                        if tracker:
                            tracker.track_meta_api_call(
                                endpoint=url[:200],
                                keyword=self._current_keyword,
                                status_code=r.status_code,
                                success=False,
                                error_type="rate_limit",
                                error_message=error_msg[:200],
                                response_time_ms=response_time
                            )

                        # Essayer de switcher de token si possible
                        if rotator and rotator.token_count > 1:
                            switched = rotator.mark_rate_limited(cooldown_seconds=60, error_message=error_msg)
                            if switched:
                                # Retry immédiatement avec le nouveau token
                                continue

                        # Rate limit - exponential backoff
                        sleep_time = min(2 ** attempt, 60)  # Max 60s
                        print(f"⏳ Rate limit atteint, attente {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue

                    # Track other API error
                    if tracker:
                        tracker.track_meta_api_call(
                            endpoint=url[:200],
                            keyword=self._current_keyword,
                            status_code=r.status_code,
                            success=False,
                            error_type="api_error",
                            error_message=error_msg[:200],
                            response_time_ms=response_time
                        )

                    # Other API error
                    raise RuntimeError(f"API Error {error_code}: {error_msg}")

                if r.status_code == 200:
                    # Track successful call
                    items_count = len(data.get("data", []))
                    if tracker:
                        tracker.track_meta_api_call(
                            endpoint=url[:200],
                            keyword=self._current_keyword,
                            status_code=200,
                            success=True,
                            response_time_ms=response_time,
                            response_size=response_size,
                            items_returned=items_count
                        )
                    # Enregistrer le succès dans le rotator
                    if rotator:
                        rotator.record_call(success=True)
                    return data

                if r.status_code in (429, 500, 502, 503):
                    if tracker:
                        tracker.track_meta_api_call(
                            endpoint=url[:200],
                            keyword=self._current_keyword,
                            status_code=r.status_code,
                            success=False,
                            error_type="http_error",
                            response_time_ms=response_time
                        )
                    sleep_time = min(2 ** attempt, 30)
                    time.sleep(sleep_time)
                    continue

                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

            except requests.RequestException as e:
                response_time = (time.time() - start_time) * 1000
                if tracker:
                    tracker.track_meta_api_call(
                        endpoint=url[:200],
                        keyword=self._current_keyword,
                        success=False,
                        error_type="network_error",
                        error_message=str(e)[:200],
                        response_time_ms=response_time
                    )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Erreur réseau: {e}")

        raise RuntimeError("Échec après plusieurs tentatives (rate limit)")

    def search_ads(
        self,
        keyword: str,
        countries: List[str],
        languages: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[dict]:
        """
        Recherche des annonces par mot-clé

        Args:
            keyword: Mot-clé à rechercher
            countries: Liste des codes pays
            languages: Liste des codes langues
            progress_callback: Fonction callback pour la progression (current, total)

        Returns:
            Liste des annonces trouvées
        """
        # Set current keyword for API tracking
        self._current_keyword = keyword

        # Capture du token utilisé pour le logging
        rotator = get_token_rotator()
        token_id = rotator.get_current_token_id() if rotator else None
        token_name = rotator.get_current_token_name() if rotator else "Default"
        start_time = time.time()
        error_msg = None
        success = True

        url = ADS_ARCHIVE
        params = {
            "search_terms": keyword,
            "search_type": "KEYWORD_UNORDERED",
            "ad_type": "ALL",
            "ad_active_status": "ACTIVE",
            "ad_reached_countries": json.dumps(countries),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_SEARCH
        }
        # N'inclure languages que si une liste non vide est fournie
        if languages:
            params["languages"] = json.dumps(languages)

        all_ads = []
        limit_curr = LIMIT_SEARCH

        while True:
            try:
                data = self._get_api(url, params)
            except RuntimeError as e:
                err_msg = str(e)
                error_msg = err_msg
                success = False
                # Log l'erreur pour diagnostic
                print(f"❌ Erreur API Meta pour '{keyword}': {err_msg}")

                # Réduire la limite si demandé par l'API
                if ("reduce" in err_msg or "code\":1" in err_msg) and limit_curr > LIMIT_MIN:
                    limit_curr = max(LIMIT_MIN, limit_curr // 2)
                    params["limit"] = limit_curr
                    time.sleep(0.3)
                    continue

                # Erreur OAuth/Token expiré
                if "OAuth" in err_msg or "token" in err_msg.lower() or "expired" in err_msg.lower():
                    print(f"🔑 Token invalide ou expiré! Vérifiez vos tokens Meta API dans Settings.")

                break

            batch = data.get("data", [])
            all_ads.extend(batch)

            if progress_callback:
                progress_callback(len(all_ads), -1)

            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break

            # Délai entre les pages pour éviter rate limit
            time.sleep(META_DELAY_BETWEEN_PAGES)

            url = next_url
            params = {}

        # Log de l'utilisation du token
        response_time_ms = int((time.time() - start_time) * 1000)
        if token_id and _token_db:
            try:
                from app.database import log_token_usage
                # S'assurer que countries est une liste avant le join
                countries_str = ",".join(countries) if isinstance(countries, list) and countries else (countries if isinstance(countries, str) else None)
                log_token_usage(
                    _token_db,
                    token_id=token_id,
                    token_name=token_name,
                    action_type="search",
                    keyword=keyword,
                    countries=countries_str,
                    success=success,
                    ads_count=len(all_ads),
                    error_message=error_msg,
                    response_time_ms=response_time_ms
                )
            except Exception as log_err:
                print(f"⚠️ Erreur logging token: {log_err}")

        return all_ads

    def fetch_all_ads_for_page(
        self,
        page_id: str,
        countries: List[str],
        languages: List[str]
    ) -> Tuple[List[dict], int]:
        """
        Récupère toutes les annonces d'une page spécifique

        Args:
            page_id: ID de la page Facebook
            countries: Liste des codes pays
            languages: Liste des codes langues

        Returns:
            Tuple (liste des annonces, nombre total)
        """
        # Capture du token utilisé pour le logging
        rotator = get_token_rotator()
        token_id = rotator.get_current_token_id() if rotator else None
        token_name = rotator.get_current_token_name() if rotator else "Default"
        start_time = time.time()
        error_msg = None
        success = True

        params = {
            "search_page_ids": json.dumps([str(page_id)]),
            "ad_active_status": "ACTIVE",
            "ad_type": "ALL",
            "ad_reached_countries": json.dumps(countries),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_COUNT
        }
        # N'inclure languages que si une liste non vide est fournie
        if languages:
            params["languages"] = json.dumps(languages)

        url = ADS_ARCHIVE
        all_ads = []

        while True:
            try:
                data = self._get_api(url, params)
            except Exception as e:
                error_msg = str(e)
                success = False
                # Log de l'utilisation du token (erreur)
                response_time_ms = int((time.time() - start_time) * 1000)
                if token_id and _token_db:
                    try:
                        from app.database import log_token_usage
                        countries_str = ",".join(countries) if isinstance(countries, list) and countries else (countries if isinstance(countries, str) else None)
                        log_token_usage(
                            _token_db,
                            token_id=token_id,
                            token_name=token_name,
                            action_type="page_fetch",
                            page_id=str(page_id),
                            countries=countries_str,
                            success=False,
                            ads_count=len(all_ads),
                            error_message=error_msg,
                            response_time_ms=response_time_ms
                        )
                    except Exception as log_err:
                        print(f"⚠️ Erreur logging token: {log_err}")
                return all_ads, -1

            batch = data.get("data", [])
            all_ads.extend(batch)

            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break

            # Délai entre les pages pour éviter rate limit
            time.sleep(META_DELAY_BETWEEN_PAGES)

            url = next_url
            params = {}

        # Log de l'utilisation du token (succès)
        response_time_ms = int((time.time() - start_time) * 1000)
        if token_id and _token_db:
            try:
                from app.database import log_token_usage
                countries_str = ",".join(countries) if isinstance(countries, list) and countries else (countries if isinstance(countries, str) else None)
                log_token_usage(
                    _token_db,
                    token_id=token_id,
                    token_name=token_name,
                    action_type="page_fetch",
                    page_id=str(page_id),
                    countries=countries_str,
                    success=True,
                    ads_count=len(all_ads),
                    response_time_ms=response_time_ms
                )
            except Exception as log_err:
                print(f"⚠️ Erreur logging token: {log_err}")

        return all_ads, len(all_ads)

    def fetch_ads_for_pages_batch(
        self,
        page_ids: List[str],
        countries: List[str],
        languages: List[str],
        max_per_request: int = 10
    ) -> Dict[str, Tuple[List[dict], int]]:
        """
        Récupère les annonces pour plusieurs pages en une seule requête
        L'API Meta permet jusqu'à 10 page_ids par requête

        Args:
            page_ids: Liste des IDs de pages (max 10 recommandé)
            countries: Liste des codes pays
            languages: Liste des codes langues
            max_per_request: Nombre max de pages par requête (défaut: 10)

        Returns:
            Dict {page_id: (liste des annonces, count)}
        """
        results = {}

        # Limiter à max_per_request pages par batch
        page_ids_to_fetch = page_ids[:max_per_request]

        params = {
            "search_page_ids": json.dumps([str(pid) for pid in page_ids_to_fetch]),
            "ad_active_status": "ACTIVE",
            "ad_type": "ALL",
            "ad_reached_countries": json.dumps(countries),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_COUNT
        }
        # N'inclure languages que si une liste non vide est fournie
        if languages:
            params["languages"] = json.dumps(languages)

        url = ADS_ARCHIVE
        all_ads = []

        # Initialiser les résultats pour chaque page
        for pid in page_ids_to_fetch:
            results[str(pid)] = ([], 0)

        while True:
            try:
                data = self._get_api(url, params)
            except:
                break

            batch = data.get("data", [])
            all_ads.extend(batch)

            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break

            # Délai entre les pages pour éviter rate limit
            time.sleep(META_DELAY_BETWEEN_PAGES)

            url = next_url
            params = {}

        # Regrouper les annonces par page_id
        ads_by_page = {}
        for ad in all_ads:
            pid = str(ad.get("page_id", ""))
            if pid:
                if pid not in ads_by_page:
                    ads_by_page[pid] = []
                ads_by_page[pid].append(ad)

        # Construire les résultats finaux
        for pid in page_ids_to_fetch:
            pid_str = str(pid)
            ads = ads_by_page.get(pid_str, [])
            results[pid_str] = (ads, len(ads))

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# RECHERCHE PARALLÈLE INTELLIGENTE
# ═══════════════════════════════════════════════════════════════════════════════

def search_keywords_parallel(
    keywords: List[str],
    countries: List[str],
    languages: List[str],
    db=None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Tuple[List[dict], Dict[str, int]]:
    """
    Recherche des annonces pour plusieurs mots-clés avec stratégie adaptative:
    - Si tokens avec proxies: recherche parallèle (1 worker par token avec proxy)
    - Si pas de proxy: recherche séquentielle avec délai plus long

    Args:
        keywords: Liste des mots-clés à rechercher
        countries: Liste des codes pays
        languages: Liste des codes langues
        db: DatabaseManager pour le cache (optionnel)
        progress_callback: Callback(keyword, current, total) pour la progression

    Returns:
        Tuple (liste de toutes les ads, dict {keyword: nb_ads})
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        from app.config import (
            META_PARALLEL_ENABLED, META_DELAY_BETWEEN_KEYWORDS,
            META_DELAY_SEQUENTIAL_NO_PROXY, META_MIN_DELAY_BETWEEN_PARALLEL
        )
    except ImportError:
        META_PARALLEL_ENABLED = True
        META_DELAY_BETWEEN_KEYWORDS = 1.5
        META_DELAY_SEQUENTIAL_NO_PROXY = 3.5
        META_MIN_DELAY_BETWEEN_PARALLEL = 0.5

    rotator = get_token_rotator()
    if not rotator or rotator.token_count == 0:
        print("⚠️ Aucun token disponible pour la recherche")
        return [], {}

    all_ads = []
    ads_by_keyword = {}
    seen_ad_ids = set()

    # Déterminer la stratégie de recherche
    tokens_with_proxies = rotator.get_tokens_with_proxies() if rotator else []
    use_parallel = META_PARALLEL_ENABLED and len(tokens_with_proxies) > 1

    if use_parallel:
        # ═══ STRATÉGIE PARALLÈLE ═══
        # Chaque worker utilise un token+proxy dédié
        num_workers = len(tokens_with_proxies)
        print(f"🚀 Recherche parallèle activée: {num_workers} workers ({num_workers} tokens avec proxy)")

        # Créer un lock pour les résultats partagés
        from threading import Lock
        results_lock = Lock()
        failed_keywords = []  # Keywords qui ont échoué pour retry avec autre token

        def search_keyword_worker(args):
            """Worker pour rechercher un mot-clé avec un token+proxy dédié"""
            keyword, token_data, token_idx = args

            try:
                # Faire la requête API directement avec le token+proxy dédié
                ads = _search_ads_with_dedicated_token(
                    keyword, countries, languages,
                    token_data["token"], token_data.get("proxy"),
                    token_data.get("id"), token_data.get("name", f"Token #{token_idx+1}"),
                    db
                )
                # Si aucune ad et pas d'erreur, c'est peut-être un échec silencieux
                return keyword, ads, None, token_idx
            except Exception as e:
                print(f"❌ Erreur worker #{token_idx+1} pour '{keyword}': {e}")
                return keyword, [], str(e), token_idx

        # Distribuer les keywords aux workers
        keyword_tasks = []
        for i, kw in enumerate(keywords):
            # Assigner un token avec proxy à chaque keyword (round-robin)
            token_idx = i % len(tokens_with_proxies)
            token_data = tokens_with_proxies[token_idx]
            keyword_tasks.append((kw, token_data, token_idx))

        completed = 0
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Soumettre toutes les tâches avec un petit délai entre chaque
            futures = {}
            for i, task in enumerate(keyword_tasks):
                if i > 0:
                    time.sleep(META_MIN_DELAY_BETWEEN_PARALLEL)
                future = executor.submit(search_keyword_worker, task)
                futures[future] = task[0]  # keyword

            # Collecter les résultats au fur et à mesure
            for future in as_completed(futures):
                keyword = futures[future]
                try:
                    kw, ads, error, used_token_idx = future.result()

                    if error and len(ads) == 0:
                        # Échec - marquer pour retry avec un autre token
                        failed_keywords.append((kw, used_token_idx))
                    else:
                        with results_lock:
                            for ad in ads:
                                ad_id = ad.get("id")
                                if ad_id and ad_id not in seen_ad_ids:
                                    ad["_keyword"] = kw
                                    all_ads.append(ad)
                                    seen_ad_ids.add(ad_id)
                            ads_by_keyword[kw] = len(ads)

                    completed += 1
                    if progress_callback:
                        progress_callback(kw, completed, len(keywords))

                except Exception as e:
                    print(f"❌ Erreur future pour '{keyword}': {e}")
                    completed += 1

        # ═══ RETRY DES KEYWORDS ÉCHOUÉS AVEC UN AUTRE TOKEN ═══
        if failed_keywords and len(tokens_with_proxies) > 1:
            print(f"🔄 Retry de {len(failed_keywords)} keyword(s) avec un autre token...")

            for kw, failed_token_idx in failed_keywords:
                # Utiliser un token différent
                new_token_idx = (failed_token_idx + 1) % len(tokens_with_proxies)
                new_token_data = tokens_with_proxies[new_token_idx]

                print(f"  → Retry '{kw}' avec {new_token_data.get('name', f'Token #{new_token_idx+1}')}")
                time.sleep(META_DELAY_BETWEEN_KEYWORDS)  # Attendre avant le retry

                try:
                    ads = _search_ads_with_dedicated_token(
                        kw, countries, languages,
                        new_token_data["token"], new_token_data.get("proxy"),
                        new_token_data.get("id"), new_token_data.get("name", f"Token #{new_token_idx+1}"),
                        db
                    )

                    with results_lock:
                        for ad in ads:
                            ad_id = ad.get("id")
                            if ad_id and ad_id not in seen_ad_ids:
                                ad["_keyword"] = kw
                                all_ads.append(ad)
                                seen_ad_ids.add(ad_id)
                        ads_by_keyword[kw] = len(ads)

                    if len(ads) > 0:
                        print(f"  ✅ Retry réussi: {len(ads)} ads pour '{kw}'")
                    else:
                        print(f"  ⚠️ Retry: 0 ads pour '{kw}' (peut-être pas de résultats)")

                except Exception as e:
                    print(f"  ❌ Retry échoué pour '{kw}': {e}")
                    ads_by_keyword[kw] = 0

        print(f"✅ Recherche parallèle terminée: {len(all_ads)} ads uniques")

    else:
        # ═══ STRATÉGIE SÉQUENTIELLE ═══
        # Un seul token, délai plus long entre les requêtes
        delay = META_DELAY_SEQUENTIAL_NO_PROXY if not tokens_with_proxies else META_DELAY_BETWEEN_KEYWORDS
        print(f"🔄 Recherche séquentielle: {rotator.token_count} token(s), délai {delay}s entre keywords")

        client = MetaAdsClient(rotator.get_current_token())

        for i, kw in enumerate(keywords):
            if i > 0:
                time.sleep(delay)

            success = False
            max_token_attempts = min(rotator.token_count, 3)  # Max 3 tokens différents

            for attempt in range(max_token_attempts):
                try:
                    ads = client.search_ads(kw, countries, languages)

                    for ad in ads:
                        ad_id = ad.get("id")
                        if ad_id and ad_id not in seen_ad_ids:
                            ad["_keyword"] = kw
                            all_ads.append(ad)
                            seen_ad_ids.add(ad_id)

                    ads_by_keyword[kw] = len(ads)
                    success = True
                    break  # Succès, passer au keyword suivant

                except Exception as e:
                    print(f"❌ Erreur pour '{kw}' (tentative {attempt+1}/{max_token_attempts}): {e}")

                    # Si on a d'autres tokens, essayer avec le suivant
                    if attempt < max_token_attempts - 1 and rotator.token_count > 1:
                        rotator.rotate_to_next(reason=f"retry_error_{kw}")
                        client = MetaAdsClient(rotator.get_current_token())
                        print(f"  → Retry avec {rotator.get_current_token_name()}")
                        time.sleep(1)  # Petit délai avant retry

            if not success:
                ads_by_keyword[kw] = 0

            if progress_callback:
                progress_callback(kw, i + 1, len(keywords))

            # Rotation vers le prochain token pour le prochain keyword (répartir la charge)
            if rotator.token_count > 1:
                rotator.rotate_to_next(reason=f"keyword_{i+1}_done")
                client = MetaAdsClient(rotator.get_current_token())

        print(f"✅ Recherche séquentielle terminée: {len(all_ads)} ads uniques")

    return all_ads, ads_by_keyword


def _search_ads_with_dedicated_token(
    keyword: str,
    countries: List[str],
    languages: List[str],
    token: str,
    proxy: Optional[str],
    token_id: Optional[int],
    token_name: str,
    db=None,
    max_retries: int = 3
) -> List[dict]:
    """
    Recherche des annonces avec un token+proxy dédié (pour recherche parallèle).
    Ne passe pas par le rotator global.

    Args:
        keyword: Mot-clé à rechercher
        countries: Liste des codes pays
        languages: Liste des codes langues
        token: Token d'accès Meta API
        proxy: URL du proxy (optionnel)
        token_id: ID du token en DB
        token_name: Nom du token pour les logs
        db: DatabaseManager pour logging
        max_retries: Nombre max de tentatives par token
    """
    start_time = time.time()
    error_msg = None
    success = True

    url = ADS_ARCHIVE
    params = {
        "access_token": token,
        "search_terms": keyword,
        "search_type": "KEYWORD_UNORDERED",
        "ad_type": "ALL",
        "ad_active_status": "ACTIVE",
        "ad_reached_countries": json.dumps(countries),
        "fields": FIELDS_ADS_COMPLETE,
        "limit": LIMIT_SEARCH
    }
    if languages:
        params["languages"] = json.dumps(languages)

    # Configurer le proxy si disponible
    proxies = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}

    all_ads = []
    limit_curr = LIMIT_SEARCH

    while True:
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params, timeout=TIMEOUT, proxies=proxies, verify=False)

                try:
                    data = r.json()
                except (ValueError, json.JSONDecodeError):
                    data = {}

                # Check for errors
                if "error" in data:
                    error_code = data["error"].get("code")
                    error_msg_api = data["error"].get("message", "")

                    if error_code == 613 or "rate limit" in error_msg_api.lower():
                        # Rate limit - attendre et réessayer
                        sleep_time = min(2 ** attempt, 30)
                        print(f"⏳ Rate limit token {token_name}, attente {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue

                    # Réduire la limite si demandé
                    if ("reduce" in error_msg_api or "code\":1" in error_msg_api) and limit_curr > LIMIT_MIN:
                        limit_curr = max(LIMIT_MIN, limit_curr // 2)
                        params["limit"] = limit_curr
                        time.sleep(0.3)
                        continue

                    error_msg = error_msg_api
                    success = False
                    break

                # Succès
                batch = data.get("data", [])
                all_ads.extend(batch)

                next_url = data.get("paging", {}).get("next")
                if not next_url:
                    break

                # Délai entre les pages
                time.sleep(META_DELAY_BETWEEN_PAGES)
                url = next_url
                params = {}  # Next URL contient déjà les params
                break

            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                error_msg = str(e)
                success = False
                break
        else:
            # Toutes les tentatives ont échoué
            break

        # Si on n'a plus de next_url ou erreur, sortir
        if not data.get("paging", {}).get("next"):
            break

    # Log de l'utilisation du token
    response_time_ms = int((time.time() - start_time) * 1000)
    if token_id and db:
        try:
            from app.database import log_token_usage
            countries_str = ",".join(countries) if isinstance(countries, list) else countries
            log_token_usage(
                db,
                token_id=token_id,
                token_name=token_name,
                action_type="search_parallel",
                keyword=keyword,
                countries=countries_str,
                success=success,
                ads_count=len(all_ads),
                error_message=error_msg,
                response_time_ms=response_time_ms
            )
        except Exception as log_err:
            print(f"⚠️ Erreur logging token: {log_err}")

    return all_ads


def extract_website_from_ads(ads_list: List[dict]) -> str:
    """
    Extrait l'URL du site web depuis les annonces - Version optimisée
    Utilise patterns pré-compilés et système de scoring
    """
    if not ads_list:
        return ""

    # Importer les patterns pré-compilés
    try:
        from app.config import COMPILED_URL_PATTERNS, COMPILED_CAPTION_DOMAIN, COMPILED_DOMAIN_VALIDATOR
    except ImportError:
        # Fallback si import échoue
        COMPILED_URL_PATTERNS = [
            re.compile(r'https?://(?:www\.)?([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})'),
            re.compile(r'www\.([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})'),
        ]
        COMPILED_CAPTION_DOMAIN = re.compile(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2,})?$')
        COMPILED_DOMAIN_VALIDATOR = re.compile(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}')

    url_counter = Counter()

    # Liste étendue des domaines à exclure (set pour lookups O(1))
    excluded_domains = {
        # Réseaux sociaux
        "facebook.com", "instagram.com", "fb.me", "fb.com", "fb.watch",
        "messenger.com", "whatsapp.com", "meta.com",
        "twitter.com", "x.com", "tiktok.com", "pinterest.com",
        "linkedin.com", "snapchat.com", "threads.net",
        # Google
        "google.com", "google.fr", "youtube.com", "youtu.be", "goo.gl",
        # Raccourcisseurs
        "bit.ly", "t.co", "ow.ly", "tinyurl.com", "short.link",
        "rebrand.ly", "cutt.ly", "is.gd",
        # Autres
        "linktr.ee", "linkin.bio", "beacons.ai", "allmylinks.com",
        "shopify.com", "myshopify.com",
        "wixsite.com", "squarespace.com",
        "apple.com", "apps.apple.com", "play.google.com",
    }

    for ad in ads_list:
        # Champs à vérifier (ordre de priorité)
        fields_priority = {
            "ad_creative_link_captions": 5,   # Très fiable - c'est souvent le domaine exact
            "ad_creative_link_titles": 3,     # Fiable
            "ad_creative_link_descriptions": 2,
            "ad_creative_bodies": 1,          # Moins fiable mais utile
        }

        for field, base_weight in fields_priority.items():
            values = ad.get(field, [])

            # Normaliser en liste
            if values is None:
                continue
            if not isinstance(values, list):
                values = [values]

            for val in values:
                if not val:
                    continue

                val_str = str(val).strip().lower()

                # Méthode 1: Le caption EST souvent le domaine directement
                if field == "ad_creative_link_captions":
                    clean_caption = val_str.replace("www.", "").strip("/").strip()
                    if "." in clean_caption and len(clean_caption) < 50:
                        # Utiliser pattern pré-compilé
                        if COMPILED_CAPTION_DOMAIN.match(clean_caption):
                            if not any(exc in clean_caption for exc in excluded_domains):
                                url_counter[clean_caption] += 10

                # Méthode 2: Extraction par regex (patterns pré-compilés)
                for compiled_pattern in COMPILED_URL_PATTERNS:
                    matches = compiled_pattern.findall(val_str)
                    for match in matches:
                        clean = match.replace("www.", "").strip("/").strip(".")

                        # Vérifications de base
                        if len(clean) < 4 or len(clean) > 60:
                            continue
                        if "." not in clean:
                            continue
                        if any(exc in clean for exc in excluded_domains):
                            continue
                        # Éviter les faux positifs
                        if clean.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.webp')):
                            continue
                        if clean.startswith(('cdn.', 'static.', 'assets.', 'img.', 'images.')):
                            continue
                        # Éviter les emails
                        if '@' in val_str and clean in val_str.split('@')[1]:
                            continue

                        url_counter[clean] += base_weight

        # Méthode 3: Extraire depuis page_name si c'est un domaine
        page_name = ad.get("page_name", "")
        if page_name:
            page_name_lower = page_name.lower().strip()
            if "." in page_name_lower and " " not in page_name_lower:
                clean_name = page_name_lower.replace("www.", "").strip("/")
                # Utiliser pattern pré-compilé
                if COMPILED_CAPTION_DOMAIN.match(clean_name):
                    if not any(exc in clean_name for exc in excluded_domains):
                        url_counter[clean_name] += 2

    if not url_counter:
        return ""

    # Prendre le domaine le plus fréquent
    most_common = url_counter.most_common(1)[0][0]

    # Valider avec pattern pré-compilé
    if not COMPILED_DOMAIN_VALIDATOR.match(most_common):
        if len(url_counter) > 1:
            most_common = url_counter.most_common(2)[1][0]
        else:
            return ""

    if not most_common.startswith("http"):
        most_common = "https://" + most_common

    return most_common


def extract_currency_from_ads(ads_list: List[dict]) -> str:
    """Extrait la devise la plus fréquente depuis les annonces"""
    if not ads_list:
        return ""

    currencies = [
        str(ad.get("currency", "")).strip().upper()
        for ad in ads_list if ad.get("currency")
    ]
    if not currencies:
        return ""

    counter = Counter(currencies)
    return counter.most_common(1)[0][0]


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE API META
# ═══════════════════════════════════════════════════════════════════════════════

def cached_search_ads(
    client: MetaAdsClient,
    keyword: str,
    countries: List[str],
    languages: List[str],
    db=None,
    use_cache: bool = True,
    cache_ttl_hours: int = 6,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[List[dict], bool]:
    """
    Recherche des annonces avec cache optionnel.

    Args:
        client: MetaAdsClient instance
        keyword: Mot-cle a rechercher
        countries: Liste des codes pays
        languages: Liste des codes langues
        db: DatabaseManager pour le cache (optionnel)
        use_cache: Utiliser le cache (defaut: True)
        cache_ttl_hours: Duree de vie du cache en heures
        progress_callback: Fonction callback pour la progression

    Returns:
        Tuple (liste des ads, from_cache: bool)
    """
    # Si pas de db ou cache desactive, appel direct
    if not db or not use_cache:
        ads = client.search_ads(keyword, countries, languages, progress_callback)
        return (ads, False)

    try:
        from app.database import generate_cache_key, get_cached_response, set_cached_response

        # Generer la cle de cache
        cache_key = generate_cache_key(
            "search_ads",
            keyword=keyword.lower().strip(),
            countries=sorted(countries),
            languages=sorted(languages)
        )

        # Verifier le cache
        cached_data = get_cached_response(db, cache_key)
        if cached_data is not None:
            if progress_callback:
                progress_callback(len(cached_data), len(cached_data))
            return (cached_data, True)

        # Cache miss - faire l'appel API
        ads = client.search_ads(keyword, countries, languages, progress_callback)

        # Sauvegarder dans le cache si on a des resultats
        if ads:
            set_cached_response(
                db,
                cache_key,
                "search_ads",
                ads,
                ttl_hours=cache_ttl_hours
            )

        return (ads, False)

    except Exception as e:
        # En cas d'erreur de cache, fallback sur l'appel direct
        print(f"⚠️ Erreur cache: {e}")
        ads = client.search_ads(keyword, countries, languages, progress_callback)
        return (ads, False)


def cached_fetch_ads_for_page(
    client: MetaAdsClient,
    page_id: str,
    countries: List[str],
    db=None,
    use_cache: bool = True,
    cache_ttl_hours: int = 3
) -> Tuple[List[dict], bool]:
    """
    Recupere les ads d'une page avec cache optionnel.

    Args:
        client: MetaAdsClient instance
        page_id: ID de la page Facebook
        countries: Liste des codes pays
        db: DatabaseManager pour le cache (optionnel)
        use_cache: Utiliser le cache (defaut: True)
        cache_ttl_hours: Duree de vie du cache en heures

    Returns:
        Tuple (liste des ads, from_cache: bool)
    """
    # Si pas de db ou cache desactive, appel direct
    if not db or not use_cache:
        ads = client.fetch_all_ads_for_page(page_id, countries)
        return (ads, False)

    try:
        from app.database import generate_cache_key, get_cached_response, set_cached_response

        # Generer la cle de cache
        cache_key = generate_cache_key(
            "page_ads",
            page_id=page_id,
            countries=sorted(countries)
        )

        # Verifier le cache
        cached_data = get_cached_response(db, cache_key)
        if cached_data is not None:
            return (cached_data, True)

        # Cache miss - faire l'appel API
        ads = client.fetch_all_ads_for_page(page_id, countries)

        # Sauvegarder dans le cache si on a des resultats
        if ads:
            set_cached_response(
                db,
                cache_key,
                "page_ads",
                ads,
                ttl_hours=cache_ttl_hours
            )

        return (ads, False)

    except Exception as e:
        # En cas d'erreur de cache, fallback sur l'appel direct
        print(f"⚠️ Erreur cache: {e}")
        ads = client.fetch_all_ads_for_page(page_id, countries)
        return (ads, False)
