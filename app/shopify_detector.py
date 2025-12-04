"""
Module pour la détection de sites Shopify - Version améliorée
"""
import time
import requests
from typing import Optional
from urllib.parse import urlparse

try:
    from app.config import HEADERS, TIMEOUT_SHOPIFY_CHECK
except ImportError:
    from config import HEADERS, TIMEOUT_SHOPIFY_CHECK


def check_shopify_http(url: str) -> bool:
    """
    Vérifie si un site est Shopify via HTTP - Version améliorée

    Args:
        url: URL du site à vérifier

    Returns:
        True si le site est Shopify, False sinon
    """
    try:
        if not url.startswith("http"):
            url = "https://" + url

        # Extraire le domaine de base
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Méthode 1: Vérifier la page principale
        for attempt in range(3):
            try:
                timeout = TIMEOUT_SHOPIFY_CHECK + (attempt * 5)
                resp = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=timeout,
                    allow_redirects=True
                )

                if resp.status_code >= 400:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    break

                html = resp.text[:150000].lower()
                headers_dict = {k.lower(): v.lower() for k, v in resp.headers.items()}

                # Patterns HTML étendus
                html_indicators = [
                    "cdn.shopify.com" in html,
                    "shopify.com" in html,
                    "/cdn/shop/" in html,
                    "shopify-analytics" in html,
                    "shopify.theme" in html,
                    "shopify.routes" in html,
                    "shopify.paymentbutton" in html,
                    "myshopify.com" in html,
                    "/cart.js" in html,
                    "/products.json" in html,
                    "shopify-section" in html,
                    "data-shopify" in html,
                    "shopify-features" in html,
                    "shopify_pay" in html,
                    "/checkouts/" in html,
                    "shop_pay" in html,
                    "assets/theme.js" in html,
                    "monorail-edge.shopifysvc.com" in html,
                ]

                # Patterns headers
                header_indicators = [
                    "x-shopify-stage" in headers_dict,
                    "x-shopify-request-id" in headers_dict,
                    "x-sorting-hat-podid" in headers_dict,
                    "x-sorting-hat-shopid" in headers_dict,
                    "shopify" in headers_dict.get("x-powered-by", ""),
                    "shopify" in headers_dict.get("server", ""),
                    ".myshopify.com" in headers_dict.get("x-request-id", ""),
                ]

                if any(html_indicators) or any(header_indicators):
                    return True

                break

            except requests.Timeout:
                if attempt < 2:
                    time.sleep(1)
                    continue
            except requests.RequestException:
                if attempt < 2:
                    time.sleep(1)
                    continue

        # Méthode 2: Vérifier l'endpoint /products.json (spécifique Shopify)
        try:
            products_url = f"{base_url}/products.json?limit=1"
            resp = requests.get(
                products_url,
                headers=HEADERS,
                timeout=TIMEOUT_SHOPIFY_CHECK,
                allow_redirects=True
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if "products" in data:
                        return True
                except:
                    pass

        except:
            pass

        # Méthode 3: Vérifier /meta.json (Shopify expose souvent ce fichier)
        try:
            meta_url = f"{base_url}/meta.json"
            resp = requests.get(
                meta_url,
                headers=HEADERS,
                timeout=TIMEOUT_SHOPIFY_CHECK,
                allow_redirects=True
            )

            if resp.status_code == 200:
                text = resp.text.lower()
                if "shopify" in text or "shop_id" in text:
                    return True

        except:
            pass

        # Méthode 4: Vérifier /cart.json
        try:
            cart_url = f"{base_url}/cart.json"
            resp = requests.get(
                cart_url,
                headers=HEADERS,
                timeout=TIMEOUT_SHOPIFY_CHECK,
                allow_redirects=True
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # Shopify cart.json a des clés spécifiques
                    if any(k in data for k in ["token", "items", "item_count", "total_price"]):
                        return True
                except:
                    pass

        except:
            pass

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
    import re

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
