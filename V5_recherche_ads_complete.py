#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Recherche Meta Ads SHOPIFY ONLY + Analyse Web Complète
- Filtre ≥5 ads (recherche initiale)
- Détection Shopify par HTTP
- Comptage complet par search_page_ids
- Analyse web complète (fonctions originales)
- Export 3 CSV avec devises correctes
"""

import os
import sys
import csv
import json
import time
import requests
import re
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import tldextract

try:
    from tqdm import tqdm
except ImportError:
    print("⚠️  Installation des dépendances...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm", "beautifulsoup4", "lxml", "tldextract"])
    from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# Config API Meta
BASE_URL = "https://graph.facebook.com/v24.0"
ADS_ARCHIVE = f"{BASE_URL}/ads_archive"
TIMEOUT = 20

LIMIT_SEARCH = 500
LIMIT_COUNT = 500
LIMIT_MIN = 100

# Seuils
MIN_ADS_INITIAL = 5      # Filtre préliminaire (recherche keywords)
MIN_ADS_FOR_EXPORT = 15  # CSV 1 & 3
MIN_ADS_FOR_ADS_CSV = 25 # CSV 2

# Parallélisation
WORKERS_WEB_ANALYSIS = 10
TIMEOUT_WEB = 25
TIMEOUT_SHOPIFY_CHECK = 10

# Fields Meta
FIELDS_ADS_COMPLETE = ",".join([
    "id", "page_id", "page_name", "ad_creation_time",
    "ad_creative_bodies", "ad_creative_link_captions", 
    "ad_creative_link_titles", "ad_snapshot_url",
    "eu_total_reach", "languages", "publisher_platforms",
    "target_ages", "target_gender", "beneficiary_payers",
    "currency"
])

# ─────────────────────────────────────────────────────────────────────────────
# Analyse Web (fonctions COMPLÈTES d'analyze_single_site.py)

REQUEST_TIMEOUT = 25
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

DEFAULT_PAYMENTS = [
    "Visa","Mastercard","American Express","Discover","Diners Club",
    "Apple Pay","Google Pay","Shop Pay","PayPal","Amazon Pay",
    "Klarna","Clearpay","Afterpay","Alma","Scalapay",
    "Virement SEPA","Paiement à la livraison","Crypto-monnaies",
    "Stripe","Mollie","PayPlug","2Checkout","Checkout.com"
]

TAXONOMY = {
    "Mode & Accessoires": [
        "Bijoux","Montres","Maillots de bain","Sacs à main","Lunettes",
        "Chaussures","Vêtements homme","Vêtements femme","Vêtements sport"
    ],
    "Beauté & Soins": [
        "Sérums","Crèmes","Brosses nettoyantes","Huiles essentielles","Outils de massage"
    ],
    "Santé & Bien-être": [
        "Ceintures de posture","Pistolets de massage","Patchs antidouleur",
        "Accessoires de relaxation","Appareils de fitness"
    ],
    "Maison & Décoration": [
        "Luminaires","Organisateurs","Tableaux décoratifs","Plantes artificielles","Accessoires de rangement"
    ],
    "Animaux": [
        "Colliers","Harnais","Jouets","Gamelles automatiques","Produits d'hygiène"
    ],
    "High-Tech & Gadgets": [
        "Chargeurs sans fil","Écouteurs Bluetooth","Montres connectées","Caméras","Mini projecteurs","Gadgets"
    ],
    "Bébé & Enfant": [
        "Jouets éducatifs","Veilleuses","Tapis d'éveil","Bavoirs","Articles de sécurité enfant"
    ],
    "Sport & Loisirs": [
        "Accessoires de yoga","Élastiques de musculation","Bouteilles isothermes","Sacs de sport","Gants de fitness"
    ],
    "Cuisine & Alimentation": [
        "Ustensiles","Robots de cuisine","Rangements alimentaires","Accessoires de pâtisserie","Gadgets de découpe"
    ],
}

KEYWORD_OVERRIDES = {
    "Lunettes": ["lunette","sunglasses","solaires","optique"],
    "Bijoux": ["bijou","jewelry","collier","bracelet","bague","boucles"],
    "Chaussures": ["chaussure","sneaker","basket","sandale","boots"],
    "Écouteurs Bluetooth": ["ecouteurs","earbuds","bluetooth earbuds","airpods"],
}

def ensure_url(u):
    return u if u.startswith("http") else "https://" + u

def get_web(url, timeout=REQUEST_TIMEOUT):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except:
        return None

def detect_cms(html, headers):
    h = html.lower()
    hdrs = "\n".join([f"{k}:{v}" for k,v in headers.items()]).lower()
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

# Détection thème COMPLÈTE
THEME_ASSET_CANDIDATES = [
    "/assets/theme.js", "/assets/theme.css", "/assets/base.css",
    "/assets/style.css", "/assets/theme.min.js", "/assets/theme.min.css",
]
REQUEST_SNIPPET = 200_000

def _o(u):
    p = urlparse(u); return f"{p.scheme}://{p.netloc}"

def _get_text(u):
    try:
        r = requests.get(u, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and r.text:
            return r.text
    except:
        return None
    return None

def _unique(seq):
    seen=set(); out=[]
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def _clean_theme(name):
    if not name: return None
    n = name.strip().strip("/*-—–:=> \t\"'")
    if len(n) < 2 or len(n) > 120: return None
    if re.search(r'\btheme[_-]?t?_\d+\b', n, re.I):
        return None
    return n

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

def _theme_shopify(html, base_url):
    evidence = []
    for rgx in INLINE_NAME_PATTERNS:
        m = re.search(rgx, html, re.I | re.M | re.S)
        if m:
            nm = _clean_theme(m.group(1))
            if nm:
                return nm, evidence
    
    m_id = re.search(r'/cdn/shop/t/(\d+)/', html, re.I)
    theme_id = m_id.group(1) if m_id else None
    
    origin = _o(base_url)
    soup = BeautifulSoup(html, "lxml")
    asset_urls = []
    for tag in soup.find_all(["link","script"]):
        src = tag.get("href") or tag.get("src")
        if src and (src.endswith(".css") or src.endswith(".js")) and ("/assets/" in src or "/cdn/shop/t/" in src):
            asset_urls.append(src if src.startswith("http") else urljoin(origin, src))
    
    for path in THEME_ASSET_CANDIDATES:
        asset_urls.append(urljoin(origin, path))
    
    asset_urls = _unique(asset_urls)[:25]
    
    for u in asset_urls:
        txt = _get_text(u)
        if not txt: continue
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

def detect_theme(base_url, html, headers, cms):
    if cms == "Shopify":
        name, ev = _theme_shopify(html, base_url)
    else:
        name = "NA"
    return (name or "NA"), []

def detect_payments(html, soup, terms):
    text = " ".join([soup.get_text(" ", strip=True)[:400000], html]).lower()
    found = set()
    for t in terms:
        if t.lower() in text:
            found.add(t)
    for img in soup.find_all("img"):
        for attr in ("alt","src"):
            val = (img.get(attr) or "").lower()
            for tt in terms:
                if tt.lower() in val:
                    found.add(tt)
    return sorted(found)

def _kws(label):
    base = {label}
    for k in KEYWORD_OVERRIDES.get(label, []): base.add(k)
    def deacc(s): return (s.replace("é","e").replace("è","e").replace("ê","e")
                            .replace("à","a").replace("ù","u").replace("î","i")
                            .replace("ï","i").replace("ô","o").replace("ç","c"))
    out = set()
    for b in base: out.add(b); out.add(deacc(b))
    return list(out)

def classify(text, taxonomy):
    tl = text.lower()
    theme_scores = {}
    for theme, products in taxonomy.items():
        sc = sum(1 for kw in _kws(theme) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl))
        sc += sum(1 for p in products for kw in _kws(p) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl)) * 0.25
        theme_scores[theme] = sc
    best_theme = max(theme_scores, key=theme_scores.get) if theme_scores else None
    if not best_theme or theme_scores[best_theme] == 0: return None, []
    hits = []
    for p in taxonomy[best_theme]:
        sc = sum(1 for kw in _kws(p) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', tl))
        if sc > 0: hits.append((p, sc))
    hits.sort(key=lambda x: (-x[1], x[0]))
    return best_theme, [p for p,_ in hits]

def try_get(url):
    try:
        r = get_web(url)
        if r and r.status_code == 200 and r.text:
            return r.text
    except:
        return None
    return None

def collect_text_for_classification(base_url, html):
    texts = []
    soup = BeautifulSoup(html, "lxml")
    texts.append(soup.get_text(" ", strip=True))
    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    sm = try_get(urljoin(origin, "/sitemap.xml")) or try_get(urljoin(origin, "/sitemap_index.xml"))
    if sm:
        col_urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm, re.I) if "/collections/" in u][:8]
        for u in col_urls:
            t = try_get(u)
            if t:
                texts.append(BeautifulSoup(t, "lxml").get_text(" ", strip=True))
    for path in ["/collections", "/collections/all"]:
        t = try_get(urljoin(origin, path))
        if t:
            texts.append(BeautifulSoup(t, "lxml").get_text(" ", strip=True))
    nav_text = []
    for sel in ["nav", "header", "footer", ".site-nav", ".menu"]:
        for el in soup.select(sel):
            nav_text.append(el.get_text(" ", strip=True))
    if nav_text: texts.append(" ".join(nav_text))
    return (" \n ".join(texts))[:800000]

def count_products_shopify_by_country(origin, country_code="FR"):
    """Compte produits pour un pays spécifique via sitemaps"""
    import re
    
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
    
    # 1) Chercher sitemaps avec code pays dans le nom
    product_sitemaps = [
        loc for loc in locs 
        if f"sitemap_products_{country_lower}" in loc.lower() or f"products_{country_lower}" in loc.lower()
    ]
    
    # 2) Si pas de version pays, fallback sur sitemaps globaux
    if not product_sitemaps:
        product_sitemaps = [loc for loc in locs if "sitemap_products" in loc]
    
    # 3) Si toujours rien, essayer URLs directes avec pays
    if not product_sitemaps:
        # Essayer avec code pays
        for i in range(1, 6):
            product_sitemaps.append(urljoin(origin, f"/sitemap_products_{country_lower}_{i}.xml"))
        # Fallback global
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

def extract_currency_from_html(html):
    """Extrait devise depuis le HTML Shopify"""
    m = re.search(r'Shopify\.currency\s*=\s*{[^}]*"active"\s*:\s*"([A-Z]{3})"', html)
    if m:
        return m.group(1)
    m = re.search(r'property=["\']og:price:currency["\']\s+content=["\']([A-Z]{3})["\']', html, re.I)
    if m:
        return m.group(1)
    return None

def analyze_website_complete(url, country_code="FR"):
    """Analyse COMPLÈTE avec comptage par pays"""
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

# ─────────────────────────────────────────────────────────────────────────────
# Détection Shopify HTTP

def check_shopify_http(url):
    """Vérification HTTP si site Shopify - VERSION ROBUSTE"""
    try:
        url = ensure_url(url)
        
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
    except Exception as e:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Meta API

def load_blacklist(filepath="blacklist.csv"):
    blacklist_ids = set()
    blacklist_names = set()
    
    if not os.path.exists(filepath):
        print(f"⚠️  Fichier blacklist introuvable: {filepath}")
        return blacklist_ids, blacklist_names
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            pid = row.get("page_id", "").strip()
            pname = row.get("page_name", "").strip()
            if pid:
                blacklist_ids.add(pid)
            if pname:
                blacklist_names.add(pname.lower())
    
    print(f"✅ Blacklist: {len(blacklist_ids)} page_id, {len(blacklist_names)} page_name")
    return blacklist_ids, blacklist_names

def is_blacklisted(page_id, page_name, blacklist_ids, blacklist_names):
    if str(page_id).strip() in blacklist_ids:
        return True
    if page_name and page_name.strip().lower() in blacklist_names:
        return True
    return False

def get_meta_api(url, params, token):
    params = params.copy()
    params["access_token"] = token
    
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            
            if r.status_code in (429, 500):
                sleep_time = 0.5 * (attempt + 1)
                time.sleep(sleep_time)
                continue
            
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise RuntimeError(f"Erreur réseau: {e}")
    
    raise RuntimeError("Échec après 3 tentatives")

def search_ads_complete(keyword, countries, languages, token):
    url = ADS_ARCHIVE
    params = {
        "search_terms": keyword,
        "search_type": "KEYWORD_UNORDERED",
        "ad_type": "ALL",
        "ad_active_status": "ACTIVE",
        "ad_reached_countries": json.dumps(countries),
        "languages": json.dumps(languages),
        "fields": FIELDS_ADS_COMPLETE,
        "limit": LIMIT_SEARCH
    }
    
    all_ads = []
    limit_curr = LIMIT_SEARCH
    
    pbar = tqdm(desc=f"  '{keyword}'", unit=" ads", dynamic_ncols=True)
    
    while True:
        try:
            data = get_meta_api(url, params, token)
        except RuntimeError as e:
            err_msg = str(e)
            if ("reduce" in err_msg or "code\":1" in err_msg) and limit_curr > LIMIT_MIN:
                limit_curr = max(LIMIT_MIN, limit_curr // 2)
                params["limit"] = limit_curr
                time.sleep(0.3)
                continue
            pbar.write(f"  ❌ {err_msg}")
            break
        
        batch = data.get("data", [])
        all_ads.extend(batch)
        pbar.update(len(batch))
        pbar.set_postfix({"total": len(all_ads)})
        
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        
        url = next_url
        params = {}
    
    pbar.close()
    return all_ads

def extract_website_from_ads(ads_list):
    if not ads_list:
        return ""
    
    url_counter = Counter()
    
    for ad in ads_list:
        for field in ["ad_creative_link_captions", "ad_creative_link_titles"]:
            values = ad.get(field, [])
            if not isinstance(values, list):
                values = [values] if values else []
            
            for val in values:
                if not val:
                    continue
                
                val_str = str(val).strip().lower()
                patterns = [
                    r'(?:https?://)?(?:www\.)?([a-z0-9-]+\.[a-z]{2,})',
                    r'([a-z0-9-]+\.[a-z]{2,})',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, val_str)
                    for match in matches:
                        clean = match.replace("www.", "").strip("/")
                        if len(clean) > 4 and "." in clean and not any(x in clean for x in ["facebook.com", "instagram.com", "fb.me"]):
                            url_counter[clean] += 1
    
    if not url_counter:
        return ""
    
    most_common = url_counter.most_common(1)[0][0]
    if not most_common.startswith("http"):
        most_common = "https://" + most_common
    
    return most_common

def extract_currency_from_ads(ads_list):
    """Extrait devise la plus fréquente depuis field currency"""
    if not ads_list:
        return ""
    
    currencies = [str(ad.get("currency", "")).strip().upper() for ad in ads_list if ad.get("currency")]
    if not currencies:
        return ""
    
    counter = Counter(currencies)
    return counter.most_common(1)[0][0]

def fetch_all_ads_for_page(page_id, countries, languages, token):
    """Récupère TOUTES les ads d'une page avec tous les fields"""
    params = {
        "search_page_ids": json.dumps([str(page_id)]),
        "ad_active_status": "ACTIVE",
        "ad_type": "ALL",
        "ad_reached_countries": json.dumps(countries),
        "languages": json.dumps(languages),
        "fields": FIELDS_ADS_COMPLETE,
        "limit": LIMIT_COUNT
    }
    
    url = ADS_ARCHIVE
    all_ads = []
    
    while True:
        try:
            data = get_meta_api(url, params, token)
        except:
            return all_ads, -1
        
        batch = data.get("data", [])
        all_ads.extend(batch)
        
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}
    
    return all_ads, len(all_ads)

