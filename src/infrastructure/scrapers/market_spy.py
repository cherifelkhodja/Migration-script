"""
MarketSpy V2 - Module d'analyse optimise pour sites e-commerce.

Architecture "Smart Stream" avec optimisations:
- 1 requete HTTP unique par site pour homepage (CMS + Theme + Metadata)
- Sitemap streaming avec limites budgetaires (50Ko/1MB)
- Connection pooling et gzip
- SSL configurable via PROXY_CA_BUNDLE
- Retry avec exponential backoff

Classes:
    - HttpClient: Client HTTP optimise avec retry et SSL
    - ThemeDetector: Detection theme Shopify depuis HTML uniquement
    - SitemapAnalyzer: Streaming sitemap avec limites
    - MarketSpy: Orchestrateur principal

Usage:
    spy = MarketSpy()
    result = spy.analyze(url)
"""

import os
import re
import time
import random
import logging
import warnings
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Desactiver les warnings SSL si pas de CA bundle
import urllib3

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================================================================
# CONFIGURATION
# ===========================================================================

# Timeouts (en secondes)
TIMEOUT_HOMEPAGE = 8
TIMEOUT_SITEMAP = 10

# Limites sitemap (en bytes)
SITEMAP_STREAM_LIMIT_MULTI = 50 * 1024      # 50 Ko pour extraction titres
SITEMAP_STREAM_LIMIT_SINGLE = 1 * 1024 * 1024  # 1 MB pour comptage

# Estimation produits par sitemap
PRODUCTS_PER_SITEMAP_ESTIMATE = 50000

# Retry configuration
RETRY_STATUS_CODES = [429, 502, 503, 504]
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 1.0  # 1s, 2s, 4s

# User-Agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

# Domaines a exclure (pre-filtrage sans HTTP)
EXCLUDED_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "pinterest.com", "tiktok.com", "youtube.com",
    "linktr.ee", "linktree.com", "bit.ly", "goo.gl", "t.co",
    "google.com", "apple.com", "amazon.com", "ebay.com",
}

# Patterns regex pre-compiles pour detection theme
THEME_JSON_PATTERNS = [
    re.compile(r'Shopify\.theme\s*=\s*\{[^}]*?"name"\s*:\s*"([^"]+)"', re.I),
    re.compile(r'Shopify\.theme\.name\s*=\s*["\']([^"\']+)["\']', re.I),
    re.compile(r'BOOMR\.themeName\s*=\s*["\']([^"\']+)["\']', re.I),
    re.compile(r'data-theme-name\s*=\s*["\']([^"\']+)["\']', re.I),
]

# Pattern pour extraire theme depuis URL des assets CSS
THEME_LINK_PATTERN = re.compile(
    r'<link[^>]+href=["\'][^"\']*?/assets/([a-zA-Z0-9_-]+)\.css',
    re.I
)

# Pattern alternatif pour CDN Shopify
THEME_CDN_PATTERN = re.compile(
    r'/cdn/shop/t/\d+/assets/([a-zA-Z0-9_-]+)(?:\.min)?\.css',
    re.I
)

# Patterns pour detection CMS
CMS_PATTERNS = {
    "Shopify": [
        re.compile(r'cdn\.shopify\.com', re.I),
        re.compile(r'Shopify\.theme', re.I),
        re.compile(r'/collections/', re.I),
        re.compile(r'/products/', re.I),
    ],
    "WooCommerce": [
        re.compile(r'woocommerce', re.I),
        re.compile(r'wp-content', re.I),
        re.compile(r'add-to-cart', re.I),
    ],
    "PrestaShop": [
        re.compile(r'prestashop', re.I),
        re.compile(r'ps_shoppingcart', re.I),
    ],
    "Magento": [
        re.compile(r'magento', re.I),
        re.compile(r'mage/', re.I),
    ],
    "Wix": [
        re.compile(r'wixstatic\.com', re.I),
        re.compile(r'wix\.com', re.I),
    ],
    "Squarespace": [
        re.compile(r'squarespace\.com', re.I),
        re.compile(r'static1\.squarespace', re.I),
    ],
    "BigCommerce": [
        re.compile(r'bigcommerce', re.I),
        re.compile(r'cdn\.bcapp', re.I),
    ],
}

