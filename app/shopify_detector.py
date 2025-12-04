"""
Module pour la détection de CMS - Version améliorée
Détecte Shopify, WooCommerce, PrestaShop, Magento, etc.
"""
import time
import re
import requests
from typing import Optional, Dict
from urllib.parse import urlparse

try:
    from app.config import HEADERS, TIMEOUT_SHOPIFY_CHECK
except ImportError:
    from config import HEADERS, TIMEOUT_SHOPIFY_CHECK


def detect_cms_from_url(url: str) -> Dict[str, any]:
    """
    Détecte le CMS d'un site web avec plusieurs méthodes

    Returns:
        Dict avec 'cms', 'is_shopify', 'confidence', 'details'
    """
    result = {
        "cms": "Unknown",
        "is_shopify": False,
        "confidence": 0,
        "details": ""
    }

    try:
        if not url.startswith("http"):
            url = "https://" + url

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Récupérer la page principale avec retry
        html = ""
        headers_dict = {}
        cookies = {}

        for attempt in range(3):
            try:
                timeout = TIMEOUT_SHOPIFY_CHECK + (attempt * 5)
                resp = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=timeout,
                    allow_redirects=True
                )

                if resp.status_code < 400:
                    html = resp.text[:200000].lower()
                    headers_dict = {k.lower(): v.lower() for k, v in resp.headers.items()}
                    cookies = resp.cookies.get_dict()
                    break

            except requests.RequestException:
                if attempt < 2:
                    time.sleep(1)
                    continue

        if not html:
            return result

        # ═══════════════════════════════════════════════════════════════════
        # DÉTECTION SHOPIFY (prioritaire)
        # ═══════════════════════════════════════════════════════════════════
        shopify_score = 0
        shopify_evidence = []

        # Patterns HTML (score +1 chacun)
        html_patterns = [
            ("cdn.shopify.com", 3),
            ("shopify.com", 1),
            ("/cdn/shop/", 2),
            ("shopify-analytics", 2),
            ("shopify.theme", 2),
            ("shopify.routes", 2),
            ("shopify.paymentbutton", 2),
            ("myshopify.com", 3),
            ("/cart.js", 1),
            ("shopify-section", 2),
            ("data-shopify", 2),
            ("shopify-features", 1),
            ("shopify_pay", 1),
            ("shop_pay", 1),
            ("monorail-edge.shopifysvc.com", 3),
            ("shopify.accesstoken", 2),
            ("window.shopify", 2),
            ("shopify.cdnhost", 2),
        ]

        for pattern, score in html_patterns:
            if pattern in html:
                shopify_score += score
                shopify_evidence.append(f"html:{pattern}")

        # Headers (score +2 chacun)
        header_patterns = [
            "x-shopify-stage",
            "x-shopify-request-id",
            "x-sorting-hat-podid",
            "x-sorting-hat-shopid",
            "x-shopid",
        ]

        for pattern in header_patterns:
            if pattern in headers_dict:
                shopify_score += 2
                shopify_evidence.append(f"header:{pattern}")

        if "shopify" in headers_dict.get("x-powered-by", ""):
            shopify_score += 2
            shopify_evidence.append("header:x-powered-by")

        if "shopify" in headers_dict.get("server", ""):
            shopify_score += 2
            shopify_evidence.append("header:server")

        # Cookies Shopify
        shopify_cookies = ["_shopify_s", "_shopify_y", "cart_sig", "secure_customer_sig"]
        for cookie in shopify_cookies:
            if cookie in cookies or cookie in str(headers_dict.get("set-cookie", "")):
                shopify_score += 2
                shopify_evidence.append(f"cookie:{cookie}")

        # Si score suffisant, c'est Shopify
        if shopify_score >= 3:
            result["cms"] = "Shopify"
            result["is_shopify"] = True
            result["confidence"] = min(100, shopify_score * 10)
            result["details"] = ", ".join(shopify_evidence[:5])
            return result

        # Vérifications API Shopify (si score faible mais potentiel)
        if shopify_score >= 1 or _check_shopify_endpoints(base_url):
            result["cms"] = "Shopify"
            result["is_shopify"] = True
            result["confidence"] = 80
            result["details"] = "API endpoint detected"
            return result

        # ═══════════════════════════════════════════════════════════════════
        # DÉTECTION AUTRES CMS
        # ═══════════════════════════════════════════════════════════════════

        # WooCommerce / WordPress
        woo_patterns = ["woocommerce", "wp-content", "wp-includes", "wordpress",
                        "wc-ajax", "add_to_cart", "cart-contents"]
        if any(p in html for p in woo_patterns):
            if "woocommerce" in html or "wc-ajax" in html:
                result["cms"] = "WooCommerce"
            else:
                result["cms"] = "WordPress"
            result["confidence"] = 80
            return result

        # PrestaShop
        presta_patterns = ["prestashop", "presta", "ps_", "prestashop-page"]
        if any(p in html for p in presta_patterns):
            result["cms"] = "PrestaShop"
            result["confidence"] = 80
            return result

        # Magento
        magento_patterns = ["magento", "mage-", "x-magento", "varien"]
        if any(p in html for p in magento_patterns) or "x-magento" in str(headers_dict):
            result["cms"] = "Magento"
            result["confidence"] = 80
            return result

        # Wix
        if "wixstatic.com" in html or "wix.com" in html:
            result["cms"] = "Wix"
            result["confidence"] = 90
            return result

        # Squarespace
        if "squarespace.com" in html or "static1.squarespace" in html:
            result["cms"] = "Squarespace"
            result["confidence"] = 90
            return result

        # BigCommerce
        if "bigcommerce" in html or "cdn.bcapp" in html:
            result["cms"] = "BigCommerce"
            result["confidence"] = 80
            return result

        # Webflow
        if "webflow" in html:
            result["cms"] = "Webflow"
            result["confidence"] = 80
            return result

        # Shopware
        if "shopware" in html:
            result["cms"] = "Shopware"
            result["confidence"] = 80
            return result

        # OpenCart
        if "opencart" in html or "route=product" in html:
            result["cms"] = "OpenCart"
            result["confidence"] = 70
            return result

        # Salesforce Commerce Cloud
        if "demandware" in html or "salesforce" in html.lower():
            result["cms"] = "Salesforce Commerce"
            result["confidence"] = 70
            return result

        return result

    except Exception as e:
        return result


