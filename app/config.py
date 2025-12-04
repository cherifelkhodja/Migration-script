"""
Configuration et constantes pour l'application Meta Ads Analyzer
"""
import os

# ─────────────────────────────────────────────────────────────────────────────
# API Meta
BASE_URL = "https://graph.facebook.com/v24.0"
ADS_ARCHIVE = f"{BASE_URL}/ads_archive"
TIMEOUT = 20

# Limites de pagination
LIMIT_SEARCH = 500
LIMIT_COUNT = 500
LIMIT_MIN = 100

# Seuils de filtrage
MIN_ADS_INITIAL = 5      # Filtre préliminaire (recherche keywords)
MIN_ADS_FOR_EXPORT = 15  # CSV 1 & 3
MIN_ADS_FOR_ADS_CSV = 25 # CSV 2

# Parallélisation
WORKERS_WEB_ANALYSIS = 10
TIMEOUT_WEB = 25
TIMEOUT_SHOPIFY_CHECK = 10

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
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

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
}

AVAILABLE_LANGUAGES = {
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
}
