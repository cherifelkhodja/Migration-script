"""
Configuration et constantes pour l'application Meta Ads Analyzer
"""
import os

# ─────────────────────────────────────────────────────────────────────────────
# Base de données PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/meta_ads"
)

# Seuils pour la sauvegarde en BDD
MIN_ADS_SUIVI = 10     # Minimum ads pour table suivi_page
MIN_ADS_LISTE = 20     # Minimum ads pour table liste_ads_recherche

# ─────────────────────────────────────────────────────────────────────────────
# API Meta
BASE_URL = "https://graph.facebook.com/v24.0"
ADS_ARCHIVE = f"{BASE_URL}/ads_archive"
TIMEOUT = 20

# Limites de pagination
LIMIT_SEARCH = 1000    # Limite max par requête (pagination automatique si plus)
LIMIT_COUNT = 1000     # Limite pour comptage des ads
LIMIT_MIN = 100

# Seuils de filtrage
MIN_ADS_INITIAL = 1      # Filtre préliminaire (recherche keywords)
MIN_ADS_FOR_EXPORT = 15  # CSV 1 & 3
MIN_ADS_FOR_ADS_CSV = 25 # CSV 2

# Seuils d'états (basés sur le nombre d'ads actives)
# Format: {"état": seuil_minimum}
DEFAULT_STATE_THRESHOLDS = {
    "XS": 1,      # 1-9 ads
    "S": 10,      # 10-19 ads
    "M": 20,      # 20-34 ads
    "L": 35,      # 35-79 ads
    "XL": 80,     # 80-149 ads
    "XXL": 150,   # 150+ ads
}

# ─────────────────────────────────────────────────────────────────────────────
# Critères Winning Ads
# Format: liste de tuples (max_age_days, min_reach)
# Une ad est "winning" si elle valide au moins un de ces critères
WINNING_AD_CRITERIA = [
    (4, 15000),    # ≤4 jours et >15k reach
    (5, 20000),    # ≤5 jours et >20k reach
    (6, 30000),    # ≤6 jours et >30k reach
    (7, 40000),    # ≤7 jours et >40k reach
    (8, 50000),    # ≤8 jours et >50k reach
    (15, 100000),  # ≤15 jours et >100k reach
    (22, 200000),  # ≤22 jours et >200k reach
    (29, 400000),  # ≤29 jours et >400k reach
]

# Parallélisation
WORKERS_WEB_ANALYSIS = 5  # Réduit pour éviter les bans (était 10)
TIMEOUT_WEB = 25
TIMEOUT_SHOPIFY_CHECK = 10

# ─────────────────────────────────────────────────────────────────────────────
# Throttling API (délais pour éviter les rate limits)
# Meta API
META_DELAY_BETWEEN_KEYWORDS = 1.5      # Secondes entre chaque mot-clé (avec proxy)
META_DELAY_SEQUENTIAL_NO_PROXY = 3.5   # Délai plus long sans proxy (protège le token unique)
META_DELAY_BETWEEN_PAGES = 0.3         # Secondes entre chaque page de pagination
META_DELAY_BETWEEN_BATCHES = 0.5       # Secondes entre chaque batch de 10 pages
META_DELAY_ON_ERROR = 2.0              # Délai supplémentaire après une erreur

# Recherche parallèle par keywords
META_PARALLEL_ENABLED = True           # Activer la recherche parallèle si proxies disponibles
META_MIN_DELAY_BETWEEN_PARALLEL = 0.5  # Délai minimum entre lancements parallèles

# Web/Shopify scraping
WEB_DELAY_BETWEEN_REQUESTS = 0.5       # Secondes entre chaque requête web
WEB_DELAY_CMS_CHECK = 0.3              # Délai entre les checks CMS
WEB_MAX_CONCURRENT = 3                 # Max requêtes simultanées (réduit de 5)

# Adaptative throttling (augmente les délais si rate limits détectés)
THROTTLE_MULTIPLIER_ON_RATE_LIMIT = 2.0  # Multiplie les délais si rate limit

# Fields Meta API
FIELDS_ADS_COMPLETE = ",".join([
    "id", "page_id", "page_name", "ad_creation_time",
    "ad_creative_bodies", "ad_creative_link_captions",
    "ad_creative_link_titles", "ad_snapshot_url",
    "eu_total_reach", "languages", "publisher_platforms",
    "target_ages", "target_gender", "beneficiary_payers",
    "currency"
])

# ─────────────────────────────────────────────────────────────────────────────
# Analyse Web
REQUEST_TIMEOUT = 25

# ScraperAPI pour proxy (optionnel - si pas de clé, requêtes directes)
# Configurer SCRAPER_API_KEY dans les variables d'environnement Railway
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")
SCRAPER_API_URL = "http://api.scraperapi.com"

