"""
Module pour la detection de CMS - Version amelioree.

Detecte Shopify, WooCommerce, PrestaShop, Magento, etc.
"""
import time
import re
import requests
from typing import Dict
from urllib.parse import urlparse

from src.infrastructure.config import (
    HEADERS,
    TIMEOUT_SHOPIFY_CHECK,
    get_proxied_url,
)


def detect_cms_from_url(url: str) -> Dict[str, any]:
    """
    Detecte le CMS d'un site web avec plusieurs methodes.
    Utilise ScraperAPI si configure pour eviter les bans.

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

        # Recuperer la page principale avec retry + fallback sans proxy
        html = ""
        headers_dict = {}
        cookies = {}

        # Phase 1: Essayer avec proxy (si configure)
        from src.infrastructure.config import is_proxy_enabled
        proxy_failed = False

        for attempt in range(3):
            try:
                timeout = TIMEOUT_SHOPIFY_CHECK + (attempt * 5)
                proxied_url, headers = get_proxied_url(url)
                resp = requests.get(
                    proxied_url,
                    headers=headers,
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
                else:
                    proxy_failed = True

        # Phase 2: Fallback sans proxy si echec et proxy etait active
        if not html and proxy_failed and is_proxy_enabled():
            import random
            from src.infrastructure.config import USER_AGENTS
            direct_headers = {"User-Agent": random.choice(USER_AGENTS)}

            for attempt in range(2):
                try:
                    timeout = TIMEOUT_SHOPIFY_CHECK + (attempt * 5)
                    resp = requests.get(
                        url,
                        headers=direct_headers,
                        timeout=timeout,
                        allow_redirects=True
                    )

                    if resp.status_code < 400:
                        html = resp.text[:200000].lower()
                        headers_dict = {k.lower(): v.lower() for k, v in resp.headers.items()}
                        cookies = resp.cookies.get_dict()
                        break

                except requests.RequestException:
                    if attempt < 1:
                        time.sleep(1)
                        continue

        if not html:
            return result

        # ==================================================================
        # DETECTION SHOPIFY (prioritaire)
        # ==================================================================
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

        # Verifications API Shopify (si score faible mais potentiel)
        if shopify_score >= 1 or _check_shopify_endpoints(base_url):
            result["cms"] = "Shopify"
            result["is_shopify"] = True
            result["confidence"] = 80
            result["details"] = "API endpoint detected"
            return result

        # ==================================================================
        # DETECTION AUTRES CMS (ordre de priorite par frequence)
        # ==================================================================

        # WooCommerce (WordPress + plugin e-commerce)
        woo_strong = ["woocommerce", "wc-ajax", "wc-add-to-cart", "wc_cart", "wc-blocks"]
        woo_medium = ["wp-content/plugins/woocommerce", "add_to_cart_button", "cart-contents"]
        if any(p in html for p in woo_strong):
            result["cms"] = "WooCommerce"
            result["confidence"] = 90
            return result
        if any(p in html for p in woo_medium):
            result["cms"] = "WooCommerce"
            result["confidence"] = 75
            return result

        # WordPress (sans WooCommerce)
        wp_patterns = ["wp-content", "wp-includes", "wordpress", "wp-json", "/wp-admin",
                       'name="generator" content="wordpress', "powered by wordpress"]
        if any(p in html for p in wp_patterns):
            result["cms"] = "WordPress"
            result["confidence"] = 80
            return result

        # PrestaShop
        presta_strong = ["prestashop", "/modules/ps_", "prestashop-page", "id_product="]
        presta_medium = ["ps_shoppingcart", "ps_customersignin", "blockcart", "/themes/classic/"]
        if any(p in html for p in presta_strong):
            result["cms"] = "PrestaShop"
            result["confidence"] = 90
            return result
        if any(p in html for p in presta_medium):
            result["cms"] = "PrestaShop"
            result["confidence"] = 75
            return result

        # Magento / Adobe Commerce
        magento_strong = ["magento", "mage-", "x-magento", "/static/frontend/magento"]
        magento_medium = ["varien", "mage/cookies", "checkout/cart", "catalogsearch/result"]
        if any(p in html for p in magento_strong) or "x-magento" in str(headers_dict):
            result["cms"] = "Magento"
            result["confidence"] = 90
            return result
        if any(p in html for p in magento_medium):
            result["cms"] = "Magento"
            result["confidence"] = 70
            return result

        # Wix
        wix_patterns = ["wixstatic.com", "wix.com", "parastorage.com", "_wix_browser_sess",
                        "wix-code-sdk", "wixapps.net"]
        if any(p in html for p in wix_patterns):
            result["cms"] = "Wix"
            result["confidence"] = 90
            return result

        # Squarespace
        squarespace_patterns = ["squarespace.com", "static1.squarespace", "squarespace-cdn",
                                 "sqs-analytics", 'data-squarespace-']
        if any(p in html for p in squarespace_patterns):
            result["cms"] = "Squarespace"
            result["confidence"] = 90
            return result

        # BigCommerce
        bigcommerce_patterns = ["bigcommerce", "cdn.bcapp", "bcappcdn", "bigcommerce.com",
                                 "stencil-", "cornerstone-"]
        if any(p in html for p in bigcommerce_patterns):
            result["cms"] = "BigCommerce"
            result["confidence"] = 85
            return result

        # Webflow
        webflow_patterns = ["webflow.com", "assets.website-files.com", 'data-wf-site',
                            "webflow-production", "w-commerce"]
        if any(p in html for p in webflow_patterns):
            result["cms"] = "Webflow"
            result["confidence"] = 90
            return result

        # Shopware
        shopware_patterns = ["shopware", "sw-cms-", "sw-blocks", "/frontend/", "shopware.com"]
        if any(p in html for p in shopware_patterns):
            result["cms"] = "Shopware"
            result["confidence"] = 85
            return result

        # OpenCart
        opencart_patterns = ["opencart", "route=product", "route=checkout", "index.php?route="]
        if any(p in html for p in opencart_patterns):
            result["cms"] = "OpenCart"
            result["confidence"] = 80
            return result

        # Salesforce Commerce Cloud (Demandware)
        sfcc_patterns = ["demandware", "dwanalytics", "dw/shop", "sfcc", "salesforce commerce"]
        if any(p in html for p in sfcc_patterns):
            result["cms"] = "Salesforce Commerce"
            result["confidence"] = 85
            return result

        # WiziShop (francais)
        wizishop_patterns = ["wizishop", "wizi-", "cdn.wizishop.com"]
        if any(p in html for p in wizishop_patterns):
            result["cms"] = "WiziShop"
            result["confidence"] = 90
            return result

        # Oxatis (francais)
        oxatis_patterns = ["oxatis", "cdn.oxatis.com", "oxatis-cdn"]
        if any(p in html for p in oxatis_patterns):
            result["cms"] = "Oxatis"
            result["confidence"] = 90
            return result

        # Ecwid
        ecwid_patterns = ["ecwid", "app.ecwid.com", "ecwid_product"]
        if any(p in html for p in ecwid_patterns):
            result["cms"] = "Ecwid"
            result["confidence"] = 90
            return result

        # Jimdo
        jimdo_patterns = ["jimdo", "jimdocdn", "a.jimdo.com"]
        if any(p in html for p in jimdo_patterns):
            result["cms"] = "Jimdo"
            result["confidence"] = 90
            return result

        # Drupal Commerce
        drupal_patterns = ["drupal", "/sites/default/files", "drupal.org", "/core/misc/drupal"]
        if any(p in html for p in drupal_patterns):
            result["cms"] = "Drupal"
            result["confidence"] = 80
            return result

        # Odoo
        odoo_patterns = ["odoo", "/web/static/", "/website/static/", "odoo.com"]
        if any(p in html for p in odoo_patterns):
            result["cms"] = "Odoo"
            result["confidence"] = 80
            return result

        # Typo3
        typo3_patterns = ["typo3", "typo3conf", "typo3temp"]
        if any(p in html for p in typo3_patterns):
            result["cms"] = "Typo3"
            result["confidence"] = 80
            return result

        # Joomla
        joomla_patterns = ["joomla", "/components/com_", "/media/jui/", "option=com_"]
        if any(p in html for p in joomla_patterns):
            result["cms"] = "Joomla"
            result["confidence"] = 80
            return result

        # Weebly
        weebly_patterns = ["weebly", "weeblycloud", "editmysite.com"]
        if any(p in html for p in weebly_patterns):
            result["cms"] = "Weebly"
            result["confidence"] = 90
            return result

        # Volusion
        volusion_patterns = ["volusion", "vspfiles", "/v/vspfiles/"]
        if any(p in html for p in volusion_patterns):
            result["cms"] = "Volusion"
            result["confidence"] = 85
            return result

        # 3dcart / Shift4Shop
        dcart_patterns = ["3dcart", "shift4shop", "3dcartstores"]
        if any(p in html for p in dcart_patterns):
            result["cms"] = "Shift4Shop"
            result["confidence"] = 85
            return result

        # Snipcart
        snipcart_patterns = ["snipcart", "cdn.snipcart.com", "snipcart-add-item"]
        if any(p in html for p in snipcart_patterns):
            result["cms"] = "Snipcart"
            result["confidence"] = 90
            return result

        # Gumroad
        gumroad_patterns = ["gumroad", "gumroad.com", "gumroad-overlay"]
        if any(p in html for p in gumroad_patterns):
            result["cms"] = "Gumroad"
            result["confidence"] = 90
            return result

        # Kajabi
        kajabi_patterns = ["kajabi", "kajabi-cdn", "app.kajabi.com"]
        if any(p in html for p in kajabi_patterns):
            result["cms"] = "Kajabi"
            result["confidence"] = 90
            return result

        # Teachable
        teachable_patterns = ["teachable", "teachablecdn", "app.teachable.com"]
        if any(p in html for p in teachable_patterns):
            result["cms"] = "Teachable"
            result["confidence"] = 90
            return result

        # Thinkific
        thinkific_patterns = ["thinkific", "thinkific.com", "thinkific-cdn"]
        if any(p in html for p in thinkific_patterns):
            result["cms"] = "Thinkific"
            result["confidence"] = 90
            return result

        # Podia
        podia_patterns = ["podia", "app.podia.com", "podia-cdn"]
        if any(p in html for p in podia_patterns):
            result["cms"] = "Podia"
            result["confidence"] = 90
            return result

        # Systeme.io
        systeme_patterns = ["systeme.io", "systemeio", "app.systeme.io"]
        if any(p in html for p in systeme_patterns):
            result["cms"] = "Systeme.io"
            result["confidence"] = 90
            return result

        # ClickFunnels
        clickfunnels_patterns = ["clickfunnels", "cf-styles", "cf2.com"]
        if any(p in html for p in clickfunnels_patterns):
            result["cms"] = "ClickFunnels"
            result["confidence"] = 90
            return result

        # Kartra
        kartra_patterns = ["kartra", "app.kartra.com", "kartra-cdn"]
        if any(p in html for p in kartra_patterns):
            result["cms"] = "Kartra"
            result["confidence"] = 90
            return result

        # ThriveCart
        thrivecart_patterns = ["thrivecart", "thrivecart.com"]
        if any(p in html for p in thrivecart_patterns):
            result["cms"] = "ThriveCart"
            result["confidence"] = 90
            return result

        # Samcart
        samcart_patterns = ["samcart", "app.samcart.com"]
        if any(p in html for p in samcart_patterns):
            result["cms"] = "SamCart"
            result["confidence"] = 90
            return result

        # Tilda
        tilda_patterns = ["tilda.cc", "tildacdn", "tilda-"]
        if any(p in html for p in tilda_patterns):
            result["cms"] = "Tilda"
            result["confidence"] = 90
            return result

        # Duda
        duda_patterns = ["duda.co", "dudaone", "cdn.duda.co"]
        if any(p in html for p in duda_patterns):
            result["cms"] = "Duda"
            result["confidence"] = 90
            return result

        # GoDaddy Website Builder
        godaddy_patterns = ["godaddy", "img.godaddy.com", "godaddy-website-builder"]
        if any(p in html for p in godaddy_patterns):
            result["cms"] = "GoDaddy"
            result["confidence"] = 85
            return result

        # HubSpot CMS
        hubspot_patterns = ["hubspot", "hs-scripts", "hscta", "hubspotusercontent"]
        if any(p in html for p in hubspot_patterns):
            result["cms"] = "HubSpot"
            result["confidence"] = 85
            return result

        # Shoptet (Czech)
        shoptet_patterns = ["shoptet", "shoptet.cz"]
        if any(p in html for p in shoptet_patterns):
            result["cms"] = "Shoptet"
            result["confidence"] = 90
            return result

        # Lightspeed eCom
        lightspeed_patterns = ["lightspeed", "shoplightspeed", "seoshop"]
        if any(p in html for p in lightspeed_patterns):
            result["cms"] = "Lightspeed"
            result["confidence"] = 85
            return result

        # Neto (Australia)
        neto_patterns = ["neto.com.au", "netosuite"]
        if any(p in html for p in neto_patterns):
            result["cms"] = "Neto"
            result["confidence"] = 85
            return result

        return result

    except Exception:
        return result


def _check_shopify_endpoints(base_url: str) -> bool:
    """Verifie les endpoints specifiques Shopify"""
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
                except Exception:
                    if "shopify" in resp.text.lower():
                        return True
        except Exception:
            continue

    return False


def check_shopify_http(url: str) -> bool:
    """
    Verifie si un site est Shopify - Wrapper de compatibilite
    """
    result = detect_cms_from_url(url)
    return result["is_shopify"]


def get_shopify_details(url: str) -> dict:
    """
    Recupere des details supplementaires sur un site Shopify
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
