"""
Module pour l'analyse complete des sites web.
"""
import re
import time
import requests
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup

from src.infrastructure.config import (
    REQUEST_TIMEOUT, HEADERS, DEFAULT_PAYMENTS, TAXONOMY, KEYWORD_OVERRIDES,
    THEME_ASSET_CANDIDATES, REQUEST_SNIPPET,
    TIMEOUT_WEB, get_proxied_url, is_proxy_enabled,
    # Patterns pre-compiles
    COMPILED_INLINE_PATTERNS, COMPILED_ASSET_PATTERNS, COMPILED_THEME_ID_PATTERN,
    COMPILED_THEME_CLEAN_PATTERN, COMPILED_SITEMAP_LOC, COMPILED_SITEMAP_URL_TAG,
    COMPILED_SITEMAP_LANG_PREFIX, COMPILED_CURRENCY_SHOPIFY, COMPILED_CURRENCY_OG,
    MAX_SITEMAPS_TO_PARSE, MAX_PRODUCTS_FROM_SITEMAP
)
from src.infrastructure.monitoring import get_current_tracker


def ensure_url(url: str) -> str:
    """Assure que l'URL commence par http(s)"""
    return url if url.startswith("http") else "https://" + url


def get_web(url: str, timeout: int = REQUEST_TIMEOUT, site_url: str = "", page_id: str = "") -> Optional[requests.Response]:
    """Requete HTTP avec gestion d'erreurs, proxy optionnel et User-Agent aleatoire"""
    tracker = get_current_tracker()
    start_time = time.time()
    use_proxy = is_proxy_enabled()

    try:
        proxied_url, headers = get_proxied_url(url)
        response = requests.get(proxied_url, headers=headers, timeout=timeout, allow_redirects=True)
        response_time = (time.time() - start_time) * 1000

        if tracker:
            api_type = "scraper_api" if use_proxy else "web_request"
            if api_type == "scraper_api":
                tracker.track_scraper_api_call(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    status_code=response.status_code,
                    success=response.status_code == 200,
                    response_time_ms=response_time,
                    response_size=len(response.content) if response.content else 0
                )
            else:
                tracker.track_web_request(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    page_id=page_id,
                    status_code=response.status_code,
                    success=response.status_code == 200,
                    response_time_ms=response_time,
                    response_size=len(response.content) if response.content else 0
                )

        return response
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        error_type = "timeout" if "timeout" in str(e).lower() else "error"

        if tracker:
            api_type = "scraper_api" if use_proxy else "web_request"
            if api_type == "scraper_api":
                tracker.track_scraper_api_call(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    success=False,
                    error_type=error_type,
                    error_message=str(e)[:200],
                    response_time_ms=response_time
                )
            else:
                tracker.track_web_request(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    page_id=page_id,
                    success=False,
                    error_type=error_type,
                    error_message=str(e)[:200],
                    response_time_ms=response_time
                )
        return None


def detect_cms(html: str, headers: dict) -> str:
    """Detecte le CMS utilise par le site"""
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


