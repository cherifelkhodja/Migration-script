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
    """
    Compte les produits Shopify via sitemaps - Version améliorée
    Gère les différents formats de sitemaps multi-pays Shopify
    """
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
    country_upper = country_code.upper()
    total = 0

    # Essayer plusieurs URLs de sitemap index
    sitemap_urls = [
        f"{origin}/sitemap.xml",
        f"{origin}/{country_lower}/sitemap.xml",
        f"{origin}/sitemap_index.xml",
    ]

    locs = []
    for sitemap_url in sitemap_urls:
        sm = get_text(sitemap_url)
        if sm:
            locs.extend(re.findall(r"<loc>([^<]+)</loc>", sm))
            break

    if not locs:
        # Fallback: essayer de compter via /products.json
        return _count_products_via_api(origin)

    # Patterns pour trouver les sitemaps de produits par pays
    # Shopify utilise différents formats:
    # - /sitemap_products_1.xml?from=123&to=456
    # - /fr/sitemap_products_1.xml
    # - /sitemap_products_fr_1.xml
    # - /en-fr/sitemap_products_1.xml

    product_sitemaps = []

    # 1. Chercher sitemaps avec code pays dans le path ou le nom
    for loc in locs:
        loc_lower = loc.lower()
        if "sitemap_products" in loc_lower:
            # Priorité aux sitemaps du pays spécifique
            if (f"/{country_lower}/" in loc_lower or
                f"_{country_lower}_" in loc_lower or
                f"_{country_lower}." in loc_lower or
                f"-{country_lower}/" in loc_lower or
                f"/{country_lower}-" in loc_lower):
                product_sitemaps.insert(0, loc)  # Priorité haute
            else:
                product_sitemaps.append(loc)

    # 2. Si aucun sitemap trouvé, essayer des URLs directes
    if not product_sitemaps:
        direct_urls = [
            # Format avec code pays
            f"{origin}/{country_lower}/sitemap_products_1.xml",
            f"{origin}/sitemap_products_{country_lower}_1.xml",
            # Format standard
            f"{origin}/sitemap_products_1.xml",
            f"{origin}/sitemap_products.xml",
        ]
        for url in direct_urls:
            if get_text(url):
                product_sitemaps.append(url)
                break

    # 3. Compter les produits dans les sitemaps
    seen_urls = set()
    for smu in product_sitemaps:
        if smu in seen_urls:
            continue
        seen_urls.add(smu)

        txt = get_text(smu)
        if not txt:
            continue

        # Compter les URLs de produits
        # Filtrer pour ne compter que les URLs de produits du bon pays si possible
        product_urls = re.findall(r"<loc>([^<]*?/products/[^<]+)</loc>", txt, re.I)

        if product_urls:
            # Filtrer par pays si URLs contiennent le code pays
            country_urls = [u for u in product_urls if f"/{country_lower}/" in u.lower()]
            if country_urls:
                total += len(country_urls)
            else:
                total += len(product_urls)
        else:
            # Fallback: compter toutes les URLs
            count = len(re.findall(r"<url>", txt))
            total += count

        if total > 10000:
            break

    # 4. Si toujours 0, essayer l'API
    if total == 0:
        total = _count_products_via_api(origin)

    return total


def _count_products_via_api(origin: str) -> int:
    """Compte les produits via l'API Shopify /products.json"""
    try:
        # L'API retourne max 250 produits par page, on estime le total
        url = f"{origin}/products.json?limit=250"
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)

        if r.status_code != 200:
            return 0

        data = r.json()
        products = data.get("products", [])
        count = len(products)

        # Si on a 250 produits, il y en a probablement plus
        if count == 250:
            # Essayer de paginer pour avoir un meilleur compte
            page = 2
            while page <= 10:  # Max 10 pages = 2500 produits
                url = f"{origin}/products.json?limit=250&page={page}"
                r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if r.status_code != 200:
                    break
                data = r.json()
                batch = data.get("products", [])
                if not batch:
                    break
                count += len(batch)
                if len(batch) < 250:
                    break
                page += 1

        return count

    except:
        return 0


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