# ─────────────────────────────────────────────────────────────────────────────
def interactive_config():
    print("\n" + "="*70)
    print("CONFIGURATION DE LA RECHERCHE (SHOPIFY ONLY)")
    print("="*70)
    
    token = input("\n📌 Token Meta (ou vide si META_ACCESS_TOKEN): ").strip()
    if not token:
        token = os.getenv("META_ACCESS_TOKEN", "").strip()
        if not token:
            print("❌ Token manquant")
            sys.exit(1)
    
    print("\n📝 Mots-clés (séparés par virgules):")
    keywords_input = input("   > ").strip()
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    
    if not keywords:
        print("❌ Aucun mot-clé")
        sys.exit(1)
    
    print("\n🌍 Codes pays (défaut: FR):")
    countries_input = input("   > ").strip()
    countries = [c.strip().upper() for c in countries_input.split(",") if c.strip()]
    if not countries:
        countries = ["FR"]
    
    print("\n🗣️  Codes langues (défaut: fr):")
    languages_input = input("   > ").strip()
    languages = [l.strip().lower() for l in languages_input.split(",") if l.strip()]
    if not languages:
        languages = ["fr"]
    
    print("\n" + "="*70)
    print(f"✅ Config: {keywords} | {countries} | {languages}")
    print(f"🛍️  Filtre: Shopify | ≥{MIN_ADS_INITIAL} ads (initial) → ≥{MIN_ADS_FOR_EXPORT} ads (export)")
    print("="*70 + "\n")
    
    return token, keywords, countries, languages