# Patterns pour extraction metadata
CURRENCY_PATTERNS = [
    re.compile(r'Shopify\.currency\s*=\s*\{[^}]*"active"\s*:\s*"([A-Z]{3})"', re.I),
    re.compile(r'property=["\']og:price:currency["\']\s+content=["\']([A-Z]{3})["\']', re.I),
    re.compile(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', re.I),
]

# Patterns sitemap
SITEMAP_LOC_PATTERN = re.compile(r'<loc>([^<]+)</loc>', re.I)
SITEMAP_URL_PATTERN = re.compile(r'<url>', re.I)


# ===========================================================================
# DATA CLASSES
# ===========================================================================

@dataclass
class HomepageData:
    """Donnees extraites de la homepage en une seule requete."""
    url: str
    final_url: str = ""
    cms: str = "Unknown"
    theme: str = "Unknown"
    title: str = ""
    description: str = ""
    h1: str = ""
    currency: str = ""
    html: str = ""  # Conserve pour usage ulterieur (classification)
    error: Optional[str] = None

    @property
    def is_shopify(self) -> bool:
        return self.cms == "Shopify"

    def has_content(self) -> bool:
        """Verifie si on a du contenu pour classification."""
        return bool(self.title or self.description or self.h1)


@dataclass
class SitemapData:
    """Donnees extraites du sitemap."""
    url: str
    product_count: str = "N/A"  # String pour supporter "> X"
    product_titles: List[str] = field(default_factory=list)
    sitemap_count: int = 0
    error: Optional[str] = None
    bytes_downloaded: int = 0


@dataclass
class AnalysisResult:
    """Resultat complet de l'analyse d'un site."""
    url: str
    final_url: str = ""
    cms: str = "Unknown"
    theme: str = "Unknown"
    title: str = ""
    description: str = ""
    h1: str = ""
    currency: str = ""
    product_count: str = "N/A"
    product_titles: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_shopify(self) -> bool:
        return self.cms == "Shopify"

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour compatibilite."""
        return {
            "cms": self.cms,
            "theme": self.theme,
            "site_title": self.title,
            "site_description": self.description,
            "site_h1": self.h1,
            "currency_from_site": self.currency,
            "product_count": self.product_count,
            "thematique": "",  # Sera rempli par Gemini
            "type_produits": ";".join(self.product_titles[:10]),
            "payments": "",
            "error": self.error,
        }


# ===========================================================================
# HTTP CLIENT
# ===========================================================================

class HttpClient:
    """
    Client HTTP optimise avec:
    - Connection pooling (Session)
    - Gzip automatique
    - SSL configurable via PROXY_CA_BUNDLE
    - Retry avec exponential backoff sur 429/502/503/504
    """

    def __init__(self):
        self.session = self._create_session()
        self._setup_ssl()

    def _setup_ssl(self):
        """Configure SSL avec PROXY_CA_BUNDLE ou fallback verify=False."""
        self.ca_bundle = os.getenv("PROXY_CA_BUNDLE", "")

        if self.ca_bundle and os.path.exists(self.ca_bundle):
            self.verify = self.ca_bundle
            logger.info(f"SSL: Using CA bundle from {self.ca_bundle}")
        else:
            self.verify = False
            # Desactiver les warnings SSL en dev
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            if self.ca_bundle:
                logger.warning(f"SSL: CA bundle not found at {self.ca_bundle}, using verify=False")
            else:
                logger.info("SSL: No PROXY_CA_BUNDLE set, using verify=False")

    def _create_session(self) -> requests.Session:
        """Cree une session avec retry et connection pooling."""
        session = requests.Session()

        # Configuration retry avec exponential backoff
        retry_strategy = Retry(
            total=RETRY_MAX_ATTEMPTS,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=["GET", "HEAD"],
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers avec User-Agent aleatoire et gzip."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def get(
        self,
        url: str,
        timeout: int = TIMEOUT_HOMEPAGE,
        stream: bool = False
    ) -> Optional[requests.Response]:
        """
        Execute une requete GET avec retry automatique.

        Args:
            url: URL a fetcher
            timeout: Timeout en secondes
            stream: Si True, retourne la reponse en streaming

        Returns:
            Response ou None si erreur
        """
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=timeout,
                verify=self.verify,
                allow_redirects=True,
                stream=stream,
            )
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout: {url[:50]}...")
            return None
        except requests.exceptions.SSLError as e:
            logger.debug(f"SSL Error: {url[:50]}... - {str(e)[:30]}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"Connection Error: {url[:50]}... - {str(e)[:30]}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.debug(f"HTTP Error: {url[:50]}... - {str(e)[:30]}")
            return None
        except Exception as e:
            logger.debug(f"Request Error: {url[:50]}... - {str(e)[:30]}")
            return None

    def get_stream(
        self,
        url: str,
        timeout: int = TIMEOUT_SITEMAP,
        max_bytes: int = SITEMAP_STREAM_LIMIT_SINGLE
    ) -> Tuple[str, int]:
        """
        Telecharge une URL en streaming avec limite de bytes.

        Args:
            url: URL a fetcher
            timeout: Timeout en secondes
            max_bytes: Limite en bytes (coupe si depassee)

        Returns:
            Tuple (content, bytes_downloaded)
        """
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=timeout,
                verify=self.verify,
                allow_redirects=True,
                stream=True,
            )
            response.raise_for_status()

            chunks = []
            bytes_downloaded = 0

            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                if chunk:
                    chunks.append(chunk)
                    bytes_downloaded += len(chunk.encode('utf-8') if isinstance(chunk, str) else chunk)

                    if bytes_downloaded >= max_bytes:
                        logger.debug(f"Stream limit reached: {bytes_downloaded} bytes")
                        break

            content = ''.join(chunks) if chunks else ''
            return content, bytes_downloaded

        except Exception as e:
            logger.debug(f"Stream Error: {url[:50]}... - {str(e)[:30]}")
            return "", 0

    def close(self):
        """Ferme la session."""
        self.session.close()


# ===========================================================================
# THEME DETECTOR
# ===========================================================================

class ThemeDetector:
    """
    Detecteur de theme Shopify depuis HTML uniquement.

    Strategies (par ordre de priorite):
    1. JSON Shopify.theme dans le HTML
    2. Parsing des URLs dans les balises <link>
    3. Fallback "Unknown"

    AUCUNE requete sur les assets CSS/JS.
    """

    def detect(self, html: str) -> str:
        """
        Detecte le theme depuis le HTML.

        Args:
            html: Contenu HTML de la page

        Returns:
            Nom du theme ou "Unknown"
        """
        # Strategie 1: JSON inline
        theme = self._detect_from_json(html)
        if theme:
            return theme

        # Strategie 2: Parsing des balises <link>
        theme = self._detect_from_links(html)
        if theme:
            return theme

        return "Unknown"

    def _detect_from_json(self, html: str) -> Optional[str]:
        """Cherche le theme dans les objets JSON Shopify."""
        for pattern in THEME_JSON_PATTERNS:
            match = pattern.search(html)
            if match:
                theme_name = match.group(1).strip()
                if self._is_valid_theme_name(theme_name):
                    logger.debug(f"Theme found (JSON): {theme_name}")
                    return theme_name
        return None

    def _detect_from_links(self, html: str) -> Optional[str]:
        """Extrait le nom du theme depuis les URLs des <link> CSS."""
        # Pattern pour les liens CSS classiques
        match = THEME_LINK_PATTERN.search(html)
        if match:
            theme_name = match.group(1).strip()
            if self._is_valid_theme_name(theme_name):
                logger.debug(f"Theme found (link): {theme_name}")
                return theme_name

        # Pattern pour CDN Shopify
        match = THEME_CDN_PATTERN.search(html)
        if match:
            theme_name = match.group(1).strip()
            if self._is_valid_theme_name(theme_name):
                logger.debug(f"Theme found (CDN): {theme_name}")
                return theme_name

        return None

    def _is_valid_theme_name(self, name: str) -> bool:
        """Valide que le nom de theme est raisonnable."""
        if not name or len(name) < 2 or len(name) > 100:
            return False

        # Exclure les noms generiques
        excluded = {"theme", "style", "base", "main", "app", "vendor", "common"}
        if name.lower() in excluded:
            return False

        # Exclure les noms avec numeros seuls (ex: "theme_t_123")
        if re.match(r'^(theme[_-]?)?t?[_-]?\d+$', name, re.I):
            return False

        return True


# ===========================================================================
# SITEMAP ANALYZER
# ===========================================================================

class SitemapAnalyzer:
    """
    Analyseur de sitemap avec streaming et limites budgetaires.

    Strategies selon le nombre de sitemaps:
    - Multiple sitemaps: Estimation N × 50000, stream 50Ko du premier pour titres
    - Single sitemap: Stream jusqu'a 1MB, count reel

    Si coupe avant la fin: product_count = "> X"
    """

    def __init__(self, http_client: HttpClient):
        self.http = http_client

    def analyze(self, base_url: str, country_code: str = "FR") -> SitemapData:
        """
        Analyse le sitemap d'un site.

        Args:
            base_url: URL de base du site
            country_code: Code pays pour filtrer les sitemaps

        Returns:
            SitemapData avec count et titres
        """
        origin = self._get_origin(base_url)

        # Step 1: Recuperer le sitemap index
        sitemap_index = self._fetch_sitemap_index(origin)
        if not sitemap_index:
            return SitemapData(url=base_url, error="Sitemap not found")

        # Step 2: Trouver les sitemaps produits
        product_sitemaps = self._find_product_sitemaps(sitemap_index, country_code)

        if not product_sitemaps:
            return SitemapData(
                url=base_url,
                sitemap_count=0,
                error="No product sitemaps found"
            )

        # Step 3: Logique selon le nombre de sitemaps
        if len(product_sitemaps) > 1:
            return self._handle_multiple_sitemaps(origin, product_sitemaps)
        else:
            return self._handle_single_sitemap(origin, product_sitemaps[0])

    def _get_origin(self, url: str) -> str:
        """Extrait l'origine (scheme://host) d'une URL."""
        if not url.startswith("http"):
            url = f"https://{url}"
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _fetch_sitemap_index(self, origin: str) -> Optional[str]:
        """Recupere le contenu du sitemap index."""
        for path in ["/sitemap.xml", "/sitemap_index.xml"]:
            url = f"{origin}{path}"
            response = self.http.get(url, timeout=TIMEOUT_SITEMAP)
            if response and response.text:
                return response.text
        return None

    def _find_product_sitemaps(
        self,
        sitemap_content: str,
        country_code: str
    ) -> List[str]:
        """Trouve les URLs des sitemaps produits."""
        locs = SITEMAP_LOC_PATTERN.findall(sitemap_content)

        product_sitemaps = []
        country_lower = country_code.lower()

        for loc in locs:
            loc_lower = loc.lower()

            # Filtrer sur les sitemaps produits
            if "sitemap_products" in loc_lower or "products-sitemap" in loc_lower:
                # Priorite aux sitemaps du pays
                if f"/{country_lower}/" in loc_lower:
                    product_sitemaps.insert(0, loc)
                elif not any(f"/{lang}/" in loc_lower for lang in ["en", "de", "es", "it", "pt"]):
                    product_sitemaps.append(loc)

        return product_sitemaps

    def _handle_multiple_sitemaps(
        self,
        origin: str,
        sitemaps: List[str]
    ) -> SitemapData:
        """
        Gere le cas de multiples sitemaps produits.

        - Estimation: N × 50000
        - Stream 50Ko du premier pour extraire des titres
        """
        estimated_count = len(sitemaps) * PRODUCTS_PER_SITEMAP_ESTIMATE

        # Stream le premier sitemap pour les titres
        first_sitemap = sitemaps[0]
        content, bytes_downloaded = self.http.get_stream(
            first_sitemap,
            timeout=TIMEOUT_SITEMAP,
            max_bytes=SITEMAP_STREAM_LIMIT_MULTI
        )

        titles = self._extract_product_titles(content, max_titles=10)

        return SitemapData(
            url=origin,
            product_count=f"~{estimated_count}",
            product_titles=titles,
            sitemap_count=len(sitemaps),
            bytes_downloaded=bytes_downloaded,
        )

    def _handle_single_sitemap(
        self,
        origin: str,
        sitemap_url: str
    ) -> SitemapData:
        """
        Gere le cas d'un seul sitemap produit.

        - Stream jusqu'a 1MB
        - Count reel des <url>
        - Si coupe: "> X"
        """
        content, bytes_downloaded = self.http.get_stream(
            sitemap_url,
            timeout=TIMEOUT_SITEMAP,
            max_bytes=SITEMAP_STREAM_LIMIT_SINGLE
        )

        if not content:
            return SitemapData(url=origin, error="Failed to fetch sitemap")

        # Compter les <url>
        count = len(SITEMAP_URL_PATTERN.findall(content))

        # Si on a atteint la limite, le count est partiel
        was_truncated = bytes_downloaded >= SITEMAP_STREAM_LIMIT_SINGLE

        if was_truncated:
            product_count = f"> {count}"
        else:
            product_count = str(count)

        titles = self._extract_product_titles(content, max_titles=10)

        return SitemapData(
            url=origin,
            product_count=product_count,
            product_titles=titles,
            sitemap_count=1,
            bytes_downloaded=bytes_downloaded,
        )

    def _extract_product_titles(self, content: str, max_titles: int = 10) -> List[str]:
        """Extrait les titres de produits depuis le contenu XML."""
        titles = []

        # Pattern pour les titres dans les sitemaps Shopify
        # Format: <image:title>...</image:title> ou dans les URLs
        title_pattern = re.compile(r'<image:title>([^<]+)</image:title>', re.I)

        for match in title_pattern.finditer(content):
            title = match.group(1).strip()
            if title and title not in titles:
                titles.append(title)
                if len(titles) >= max_titles:
                    break

        # Fallback: extraire des URLs de produits
        if len(titles) < max_titles:
            url_pattern = re.compile(r'<loc>([^<]+/products/[^<]+)</loc>', re.I)
            for match in url_pattern.finditer(content):
                url = match.group(1)
                # Extraire le nom du produit de l'URL
                parts = url.rstrip('/').split('/')
                if parts:
                    product_slug = parts[-1].split('?')[0]
                    title = product_slug.replace('-', ' ').title()
                    if title and title not in titles:
                        titles.append(title)
                        if len(titles) >= max_titles:
                            break

        return titles


# ===========================================================================
# MARKET SPY - ORCHESTRATEUR PRINCIPAL
# ===========================================================================

class MarketSpy:
    """
    Analyseur optimise de sites e-commerce.

    Workflow:
    1. Pre-filtrage URL (domaines exclus)
    2. Analyse homepage (1 requete): CMS + Theme + Metadata
    3. Si Shopify: Analyse sitemap (streaming)
    4. Retourne AnalysisResult

    Usage:
        spy = MarketSpy()
        result = spy.analyze("https://example.com")

        # Ou en batch
        results = spy.analyze_batch(urls, max_workers=8)
    """

    def __init__(self):
        self.http = HttpClient()
        self.theme_detector = ThemeDetector()
        self.sitemap_analyzer = SitemapAnalyzer(self.http)

    def analyze(self, url: str, country_code: str = "FR") -> AnalysisResult:
        """
        Analyse complete d'un site.

        Args:
            url: URL du site
            country_code: Code pays pour les sitemaps

        Returns:
            AnalysisResult avec toutes les donnees
        """
        # Normaliser l'URL
        url = self._normalize_url(url)

        # Pre-filtrage
        if self._is_excluded_domain(url):
            return AnalysisResult(
                url=url,
                error="Excluded domain"
            )

        # Phase 1: Analyse homepage (1 requete)
        homepage_data = self._analyze_homepage(url)

        if homepage_data.error:
            return AnalysisResult(
                url=url,
                final_url=homepage_data.final_url,
                error=homepage_data.error
            )

        # Phase 2: Sitemap (seulement si Shopify)
        sitemap_data = None
        if homepage_data.is_shopify:
            sitemap_data = self.sitemap_analyzer.analyze(
                homepage_data.final_url or url,
                country_code
            )

        # Construire le resultat
        return AnalysisResult(
            url=url,
            final_url=homepage_data.final_url,
            cms=homepage_data.cms,
            theme=homepage_data.theme,
            title=homepage_data.title,
            description=homepage_data.description,
            h1=homepage_data.h1,
            currency=homepage_data.currency,
            product_count=sitemap_data.product_count if sitemap_data else "N/A",
            product_titles=sitemap_data.product_titles if sitemap_data else [],
        )

    def analyze_homepage_only(self, url: str) -> HomepageData:
        """
        Analyse uniquement la homepage (sans sitemap).

        Utile pour la Phase 4 du workflow (avant filtre CMS).

        Args:
            url: URL du site

        Returns:
            HomepageData
        """
        url = self._normalize_url(url)

        if self._is_excluded_domain(url):
            return HomepageData(url=url, error="Excluded domain")

        return self._analyze_homepage(url)

    def analyze_sitemap_only(
        self,
        url: str,
        country_code: str = "FR"
    ) -> SitemapData:
        """
        Analyse uniquement le sitemap.

        Utile pour la Phase 6 du workflow (apres filtre CMS).

        Args:
            url: URL du site
            country_code: Code pays

        Returns:
            SitemapData
        """
        url = self._normalize_url(url)
        return self.sitemap_analyzer.analyze(url, country_code)

    def analyze_batch(
        self,
        urls: List[str],
        country_code: str = "FR",
        max_workers: int = 8,
        homepage_only: bool = False
    ) -> List[AnalysisResult]:
        """
        Analyse un batch de sites en parallele.

        Args:
            urls: Liste d'URLs
            country_code: Code pays
            max_workers: Nombre de workers
            homepage_only: Si True, analyse seulement homepage (pas de sitemap)

        Returns:
            Liste de AnalysisResult
        """
        results = []

        def analyze_one(url: str) -> AnalysisResult:
            if homepage_only:
                data = self.analyze_homepage_only(url)
                return AnalysisResult(
                    url=url,
                    final_url=data.final_url,
                    cms=data.cms,
                    theme=data.theme,
                    title=data.title,
                    description=data.description,
                    h1=data.h1,
                    currency=data.currency,
                    error=data.error,
                )
            else:
                return self.analyze(url, country_code)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(analyze_one, url): url
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(AnalysisResult(
                        url=url,
                        error=str(e)[:100]
                    ))

        return results

    def _normalize_url(self, url: str) -> str:
        """Normalise l'URL (ajoute https si manquant)."""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url

    def _is_excluded_domain(self, url: str) -> bool:
        """Verifie si le domaine est dans la liste d'exclusion."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")

            # Verification exacte
            if domain in EXCLUDED_DOMAINS:
                return True

            # Verification avec sous-domaines
            for excluded in EXCLUDED_DOMAINS:
                if domain.endswith(f".{excluded}"):
                    return True

            return False
        except Exception:
            return False

    def _analyze_homepage(self, url: str) -> HomepageData:
        """
        Analyse la homepage et extrait toutes les donnees en 1 requete.

        Extrait:
        - URL finale (apres redirects)
        - CMS
        - Theme (si Shopify)
        - Title
        - Description
        - H1
        - Currency
        """
        response = self.http.get(url, timeout=TIMEOUT_HOMEPAGE)

        if not response:
            return HomepageData(url=url, error="Failed to fetch")

        html = response.text
        final_url = response.url

        # Detection CMS
        cms = self._detect_cms(html, dict(response.headers))

        # Detection Theme (seulement si Shopify)
        theme = "N/A"
        if cms == "Shopify":
            theme = self.theme_detector.detect(html)

        # Extraction metadata
        title = self._extract_title(html)
        description = self._extract_description(html)
        h1 = self._extract_h1(html)
        currency = self._extract_currency(html)

        return HomepageData(
            url=url,
            final_url=final_url,
            cms=cms,
            theme=theme,
            title=title,
            description=description,
            h1=h1,
            currency=currency,
            html=html,  # Conserve pour classification
        )

    def _detect_cms(self, html: str, headers: Dict[str, str]) -> str:
        """Detecte le CMS depuis le HTML et les headers."""
        html_lower = html.lower()
        headers_str = str(headers).lower()

        # Verifier les headers Shopify
        if "x-shopify" in headers_str:
            return "Shopify"

        # Verifier les patterns dans le HTML
        for cms_name, patterns in CMS_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(html_lower):
                    return cms_name

        return "Unknown"

    def _extract_title(self, html: str) -> str:
        """Extrait le <title>."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I | re.S)
        if match:
            return match.group(1).strip()[:200]
        return ""

    def _extract_description(self, html: str) -> str:
        """Extrait la meta description."""
        match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I
        )
        if match:
            return match.group(1).strip()[:400]

        # Format alternatif
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            html, re.I
        )
        if match:
            return match.group(1).strip()[:400]

        return ""

    def _extract_h1(self, html: str) -> str:
        """Extrait le premier H1."""
        match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I | re.S)
        if match:
            # Nettoyer le HTML interne
            text = re.sub(r'<[^>]+>', '', match.group(1))
            return text.strip()[:150]
        return ""

    def _extract_currency(self, html: str) -> str:
        """Extrait la devise."""
        for pattern in CURRENCY_PATTERNS:
            match = pattern.search(html)
            if match:
                return match.group(1).upper()
        return ""

    def close(self):
        """Ferme les connexions."""
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ===========================================================================
# FONCTIONS UTILITAIRES POUR INTEGRATION
# ===========================================================================

