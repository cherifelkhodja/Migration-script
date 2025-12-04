"""
Module pour la détection de sites Shopify
"""
import time
import requests
from typing import Optional

try:
    from app.config import HEADERS, TIMEOUT_SHOPIFY_CHECK
except ImportError:
    from config import HEADERS, TIMEOUT_SHOPIFY_CHECK


def check_shopify_http(url: str) -> bool:
    """
    Vérifie si un site est Shopify via HTTP

    Args:
        url: URL du site à vérifier

    Returns:
        True si le site est Shopify, False sinon
    """
    try:
        if not url.startswith("http"):
            url = "https://" + url

        # Retry avec timeout progressif
        for attempt in range(3):
            try:
                timeout = TIMEOUT_SHOPIFY_CHECK + (attempt * 5)
                resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)

                if resp.status_code >= 400:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    return False

                html = resp.text[:100000].lower()
                headers_str = "\n".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()

                # Patterns Shopify multiples
                shopify_indicators = [
                    "shopify" in html,
                    "cdn.shopify.com" in html,
                    "x-shopify-" in headers_str,
                    "shopify.com" in headers_str,
                    "/cdn/shop/" in html,
                    "shopify-analytics" in html
                ]

                return any(shopify_indicators)

            except requests.Timeout:
                if attempt < 2:
                    time.sleep(1)
                    continue
                return False
            except requests.RequestException:
                if attempt < 2:
                    time.sleep(1)
                    continue
                return False

        return False
    except Exception:
        return False


def get_shopify_details(url: str) -> dict:
    """
    Récupère des détails supplémentaires sur un site Shopify

    Args:
        url: URL du site Shopify

    Returns:
        Dictionnaire avec les détails (store_name, etc.)
    """
    details = {
        "is_shopify": False,
        "store_name": "",
        "theme_id": "",
    }

    try:
        if not url.startswith("http"):
            url = "https://" + url

        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SHOPIFY_CHECK, allow_redirects=True)
        if resp.status_code >= 400:
            return details

        html = resp.text[:100000]
        headers_str = "\n".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()

        # Vérifier si Shopify
        if "cdn.shopify.com" in html.lower() or "x-shopify-" in headers_str:
            details["is_shopify"] = True

            # Extraire le nom du store
            import re
            m = re.search(r'Shopify\.shop\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                details["store_name"] = m.group(1)

            # Extraire l'ID du thème
            m = re.search(r'/cdn/shop/t/(\d+)/', html)
            if m:
                details["theme_id"] = m.group(1)

    except Exception:
        pass

    return details