# Proxy ScraperAPI pour les appels API (format: http://scraperapi:KEY@proxy-server.scraperapi.com:8001)
def get_scraperapi_proxy() -> str:
    """Retourne l'URL du proxy ScraperAPI pour les appels API"""
    if SCRAPER_API_KEY:
        return f"http://scraperapi:{SCRAPER_API_KEY}@proxy-server.scraperapi.com:8001"
    return ""

# User-Agents pour rotation (éviter les bans)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]

def get_random_headers() -> dict:
    """Retourne des headers avec un User-Agent aléatoire"""
    import random
    return {"User-Agent": random.choice(USER_AGENTS)}


def get_proxied_url(url: str) -> tuple[str, dict]:
    """
    Retourne l'URL et les headers à utiliser pour la requête.
    Si ScraperAPI est configuré, utilise le proxy.
    Sinon, requête directe avec User-Agent aléatoire.

    Returns:
        tuple: (url_to_use, headers_to_use)
    """
    import random
    from urllib.parse import urlencode

    if SCRAPER_API_KEY:
        # Utiliser ScraperAPI
        params = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "render": "false",  # Pas besoin de JS rendering
        }
        proxy_url = f"{SCRAPER_API_URL}?{urlencode(params)}"
        return proxy_url, {}  # ScraperAPI gère les headers
    else:
        # Requête directe avec rotation User-Agent
        return url, {"User-Agent": random.choice(USER_AGENTS)}


def is_proxy_enabled() -> bool:
    """Vérifie si le proxy ScraperAPI est activé"""
    return bool(SCRAPER_API_KEY)


# Headers par défaut (pour compatibilité)
HEADERS = {"User-Agent": USER_AGENTS[0]}

DEFAULT_PAYMENTS = [
    "Visa", "Mastercard", "American Express", "Discover", "Diners Club",
    "Apple Pay", "Google Pay", "Shop Pay", "PayPal", "Amazon Pay",
    "Klarna", "Clearpay", "Afterpay", "Alma", "Scalapay",
    "Virement SEPA", "Paiement à la livraison", "Crypto-monnaies",
    "Stripe", "Mollie", "PayPlug", "2Checkout", "Checkout.com"
]

TAXONOMY = {
    "Mode & Accessoires": [
        "Bijoux", "Montres", "Maillots de bain", "Sacs à main", "Lunettes",
        "Chaussures", "Vêtements homme", "Vêtements femme", "Vêtements sport"
    ],
    "Beauté & Soins": [
        "Sérums", "Crèmes", "Brosses nettoyantes", "Huiles essentielles", "Outils de massage"
    ],
    "Santé & Bien-être": [
        "Ceintures de posture", "Pistolets de massage", "Patchs antidouleur",
        "Accessoires de relaxation", "Appareils de fitness"
    ],
    "Maison & Décoration": [
        "Luminaires", "Organisateurs", "Tableaux décoratifs", "Plantes artificielles", "Accessoires de rangement"
    ],
    "Animaux": [
        "Colliers", "Harnais", "Jouets", "Gamelles automatiques", "Produits d'hygiène"
    ],
    "High-Tech & Gadgets": [
        "Chargeurs sans fil", "Écouteurs Bluetooth", "Montres connectées", "Caméras", "Mini projecteurs", "Gadgets"
    ],
    "Bébé & Enfant": [
        "Jouets éducatifs", "Veilleuses", "Tapis d'éveil", "Bavoirs", "Articles de sécurité enfant"
    ],
    "Sport & Loisirs": [
        "Accessoires de yoga", "Élastiques de musculation", "Bouteilles isothermes", "Sacs de sport", "Gants de fitness"
    ],
    "Cuisine & Alimentation": [
        "Ustensiles", "Robots de cuisine", "Rangements alimentaires", "Accessoires de pâtisserie", "Gadgets de découpe"
    ],
}

