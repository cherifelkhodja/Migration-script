"""
Module pour l'analyse complète des sites web
"""
import re
import requests
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup

try:
    from app.config import (
        REQUEST_TIMEOUT, HEADERS, DEFAULT_PAYMENTS, TAXONOMY, KEYWORD_OVERRIDES,
        THEME_ASSET_CANDIDATES, REQUEST_SNIPPET, INLINE_NAME_PATTERNS,
        ASSET_HEADER_PATTERNS, TIMEOUT_WEB
    )
except ImportError:
    from config import (
        REQUEST_TIMEOUT, HEADERS, DEFAULT_PAYMENTS, TAXONOMY, KEYWORD_OVERRIDES,
        THEME_ASSET_CANDIDATES, REQUEST_SNIPPET, INLINE_NAME_PATTERNS,
        ASSET_HEADER_PATTERNS, TIMEOUT_WEB
    )


def ensure_url(url: str) -> str:
    """Assure que l'URL commence par http(s)"""
    return url if url.startswith("http") else "https://" + url


def get_web(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """Requête HTTP avec gestion d'erreurs"""
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except:
        return None


def detect_cms(html: str, headers: dict) -> str:
    """Détecte le CMS utilisé par le site"""
    h = html.lower()
    hdrs = "\n".join([f"{k}:{v}" for k, v in headers.items()]).lower()

    if "cdn.shopify.com" in h or "x-shopify-" in hdrs or "/collections/" in h or "/products/" in h:
        return "Shopify"
    if "woocommerce" in h or "wp-content" in h or 'content="wordpress' in h:
        return "WooCommerce / WordPress"
    if "prestashop" in h or "ps_shoppingcart" in h:
        return "PrestaShop"
    if "magento" in h or "x-magento" in hdrs:
        return "Magento"
    if "wixstatic.com" in h:
        return "Wix"
    if "static1.squarespace.com" in h:
        return "Squarespace"
    if "bigcommerce" in h or "cdn.bcapp" in h:
        return "BigCommerce"
    return "Unknown"


def _origin(url: str) -> str:
    """Extrait l'origine (scheme://host) d'une URL"""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _get_text(url: str) -> Optional[str]:
    """Récupère le contenu texte d'une URL"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and r.text:
            return r.text
    except:
        return None
    return None


def _unique(seq: list) -> list:
    """Retourne une liste unique tout en préservant l'ordre"""
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _clean_theme(name: Optional[str]) -> Optional[str]:
    """Nettoie le nom de thème"""
    if not name:
        return None
    n = name.strip().strip("/*-—–:=> \t\"'")
    if len(n) < 2 or len(n) > 120:
        return None
    if re.search(r'\btheme[_-]?t?_\d+\b', n, re.I):
        return None
    return n


def _theme_shopify(html: str, base_url: str) -> Tuple[Optional[str], list]:
    """Détecte le thème Shopify"""
    evidence = []

    # Patterns inline
    for rgx in INLINE_NAME_PATTERNS:
        m = re.search(rgx, html, re.I | re.M | re.S)
        if m:
            nm = _clean_theme(m.group(1))
            if nm:
                return nm, evidence

    # Chercher l'ID du thème
    m_id = re.search(r'/cdn/shop/t/(\d+)/', html, re.I)
    theme_id = m_id.group(1) if m_id else None

    origin = _origin(base_url)
    soup = BeautifulSoup(html, "lxml")
    asset_urls = []

    for tag in soup.find_all(["link", "script"]):
        src = tag.get("href") or tag.get("src")
        if src and (src.endswith(".css") or src.endswith(".js")) and ("/assets/" in src or "/cdn/shop/t/" in src):
            asset_urls.append(src if src.startswith("http") else urljoin(origin, src))

    for path in THEME_ASSET_CANDIDATES:
        asset_urls.append(urljoin(origin, path))

    asset_urls = _unique(asset_urls)[:25]

    for u in asset_urls:
        txt = _get_text(u)
        if not txt:
            continue
        head = txt[:REQUEST_SNIPPET]
        for rgx in ASSET_HEADER_PATTERNS:
            m = re.search(rgx, head, re.I | re.M)
            if m:
                nm = _clean_theme(m.group(1))
                if nm:
                    return nm, evidence

    if theme_id:
        return f"theme_t_{theme_id}", evidence
    return None, evidence


def detect_theme(base_url: str, html: str, headers: dict, cms: str) -> Tuple[str, list]:
    """Détecte le thème utilisé"""
    if cms == "Shopify":
        name, ev = _theme_shopify(html, base_url)
    else:
        name = "NA"
    return (name or "NA"), []


def detect_payments(html: str, soup: BeautifulSoup, terms: List[str]) -> List[str]:
    """Détecte les moyens de paiement disponibles"""
    text = " ".join([soup.get_text(" ", strip=True)[:400000], html]).lower()
    found = set()

    for t in terms:
        if t.lower() in text:
            found.add(t)

    for img in soup.find_all("img"):
        for attr in ("alt", "src"):
            val = (img.get(attr) or "").lower()
            for tt in terms:
                if tt.lower() in val:
                    found.add(tt)

    return sorted(found)


def _kws(label: str) -> List[str]:
    """Génère les variantes de mots-clés"""
    base = {label}
    for k in KEYWORD_OVERRIDES.get(label, []):
        base.add(k)

    def deacc(s):
        return (s.replace("é", "e").replace("è", "e").replace("ê", "e")
                .replace("à", "a").replace("ù", "u").replace("î", "i")
                .replace("ï", "i").replace("ô", "o").replace("ç", "c"))

    out = set()
    for b in base:
        out.add(b)
        out.add(deacc(b))
    return list(out)


def classify(text: str, taxonomy: Dict[str, List[str]]) -> Tuple[Optional[str], List[str]]:
    """Classifie le contenu selon la taxonomie"""
    tl = text.lower()
    theme_scores = {}

    for theme, products in taxonomy.items():
        sc = sum(1 for kw in _kws(theme) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl))
        sc += sum(1 for p in products for kw in _kws(p) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl)) * 0.25
        theme_scores[theme] = sc

    best_theme = max(theme_scores, key=theme_scores.get) if theme_scores else None
    if not best_theme or theme_scores[best_theme] == 0:
        return None, []

    hits = []
    for p in taxonomy[best_theme]:
        sc = sum(1 for kw in _kws(p) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl))
        if sc > 0:
            hits.append((p, sc))
    hits.sort(key=lambda x: (-x[1], x[0]))

    return best_theme, [p for p, _ in hits]