def analyze_website_v2(url: str, country_code: str = "FR") -> Dict[str, Any]:
    """
    Fonction de remplacement pour analyze_website_complete.

    Compatibilite arriere avec l'ancienne API.

    Args:
        url: URL du site
        country_code: Code pays

    Returns:
        Dict compatible avec l'ancien format
    """
    with MarketSpy() as spy:
        result = spy.analyze(url, country_code)
        return result.to_dict()


def analyze_homepage_v2(url: str) -> Dict[str, Any]:
    """
    Analyse homepage uniquement (pour Phase 4).

    Args:
        url: URL du site

    Returns:
        Dict avec cms, theme, title, description, h1, currency
    """
    with MarketSpy() as spy:
        data = spy.analyze_homepage_only(url)
        return {
            "url": data.url,
            "final_url": data.final_url,
            "cms": data.cms,
            "theme": data.theme,
            "site_title": data.title,
            "site_description": data.description,
            "site_h1": data.h1,
            "currency_from_site": data.currency,
            "is_shopify": data.is_shopify,
            "html": data.html,
            "error": data.error,
        }


def analyze_sitemap_v2(url: str, country_code: str = "FR") -> Dict[str, Any]:
    """
    Analyse sitemap uniquement (pour Phase 6 apres filtre CMS).

    Args:
        url: URL du site
        country_code: Code pays

    Returns:
        Dict avec product_count, product_titles
    """
    with MarketSpy() as spy:
        data = spy.analyze_sitemap_only(url, country_code)
        return {
            "product_count": data.product_count,
            "product_titles": data.product_titles,
            "sitemap_count": data.sitemap_count,
            "bytes_downloaded": data.bytes_downloaded,
            "error": data.error,
        }


def analyze_batch_v2(
    sites: List[Dict[str, str]],
    country_code: str = "FR",
    max_workers: int = 8,
    homepage_only: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    Analyse un batch de sites.

    Args:
        sites: Liste de {"page_id": "...", "url": "..."}
        country_code: Code pays
        max_workers: Nombre de workers paralleles
        homepage_only: Si True, analyse seulement homepage

    Returns:
        Dict {page_id: result_dict}
    """
    urls = [s.get("url", "") for s in sites]
    url_to_page_id = {s.get("url", ""): s.get("page_id", "") for s in sites}

    with MarketSpy() as spy:
        results = spy.analyze_batch(
            urls,
            country_code=country_code,
            max_workers=max_workers,
            homepage_only=homepage_only
        )

        return {
            url_to_page_id.get(r.url, r.url): r.to_dict()
            for r in results
        }
