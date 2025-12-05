"""
Module pour l'interaction avec l'API Meta Ads Archive
"""
import json
import time
import re
import requests
from collections import Counter
from typing import List, Dict, Tuple, Optional, Callable

try:
    from app.config import (
        ADS_ARCHIVE, TIMEOUT, LIMIT_SEARCH, LIMIT_COUNT, LIMIT_MIN,
        FIELDS_ADS_COMPLETE
    )
    from app.api_tracker import get_current_tracker
except ImportError:
    from config import (
        ADS_ARCHIVE, TIMEOUT, LIMIT_SEARCH, LIMIT_COUNT, LIMIT_MIN,
        FIELDS_ADS_COMPLETE
    )
    try:
        from api_tracker import get_current_tracker
    except ImportError:
        def get_current_tracker():
            return None


class MetaAdsClient:
    """Client pour interagir avec l'API Meta Ads Archive"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._current_keyword = ""  # Pour tracking

    def _get_api(self, url: str, params: dict) -> dict:
        """Appel API avec retry automatique et gestion du rate limiting"""
        params = params.copy()
        params["access_token"] = self.access_token

        tracker = get_current_tracker()
        max_retries = 5

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                r = requests.get(url, params=params, timeout=TIMEOUT)
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

        url = ADS_ARCHIVE
        params = {
            "search_terms": keyword,
            "search_type": "KEYWORD_UNORDERED",
            "ad_type": "ALL",
            "ad_active_status": "ACTIVE",
            "ad_reached_countries": json.dumps(countries),
            "languages": json.dumps(languages),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_SEARCH
        }

        all_ads = []
        limit_curr = LIMIT_SEARCH

        while True:
            try:
                data = self._get_api(url, params)
            except RuntimeError as e:
                err_msg = str(e)
                if ("reduce" in err_msg or "code\":1" in err_msg) and limit_curr > LIMIT_MIN:
                    limit_curr = max(LIMIT_MIN, limit_curr // 2)
                    params["limit"] = limit_curr
                    time.sleep(0.3)
                    continue
                break

            batch = data.get("data", [])
            all_ads.extend(batch)

            if progress_callback:
                progress_callback(len(all_ads), -1)

            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break

            url = next_url
            params = {}

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
        params = {
            "search_page_ids": json.dumps([str(page_id)]),
            "ad_active_status": "ACTIVE",
            "ad_type": "ALL",
            "ad_reached_countries": json.dumps(countries),
            "languages": json.dumps(languages),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_COUNT
        }

        url = ADS_ARCHIVE
        all_ads = []

        while True:
            try:
                data = self._get_api(url, params)
            except:
                return all_ads, -1

            batch = data.get("data", [])
            all_ads.extend(batch)

            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            url = next_url
            params = {}

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
            "languages": json.dumps(languages),
            "fields": FIELDS_ADS_COMPLETE,
            "limit": LIMIT_COUNT
        }

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


def extract_website_from_ads(ads_list: List[dict]) -> str:
    """
    Extrait l'URL du site web depuis les annonces - Version améliorée
    Utilise plusieurs méthodes et un système de scoring
    """
    if not ads_list:
        return ""

    url_counter = Counter()

    # Liste étendue des domaines à exclure
    excluded_domains = [
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
        "shopify.com", "myshopify.com",  # Domaines Shopify génériques
        "wixsite.com", "squarespace.com",
        "apple.com", "apps.apple.com", "play.google.com",
    ]

    # Extensions de domaines valides (étendu)
    valid_tlds = (
        # Génériques
        "com", "net", "org", "co", "io", "app", "dev", "me", "info", "biz",
        # E-commerce
        "shop", "store", "boutique", "buy", "sale", "deals",
        # Pays européens
        "fr", "de", "es", "it", "pt", "nl", "be", "ch", "at", "lu",
        "uk", "co.uk", "ie", "pl", "se", "no", "dk", "fi",
        # Autres pays
        "ca", "us", "au", "nz", "br", "mx", "ar",
        # Nouveaux TLDs
        "online", "site", "website", "web", "live", "world", "tech",
        "fashion", "beauty", "style", "fit", "health", "life",
    )

    # Patterns regex améliorés
    url_patterns = [
        # URL complète avec protocole
        r'https?://(?:www\.)?([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})',
        # Domaine avec www
        r'www\.([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})',
        # Domaine simple (mot.extension)
        r'\b([a-z0-9][-a-z0-9]{1,}\.(?:' + '|'.join(valid_tlds) + r'))\b',
        # Domaine avec sous-domaine
        r'\b([a-z0-9][-a-z0-9]*\.[a-z0-9][-a-z0-9]*\.(?:' + '|'.join(valid_tlds[:20]) + r'))\b',
    ]

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
                    # Nettoyer et vérifier si c'est un domaine valide
                    clean_caption = val_str.replace("www.", "").strip("/").strip()
                    if "." in clean_caption and len(clean_caption) < 50:
                        # Vérifier que ça ressemble à un domaine
                        if re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2,})?$', clean_caption):
                            if not any(exc in clean_caption for exc in excluded_domains):
                                url_counter[clean_caption] += 10  # Très haute priorité

                # Méthode 2: Extraction par regex
                for pattern in url_patterns:
                    matches = re.findall(pattern, val_str)
                    for match in matches:
                        # Nettoyer le domaine
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
            # Vérifier si le page_name ressemble à un domaine
            if "." in page_name_lower and " " not in page_name_lower:
                clean_name = page_name_lower.replace("www.", "").strip("/")
                if re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2,})?$', clean_name):
                    if not any(exc in clean_name for exc in excluded_domains):
                        url_counter[clean_name] += 2  # Poids moyen

    if not url_counter:
        return ""

    # Prendre le domaine le plus fréquent
    most_common = url_counter.most_common(1)[0][0]

    # Valider que c'est bien un domaine valide
    if not re.match(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}', most_common):
        # Essayer le second choix
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