def try_get(url: str) -> Optional[str]:
    """Essaie de récupérer le contenu d'une URL"""
    try:
        r = get_web(url)
        if r and r.status_code == 200 and r.text:
            return r.text
    except:
        return None
    return None


def collect_text_for_classification(base_url: str, html: str) -> str:
    """Collecte le texte pour la classification"""
    texts = []
    soup = BeautifulSoup(html, "lxml")
    texts.append(soup.get_text(" ", strip=True))

    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

    # Sitemap
    sm = try_get(urljoin(origin, "/sitemap.xml")) or try_get(urljoin(origin, "/sitemap_index.xml"))
    if sm:
        col_urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm, re.I) if "/collections/" in u][:8]
        for u in col_urls:
            t = try_get(u)
            if t:
                texts.append(BeautifulSoup(t, "lxml").get_text(" ", strip=True))

    # Pages de collections
    for path in ["/collections", "/collections/all"]:
        t = try_get(urljoin(origin, path))
        if t:
            texts.append(BeautifulSoup(t, "lxml").get_text(" ", strip=True))

    # Navigation
    nav_text = []
    for sel in ["nav", "header", "footer", ".site-nav", ".menu"]:
        for el in soup.select(sel):
            nav_text.append(el.get_text(" ", strip=True))
    if nav_text:
        texts.append(" ".join(nav_text))

    return (" \n ".join(texts))[:800000]


def count_products_shopify_by_country(origin: str, country_code: str = "FR") -> int:
    """Compte les produits Shopify via sitemaps"""
    def get_text(u):
        try:
            r = requests.get(u, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            return r.text if r and r.status_code == 200 else None
        except:
            return None

    # Nettoyer origin
    if not origin.startswith("http"):
        origin = "https://" + origin
    origin = origin.rstrip("/")

    country_lower = country_code.lower()
    total = 0

    sm = get_text(urljoin(origin, "/sitemap.xml"))
    if not sm:
        return 0

    locs = re.findall(r"<loc>([^<]+)</loc>", sm)

    # Chercher sitemaps avec code pays
    product_sitemaps = [
        loc for loc in locs
        if f"sitemap_products_{country_lower}" in loc.lower() or f"products_{country_lower}" in loc.lower()
    ]

    # Fallback sur sitemaps globaux
    if not product_sitemaps:
        product_sitemaps = [loc for loc in locs if "sitemap_products" in loc]

    # Essayer URLs directes
    if not product_sitemaps:
        for i in range(1, 6):
            product_sitemaps.append(urljoin(origin, f"/sitemap_products_{country_lower}_{i}.xml"))
        for i in range(1, 6):
            product_sitemaps.append(urljoin(origin, f"/sitemap_products_{i}.xml"))

    for smu in product_sitemaps:
        txt = get_text(smu)
        if not txt:
            if "sitemap_products" in smu and total > 0:
                break
            continue

        count = len(re.findall(r"<url>", txt))
        total += count

        if total > 10000:
            break

    return total


def extract_currency_from_html(html: str) -> Optional[str]:
    """Extrait la devise depuis le HTML Shopify"""
    m = re.search(r'Shopify\.currency\s*=\s*{[^}]*"active"\s*:\s*"([A-Z]{3})"', html)
    if m:
        return m.group(1)
    m = re.search(r'property=["\']og:price:currency["\']\s+content=["\']([A-Z]{3})["\']', html, re.I)
    if m:
        return m.group(1)
    return None


def analyze_website_complete(url: str, country_code: str = "FR") -> Dict:
    """Analyse complète d'un site web"""
    try:
        url = ensure_url(url)
        resp = get_web(url, timeout=TIMEOUT_WEB)

        if not resp or resp.status_code >= 400:
            return {
                "cms": "ERROR", "theme": "ERROR", "payments": "",
                "thematique": "", "type_produits": "", "product_count": 0,
                "currency_from_site": ""
            }

        final_url = resp.url
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        cms = detect_cms(html, resp.headers)
        theme, _ = detect_theme(final_url, html, resp.headers, cms)
        payments = detect_payments(html, soup, DEFAULT_PAYMENTS)

        big_text = collect_text_for_classification(final_url, html)
        thematique, product_list = classify(big_text, TAXONOMY)

        product_count = 0
        if cms == "Shopify":
            origin = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
            product_count = count_products_shopify_by_country(origin, country_code)

        currency_from_site = extract_currency_from_html(html)

        return {
            "cms": cms,
            "theme": theme,
            "payments": ";".join(payments),
            "thematique": thematique or "",
            "type_produits": ";".join(product_list),
            "product_count": product_count,
            "currency_from_site": currency_from_site or ""
        }
    except Exception as e:
        return {
            "cms": "ERROR", "theme": "ERROR", "payments": "",
            "thematique": "", "type_produits": "", "product_count": 0,
            "currency_from_site": ""
        }
