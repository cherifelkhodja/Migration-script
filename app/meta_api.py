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
except ImportError:
    from config import (
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