KEYWORD_OVERRIDES = {
    "Lunettes": ["lunette", "sunglasses", "solaires", "optique"],
    "Bijoux": ["bijou", "jewelry", "collier", "bracelet", "bague", "boucles"],
    "Chaussures": ["chaussure", "sneaker", "basket", "sandale", "boots"],
    "Écouteurs Bluetooth": ["ecouteurs", "earbuds", "bluetooth earbuds", "airpods"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Patterns pour détection de thème
THEME_ASSET_CANDIDATES = [
    "/assets/theme.js", "/assets/theme.css", "/assets/base.css",
    "/assets/style.css", "/assets/theme.min.js", "/assets/theme.min.css",
]
REQUEST_SNIPPET = 200_000

# Patterns regex (chaînes brutes)
INLINE_NAME_PATTERNS = [
    r'Shopify\.theme\s*=\s*{[^}]*?\bname\s*:\s*["\']([^"\']+)["\']',
    r'Shopify\.theme\.name\s*=\s*["\']([^"\']+)["\']',
    r'data-theme-name\s*=\s*["\']([^"\']+)["\']',
    r'data-theme\s*=\s*["\']([^"\']+)["\']',
    r'theme_name\s*[:=]\s*["\']([^"\']+)["\']',
]

ASSET_HEADER_PATTERNS = [
    r'(?im)^\s*/\*+\s*(?:theme|theme name)\s*[:=-]?\s*([^\*/]{2,120})\*+/',
    r'(?im)^\s*//\s*(?:theme|theme name)\s*[:=-]?\s*([^\n<"\*]{2,120})$',
    r'Shopify\.theme\s*=\s*{[^}]*?\bname\s*:\s*["\']([^"\']+)["\']',
]

# ─────────────────────────────────────────────────────────────────────────────
# PATTERNS REGEX PRÉ-COMPILÉS (performance)
import re

# Patterns pré-compilés pour détection de thème
COMPILED_INLINE_PATTERNS = [re.compile(p, re.I | re.M | re.S) for p in INLINE_NAME_PATTERNS]
COMPILED_ASSET_PATTERNS = [re.compile(p, re.I | re.M) for p in ASSET_HEADER_PATTERNS]
COMPILED_THEME_ID_PATTERN = re.compile(r'/cdn/shop/t/(\d+)/', re.I)
COMPILED_THEME_CLEAN_PATTERN = re.compile(r'\btheme[_-]?t?_\d+\b', re.I)

# Patterns pré-compilés pour extraction URL des ads
VALID_TLDS_PATTERN = (
    "com|net|org|co|io|app|dev|me|info|biz|"
    "shop|store|boutique|buy|sale|deals|"
    "fr|de|es|it|pt|nl|be|ch|at|lu|uk|ie|pl|se|no|dk|fi|"
    "ca|us|au|nz|br|mx|ar|"
    "online|site|website|web|live|world|tech|fashion|beauty|style|fit|health|life"
)

COMPILED_URL_PATTERNS = [
    # URL complète avec protocole
    re.compile(r'https?://(?:www\.)?([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})'),
    # Domaine avec www
    re.compile(r'www\.([a-z0-9][-a-z0-9]*(?:\.[a-z0-9][-a-z0-9]*)*\.[a-z]{2,})'),
    # Domaine simple (mot.extension)
    re.compile(r'\b([a-z0-9][-a-z0-9]{1,}\.(?:' + VALID_TLDS_PATTERN + r'))\b'),
    # Domaine avec sous-domaine
    re.compile(r'\b([a-z0-9][-a-z0-9]*\.[a-z0-9][-a-z0-9]*\.(?:com|net|org|co|io|fr|de|es|it|uk))\b'),
]

# Pattern pour valider domaine final
COMPILED_DOMAIN_VALIDATOR = re.compile(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}')
COMPILED_CAPTION_DOMAIN = re.compile(r'^[a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2,})?$')

# Patterns pour sitemap
COMPILED_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)
COMPILED_SITEMAP_URL_TAG = re.compile(r"<url>")
COMPILED_SITEMAP_LANG_PREFIX = re.compile(r'^/([a-z]{2})(?:-[a-z]{2})?/')

# Patterns pour extraction de devise
COMPILED_CURRENCY_SHOPIFY = re.compile(r'Shopify\.currency\s*=\s*{[^}]*"active"\s*:\s*"([A-Z]{3})"')
COMPILED_CURRENCY_OG = re.compile(r'property=["\']og:price:currency["\']\s+content=["\']([A-Z]{3})["\']', re.I)

# Limite sitemap (optimisation mémoire)
MAX_SITEMAPS_TO_PARSE = 10
MAX_PRODUCTS_FROM_SITEMAP = 5000

# ─────────────────────────────────────────────────────────────────────────────
# Pays et langues par défaut
DEFAULT_COUNTRIES = ["FR"]
DEFAULT_LANGUAGES = ["fr"]

# Liste des pays disponibles
AVAILABLE_COUNTRIES = {
    "FR": "France",
    "BE": "Belgique",
    "CH": "Suisse",
    "CA": "Canada",
    "US": "États-Unis",
    "GB": "Royaume-Uni",
    "DE": "Allemagne",
    "ES": "Espagne",
    "IT": "Italie",
    "PT": "Portugal",
    "NL": "Pays-Bas",
    "AT": "Autriche",
    "LU": "Luxembourg",
    "PL": "Pologne",
}

AVAILABLE_LANGUAGES = {
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
}