def _check_shopify_endpoints(base_url: str) -> bool:
    """Vérifie les endpoints spécifiques Shopify"""
    endpoints = [
        ("/products.json?limit=1", "products"),
        ("/cart.json", "token"),
        ("/meta.json", "id"),
    ]

    for endpoint, key in endpoints:
        try:
            resp = requests.get(
                f"{base_url}{endpoint}",
                headers=HEADERS,
                timeout=TIMEOUT_SHOPIFY_CHECK,
                allow_redirects=True
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if key in data or isinstance(data, dict):
                        return True
                except:
                    if "shopify" in resp.text.lower():
                        return True
        except:
            continue

    return False


def check_shopify_http(url: str) -> bool:
    """
    Vérifie si un site est Shopify - Wrapper de compatibilité
    """
    result = detect_cms_from_url(url)
    return result["is_shopify"]


def get_shopify_details(url: str) -> dict:
    """
    Récupère des détails supplémentaires sur un site Shopify
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

        if "cdn.shopify.com" in html.lower() or "x-shopify-" in headers_str:
            details["is_shopify"] = True

            m = re.search(r'Shopify\.shop\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                details["store_name"] = m.group(1)

            m = re.search(r'/cdn/shop/t/(\d+)/', html)
            if m:
                details["theme_id"] = m.group(1)

    except Exception:
        pass

    return details