def _get_text(url: str, site_url: str = "") -> Optional[str]:
    """Recupere le contenu texte d'une URL avec proxy optionnel"""
    tracker = get_current_tracker()
    start_time = time.time()
    use_proxy = is_proxy_enabled()

    try:
        proxied_url, headers = get_proxied_url(url)
        r = requests.get(proxied_url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response_time = (time.time() - start_time) * 1000

        if tracker:
            api_type = "scraper_api" if use_proxy else "web_request"
            if api_type == "scraper_api":
                tracker.track_scraper_api_call(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    status_code=r.status_code,
                    success=r.status_code == 200,
                    response_time_ms=response_time,
                    response_size=len(r.content) if r.content else 0
                )
            else:
                tracker.track_web_request(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    status_code=r.status_code,
                    success=r.status_code == 200,
                    response_time_ms=response_time,
                    response_size=len(r.content) if r.content else 0
                )

        if r.status_code == 200 and r.text:
            return r.text
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        error_type = "timeout" if "timeout" in str(e).lower() else "error"

        if tracker:
            api_type = "scraper_api" if use_proxy else "web_request"
            if api_type == "scraper_api":
                tracker.track_scraper_api_call(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    success=False,
                    error_type=error_type,
                    error_message=str(e)[:200],
                    response_time_ms=response_time
                )
            else:
                tracker.track_web_request(
                    url=url[:200],
                    site_url=site_url or url[:200],
                    success=False,
                    error_type=error_type,
                    error_message=str(e)[:200],
                    response_time_ms=response_time
                )
        return None
    return None


def _unique(seq: list) -> list:
    """Retourne une liste unique tout en preservant l'ordre"""
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _clean_theme(name: Optional[str]) -> Optional[str]:
    """Nettoie le nom de theme"""
    if not name:
        return None
    n = name.strip().strip("/*-—–:=> \t\"'")
    if len(n) < 2 or len(n) > 120:
        return None
    # Utiliser le pattern pre-compile
    if COMPILED_THEME_CLEAN_PATTERN.search(n):
        return None
    return n


def _theme_shopify(html: str, base_url: str) -> Tuple[Optional[str], list]:
    """Detecte le theme Shopify - Version optimisee avec patterns pre-compiles"""
    evidence = []

    # Patterns inline (pre-compiles)
    for compiled_rgx in COMPILED_INLINE_PATTERNS:
        m = compiled_rgx.search(html)
        if m:
            nm = _clean_theme(m.group(1))
            if nm:
                return nm, evidence

    # Chercher l'ID du theme (pattern pre-compile)
    m_id = COMPILED_THEME_ID_PATTERN.search(html)
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
        # Patterns pre-compiles pour assets
        for compiled_rgx in COMPILED_ASSET_PATTERNS:
            m = compiled_rgx.search(head)
            if m:
                nm = _clean_theme(m.group(1))
                if nm:
                    return nm, evidence

    if theme_id:
        return f"theme_t_{theme_id}", evidence
    return None, evidence


def detect_theme(base_url: str, html: str, headers: dict, cms: str) -> Tuple[str, list]:
    """Detecte le theme utilise"""
    if cms == "Shopify":
        name, ev = _theme_shopify(html, base_url)
    else:
        name = "NA"
    return (name or "NA"), []


def detect_payments(html: str, soup: BeautifulSoup, terms: List[str]) -> List[str]:
    """Detecte les moyens de paiement disponibles"""
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
    """Genere les variantes de mots-cles"""
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
    """Essaie de recuperer le contenu d'une URL"""
    try:
        r = get_web(url)
        if r and r.status_code == 200 and r.text:
            return r.text
    except Exception:
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
    Compte les produits Shopify via sitemaps - Version optimisee.
    - Patterns regex pre-compiles
    - Limite max de sitemaps a parser (MAX_SITEMAPS_TO_PARSE)
    - Arret anticipe si MAX_PRODUCTS_FROM_SITEMAP atteint

    Logique:
    1. Sitemap avec code pays explicite (/{country}/) -> priorite haute
    2. Sitemap "root" sans prefixe de langue -> version par defaut du site
    3. Eviter les sitemaps des autres langues
    """
    def get_text_proxied(u):
        """Recupere le texte d'une URL avec proxy si disponible"""
        try:
            proxied_url, headers = get_proxied_url(u)
            r = requests.get(proxied_url, headers=headers, timeout=REQUEST_TIMEOUT)
            return r.text if r and r.status_code == 200 else None
        except Exception:
            return None

    # Nettoyer origin
    if not origin.startswith("http"):
        origin = "https://" + origin
    origin = origin.rstrip("/")

    country_lower = country_code.lower()
    total = 0

    # Codes langues connus a exclure (sauf si c'est notre pays)
    other_languages = {"en", "es", "de", "it", "pt", "nl", "pl", "ru", "ja", "zh", "ko", "ar"}
    other_languages.discard(country_lower)  # Ne pas exclure notre pays

    # Recuperer le sitemap index
    sm = get_text_proxied(f"{origin}/sitemap.xml")
    if not sm:
        return _count_products_via_api(origin)

    # Utiliser pattern pre-compile
    locs = COMPILED_SITEMAP_LOC.findall(sm)

    # Separer les sitemaps produits
    product_sitemaps_country = []  # Sitemaps avec notre code pays
    product_sitemaps_root = []     # Sitemaps "root" (sans prefixe langue)

    for loc in locs:
        loc_lower = loc.lower()

        # On ne s'interesse qu'aux sitemaps produits
        if "sitemap_products" not in loc_lower:
            continue

        # Extraire le path apres le domaine
        try:
            parsed = urlparse(loc)
            path = parsed.path.lower()
        except Exception:
            path = loc_lower

        # Verifier si c'est un sitemap avec prefixe de langue (pattern pre-compile)
        has_language_prefix = False
        is_our_country = False

        lang_match = COMPILED_SITEMAP_LANG_PREFIX.match(path)
        if lang_match:
            lang = lang_match.group(1)
            has_language_prefix = True
            if lang == country_lower:
                is_our_country = True
            elif lang in other_languages:
                # C'est une autre langue, on ignore
                continue

        # Classifier le sitemap
        if is_our_country:
            # Sitemap avec notre code pays -> priorite maximale
            product_sitemaps_country.append(loc)
        elif not has_language_prefix:
            # Sitemap "root" sans prefixe -> version par defaut
            product_sitemaps_root.append(loc)

    # Choisir les sitemaps a utiliser (priorite: pays > root)
    if product_sitemaps_country:
        product_sitemaps = product_sitemaps_country
    elif product_sitemaps_root:
        product_sitemaps = product_sitemaps_root
    else:
        # Fallback: essayer l'API
        return _count_products_via_api(origin)

    # Limiter le nombre de sitemaps a parser
    product_sitemaps = product_sitemaps[:MAX_SITEMAPS_TO_PARSE]

    # Compter les produits
    seen_urls = set()

    for smu in product_sitemaps:
        if smu in seen_urls:
            continue
        seen_urls.add(smu)

        txt = get_text_proxied(smu)
        if not txt:
            continue

        # Compter les URLs (pattern pre-compile)
        count = len(COMPILED_SITEMAP_URL_TAG.findall(txt))
        total += count

        # Arret anticipe si limite atteinte
        if total >= MAX_PRODUCTS_FROM_SITEMAP:
            print(f"Limite {MAX_PRODUCTS_FROM_SITEMAP} produits atteinte, arret anticipe")
            break

    # Si toujours 0, essayer l'API
    if total == 0:
        total = _count_products_via_api(origin)

    return total


def _count_products_via_api(origin: str) -> int:
    """Compte les produits via l'API Shopify /products.json avec proxy"""
    try:
        # L'API retourne max 250 produits par page, on estime le total
        url = f"{origin}/products.json?limit=250"
        proxied_url, headers = get_proxied_url(url)
        r = requests.get(proxied_url, headers=headers, timeout=REQUEST_TIMEOUT)

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
                proxied_url, headers = get_proxied_url(url)
                r = requests.get(proxied_url, headers=headers, timeout=REQUEST_TIMEOUT)
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

    except Exception:
        return 0


def extract_currency_from_html(html: str) -> Optional[str]:
    """Extrait la devise depuis le HTML Shopify - Version optimisee avec patterns pre-compiles"""
    m = COMPILED_CURRENCY_SHOPIFY.search(html)
    if m:
        return m.group(1)
    m = COMPILED_CURRENCY_OG.search(html)
    if m:
        return m.group(1)
    return None


def analyze_website_complete(url: str, country_code: str = "FR") -> Dict:
    """Analyse complete d'un site web avec extraction des donnees pour classification Gemini"""
    try:
        url = ensure_url(url)
        resp = get_web(url, timeout=TIMEOUT_WEB)

        if not resp or resp.status_code >= 400:
            return {
                "cms": "ERROR", "theme": "ERROR", "payments": "",
                "thematique": "", "type_produits": "", "product_count": 0,
                "currency_from_site": "",
                "site_title": "", "site_description": "", "site_h1": "", "site_keywords": ""
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

        # Extraire les donnees pour classification Gemini (economise un 2e scraping)
        site_title = ""
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            site_title = title_tag.string.strip()[:200]

        site_description = ""
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            site_description = desc_tag['content'].strip()[:400]

        site_h1 = ""
        h1_tag = soup.find('h1')
        if h1_tag:
            site_h1 = h1_tag.get_text(strip=True)[:150]

        site_keywords = ""
        kw_tag = soup.find('meta', attrs={'name': 'keywords'})
        if kw_tag and kw_tag.get('content'):
            site_keywords = kw_tag['content'].strip()[:200]

        return {
            "cms": cms,
            "theme": theme,
            "payments": ";".join(payments),
            "thematique": thematique or "",
            "type_produits": ";".join(product_list),
            "product_count": product_count,
            "currency_from_site": currency_from_site or "",
            # Donnees pour classification Gemini
            "site_title": site_title,
            "site_description": site_description,
            "site_h1": site_h1,
            "site_keywords": site_keywords
        }
    except Exception:
        return {
            "cms": "ERROR", "theme": "ERROR", "payments": "",
            "thematique": "", "type_produits": "", "product_count": 0,
            "currency_from_site": "",
            "site_title": "", "site_description": "", "site_h1": "", "site_keywords": ""
        }