# ─────────────────────────────────────────────────────────────────────────────
def main():
    start_time = time.time()  # Démarrage du chronomètre
    
    token, keywords, countries, languages = interactive_config()
    blacklist_ids, blacklist_names = load_blacklist("blacklist.csv")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: RECHERCHE KEYWORDS
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 1: RECHERCHE PAR MOTS-CLÉS")
    print("="*70 + "\n")
    
    all_ads = []
    seen_ad_ids = set()  # Dédoublonnage des ads entre keywords
    
    for kw in keywords:
        ads = search_ads_complete(kw, countries, languages, token)
        
        # Filtrer les doublons
        unique_ads = []
        for ad in ads:
            ad_id = ad.get("id")
            if ad_id and ad_id not in seen_ad_ids:
                ad["_keyword"] = kw
                unique_ads.append(ad)
                seen_ad_ids.add(ad_id)
            elif not ad_id:
                # Si pas d'ID, on garde quand même (rare)
                ad["_keyword"] = kw
                unique_ads.append(ad)
        
        all_ads.extend(unique_ads)
        print(f"   Keyword '{kw}': {len(ads)} trouvées, {len(unique_ads)} uniques")
    
    print(f"\n📊 Total annonces uniques: {len(all_ads)}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: REGROUPEMENT PAR PAGE
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 2: REGROUPEMENT PAR PAGE")
    print("="*70)
    
    pages = {}
    name_counter = defaultdict(Counter)
    page_ads = defaultdict(list)
    
    for ad in tqdm(all_ads, desc="Regroupement", unit=" ads"):
        pid = ad.get("page_id")
        if not pid:
            continue
        
        pname = (ad.get("page_name") or "").strip()
        
        if is_blacklisted(pid, pname, blacklist_ids, blacklist_names):
            continue
        
        if pid not in pages:
            pages[pid] = {
                "page_id": pid,
                "page_name": pname,
                "website": "",
                "_ad_ids": set(),
                "keywords_matched": set(),
                "ads_found_search": 0,
                "ads_active_total": -1,
                "currency": "",
                "is_shopify": False
            }
        
        ad_id = ad.get("id")
        if ad_id:
            pages[pid]["_ad_ids"].add(ad_id)
            page_ads[pid].append(ad)
        
        if pname:
            name_counter[pid][pname] += 1
        
        kw = ad.get("_keyword", "")
        if kw:
            pages[pid]["keywords_matched"].add(kw)
    
    for pid, counter in name_counter.items():
        if counter and pid in pages:
            pages[pid]["page_name"] = counter.most_common(1)[0][0]
    
    for pid, data in pages.items():
        data["ads_found_search"] = len(data["_ad_ids"])
    
    print(f"\n✅ Pages uniques (hors blacklist): {len(pages)}")
    
    # Filtre préliminaire: ≥5 ads
    pages_filtered = {pid: data for pid, data in pages.items() 
                     if data["ads_found_search"] >= MIN_ADS_INITIAL}
    
    print(f"🎯 Pages avec ≥{MIN_ADS_INITIAL} ads (recherche initiale): {len(pages_filtered)}")
    
    if not pages_filtered:
        print(f"\n⚠️  Aucune page avec ≥{MIN_ADS_INITIAL} ads. Fin du script.")
        sys.exit(0)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: EXTRACTION WEBSITES
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 3: EXTRACTION WEBSITES")
    print("="*70)
    
    for pid, data in tqdm(pages_filtered.items(), desc="Extraction URLs", unit=" page"):
        ads = page_ads.get(pid, [])
        website = extract_website_from_ads(ads)
        data["website"] = website
    
    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    print(f"\n✅ Sites trouvés: {sites_found}/{len(pages_filtered)}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 4: DÉTECTION SHOPIFY (HTTP)
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 4: DÉTECTION SHOPIFY (vérification HTTP robuste)")
    print("="*70)
    
    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}
    
    print(f"\n🔍 Vérification HTTP pour {len(pages_with_sites)} sites...")
    print(f"⚙️  Retry automatique sur timeout/erreur")
    
    shopify_count = 0
    failed_checks = []
    
    for pid, data in tqdm(pages_with_sites.items(), desc="Shopify check", unit=" site"):
        is_shopify = check_shopify_http(data["website"])
        
        if is_shopify:
            data["is_shopify"] = True
            shopify_count += 1
        else:
            failed_checks.append((data["page_name"], data["website"]))
        
        time.sleep(0.2)
    
    pages_shopify = {pid: data for pid, data in pages_filtered.items() if data["is_shopify"]}
    
    print(f"\n🛍️  SHOPIFY détecté: {shopify_count}/{len(pages_with_sites)}")
    
    if failed_checks and len(failed_checks) <= 10:
        print(f"\n⚠️  Sites non-Shopify ou inaccessibles ({len(failed_checks)}):")
        for name, url in failed_checks[:10]:
            print(f"   - {name}: {url}")
    
    print(f"✅ Pages Shopify retenues: {len(pages_shopify)}")
    
    if not pages_shopify:
        print("\n⚠️  Aucune page Shopify trouvée. Fin du script.")
        sys.exit(0)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 5: COMPTAGE COMPLET PAR search_page_ids
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 5: COMPTAGE COMPLET (search_page_ids)")
    print("="*70)
    
    print(f"\n📊 Récupération de TOUTES les ads pour {len(pages_shopify)} pages Shopify...")
    
    pbar = tqdm(pages_shopify.items(), desc="Comptage complet", unit=" page", total=len(pages_shopify))
    
    for pid, data in pbar:
        pbar.set_postfix({"page": data['page_name'][:30]})
        
        # Récupérer TOUTES les ads de cette page
        ads_complete, count = fetch_all_ads_for_page(pid, countries, languages, token)
        
        if count > 0:
            # Remplacer les ads dans page_ads par les ads complètes
            page_ads[pid] = ads_complete
            data["ads_active_total"] = count
            
            # Extraire devise depuis les ads complètes
            currency = extract_currency_from_ads(ads_complete)
            data["currency"] = currency
        else:
            data["ads_active_total"] = -1
        
        time.sleep(0.2)
    
    pbar.close()
    
    # Filtre final: ≥15 ads
    pages_final = {pid: data for pid, data in pages_shopify.items() 
                   if data["ads_active_total"] >= MIN_ADS_FOR_EXPORT}
    
    print(f"\n🎯 Pages Shopify avec ≥{MIN_ADS_FOR_EXPORT} ads: {len(pages_final)}")
    
    if not pages_final:
        print(f"\n⚠️  Aucune page Shopify avec ≥{MIN_ADS_FOR_EXPORT} ads. Fin du script.")
        sys.exit(0)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 6: ANALYSE WEB COMPLÈTE
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print(f"PHASE 6: ANALYSE WEB (version optimisée du test)")
    print("="*70)
    
    sites_to_analyze = list(pages_final.items())
    sites_to_analyze = [(pid, data) for pid, data in sites_to_analyze if data["website"]]
    
    print(f"\n🌐 Sites Shopify à analyser: {len(sites_to_analyze)}")
    print(f"⚙️  Méthode: Simple et rapide (comme test_count_products)")
    print(f"⏱️  Durée estimée: ~{len(sites_to_analyze) * 0.3:.0f} minutes\n")
    
    web_results = {}
    
    if sites_to_analyze:
        # Boucle simple comme dans le test
        for pid, data in tqdm(sites_to_analyze, desc="Analyse sites", unit=" site"):
            # Passer le code pays pour comptage produits
            result = analyze_website_complete(data["website"], countries[0])
            web_results[pid] = result
            
            # Si devise pas trouvée dans ads, prendre celle du site
            if not pages_final[pid]["currency"] and result.get("currency_from_site"):
                pages_final[pid]["currency"] = result["currency_from_site"]
            
            # Affichage compact
            products = result.get("product_count", 0)
            if products > 0:
                tqdm.write(f"  ✅ {data['page_name']}: {products} produits ({countries[0]})")
            
            # Petite pause entre sites
            time.sleep(0.3)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 7: EXPORTS CSV
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 7: EXPORT CSV")
    print("="*70)
    
    results_dir = Path("résultats")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_time = datetime.now().isoformat()
    
    # ─── CSV 1: LISTE_PAGES (≥15 ads) ───
    csv1_path = results_dir / f"liste_pages_recherche_{timestamp}.csv"
    
    with open(csv1_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "page_id", "page_name", "lien_site", "lien_fb_ad_library",
            "thematique", "type_produits", "moyens_paiements",
            "pays", "langue", "cms", "template", "devise",
            "dernier_scan", "actif", "suivi_hebdomadaire"
        ])
        
        for pid, data in sorted(pages_final.items(), 
                               key=lambda x: x[1]["ads_active_total"], 
                               reverse=True):
            
            web = web_results.get(pid, {})
            
            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"
            
            writer.writerow([
                pid,
                data["page_name"],
                data["website"],
                fb_link,
                web.get("thematique", ""),
                web.get("type_produits", ""),
                web.get("payments", ""),
                ",".join(countries),
                ",".join(languages),
                web.get("cms", ""),
                web.get("theme", ""),
                data["currency"],
                scan_time,
                "",
                ""
            ])
    
    print(f"✅ CSV 1 (liste_pages): {csv1_path}")
    
    # ─── CSV 2: LISTE_ADS (≥25 ads uniquement) ───
    pages_for_ads_csv = {pid: data for pid, data in pages_final.items() 
                         if data["ads_active_total"] >= MIN_ADS_FOR_ADS_CSV}
    
    csv2_path = results_dir / f"liste_ads_recherche_{timestamp}.csv"
    
    with open(csv2_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "ad_id", "page_id", "page_name", "ad_creation_time",
            "ad_creative_bodies", "ad_creative_link_captions",
            "ad_creative_link_titles", "ad_snapshot_url",
            "eu_total_reach", "languages", "country",
            "publisher_platforms", "target_ages", "target_gender",
            "beneficiary_payers"
        ])
        
        ads_exported = 0
        for pid in pages_for_ads_csv.keys():
            for ad in page_ads.get(pid, []):
                def to_str(val):
                    if isinstance(val, list):
                        return ", ".join(str(v) for v in val)
                    return str(val) if val else ""
                
                writer.writerow([
                    ad.get("id", ""),
                    pid,
                    ad.get("page_name", ""),
                    ad.get("ad_creation_time", ""),
                    to_str(ad.get("ad_creative_bodies")),
                    to_str(ad.get("ad_creative_link_captions")),
                    to_str(ad.get("ad_creative_link_titles")),
                    ad.get("ad_snapshot_url", ""),
                    ad.get("eu_total_reach", ""),
                    to_str(ad.get("languages")),
                    ",".join(countries),
                    to_str(ad.get("publisher_platforms")),
                    ad.get("target_ages", ""),
                    ad.get("target_gender", ""),
                    to_str(ad.get("beneficiary_payers"))
                ])
                ads_exported += 1
    
    print(f"✅ CSV 2 (liste_ads): {csv2_path}")
    print(f"   → {ads_exported} annonces exportées (pages ≥{MIN_ADS_FOR_ADS_CSV} ads)")
    
    # ─── CSV 3: SUIVI_SITE (≥15 ads) ───
    csv3_path = results_dir / f"suivi_site_{timestamp}.csv"
    
    with open(csv3_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "cle_suivi", "nom_site", "nombre_ads_active",
            "nombre_produits", "date_scan"
        ])
        
        for pid, data in sorted(pages_final.items(),
                               key=lambda x: x[1]["ads_active_total"],
                               reverse=True):
            web = web_results.get(pid, {})
            
            writer.writerow([
                "",
                data["page_name"],
                data["ads_active_total"],
                web.get("product_count", 0),
                scan_time
            ])
    
    print(f"✅ CSV 3 (suivi_site): {csv3_path}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTIQUES FINALES
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 STATISTIQUES FINALES")
    print("="*70)
    print(f"Total annonces collectées (keywords): {len(all_ads)}")
    print(f"Pages uniques (hors blacklist): {len(pages)}")
    print(f"Pages ≥{MIN_ADS_INITIAL} ads (filtre initial): {len(pages_filtered)}")
    print(f"Pages Shopify détectées: {len(pages_shopify)}")
    print(f"Pages Shopify ≥{MIN_ADS_FOR_EXPORT} ads: {len(pages_final)}")
    print(f"Sites analysés: {len(web_results)}")
    print(f"Pages dans CSV 1 & 3: {len(pages_final)}")
    print(f"Pages dans CSV 2 (≥{MIN_ADS_FOR_ADS_CSV} ads): {len(pages_for_ads_csv)}")
    print(f"Annonces exportées (CSV 2): {ads_exported}")
    
    total_products = sum(web_results.get(pid, {}).get("product_count", 0) for pid in pages_final)
    print(f"Total produits actifs: {total_products}")
    
    devises_found = sum(1 for d in pages_final.values() if d["currency"])
    print(f"Devises trouvées: {devises_found}/{len(pages_final)}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEMPS D'EXÉCUTION
    # ═══════════════════════════════════════════════════════════════════════════
    end_time = time.time()
    total_duration = end_time - start_time
    
    hours = int(total_duration // 3600)
    minutes = int((total_duration % 3600) // 60)
    seconds = int(total_duration % 60)
    
    print("\n" + "="*70)
    print("⏱️  TEMPS D'EXÉCUTION")
    print("="*70)
    
    if hours > 0:
        print(f"Durée totale: {hours}h {minutes}m {seconds}s ({total_duration:.0f}s)")
    elif minutes > 0:
        print(f"Durée totale: {minutes}m {seconds}s ({total_duration:.0f}s)")
    else:
        print(f"Durée totale: {seconds}s")
    
    print("\n🎉 Terminé !\n")

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()