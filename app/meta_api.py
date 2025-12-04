"""
Module pour l'interaction avec l'API Meta Ads Archive
"""
import json
import time
import re
import requests
from collections import Counter
from typing import List, Dict, Tuple, Optional, Callable

from .config import (
    ADS_ARCHIVE, TIMEOUT, LIMIT_SEARCH, LIMIT_COUNT, LIMIT_MIN,
    FIELDS_ADS_COMPLETE
)


class MetaAdsClient:
    """Client pour interagir avec l'API Meta Ads Archive"""

    def __init__(self, access_token: str):
        self.access_token = access_token

    def _get_api(self, url: str, params: dict) -> dict:
        """Appel API avec retry automatique"""
        params = params.copy()
        params["access_token"] = self.access_token

        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=TIMEOUT)
                if r.status_code == 200:
                    return r.json()

                if r.status_code in (429, 500):
                    sleep_time = 0.5 * (attempt + 1)
                    time.sleep(sleep_time)
                    continue

                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            except requests.RequestException as e:
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise RuntimeError(f"Erreur réseau: {e}")

        raise RuntimeError("Échec après 3 tentatives")

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


def extract_website_from_ads(ads_list: List[dict]) -> str:
    """Extrait l'URL du site web depuis les annonces"""
    if not ads_list:
        return ""

    url_counter = Counter()

    for ad in ads_list:
        for field in ["ad_creative_link_captions", "ad_creative_link_titles"]:
            values = ad.get(field, [])
            if not isinstance(values, list):
                values = [values] if values else []

            for val in values:
                if not val:
                    continue

                val_str = str(val).strip().lower()
                patterns = [
                    r'(?:https?://)?(?:www\.)?([a-z0-9-]+\.[a-z]{2,})',
                    r'([a-z0-9-]+\.[a-z]{2,})',
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, val_str)
                    for match in matches:
                        clean = match.replace("www.", "").strip("/")
                        excluded = ["facebook.com", "instagram.com", "fb.me"]
                        if len(clean) > 4 and "." in clean and not any(x in clean for x in excluded):
                            url_counter[clean] += 1

    if not url_counter:
        return ""

    most_common = url_counter.most_common(1)[0][0]
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
