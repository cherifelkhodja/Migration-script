"""
Module de classification automatique des sites e-commerce avec Google Gemini.

Fonctionnalites :
- Scraper optimise low-token (extraction minimale)
- Client Gemini avec batching asynchrone
- Integration avec la taxonomie configurable
"""
import os
import re
import json
import time
import asyncio
import aiohttp
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlparse
import logging
import random

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supprimer les warnings SSL pour requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constantes
MAX_CONTENT_LENGTH = 2000  # Max caracteres par site
BATCH_SIZE = 20  # Nombre de sites par requete Gemini
REQUEST_TIMEOUT = 15  # Timeout pour le scraping (reduit pour eviter les blocages)
GEMINI_TIMEOUT = 60  # Timeout pour Gemini
RATE_LIMIT_DELAY = 4.5  # Delai entre appels Gemini (15 RPM max = 4s minimum, 4.5s pour securite)

# User-Agents realistes pour le scraping
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]


@dataclass
class SiteContent:
    """Contenu extrait d'un site"""
    page_id: str
    url: str
    page_name: str = ""  # Nom de la page Facebook/Meta Ads
    title: str = ""
    description: str = ""
    keywords: str = ""
    h1: str = ""
    product_links: List[str] = None
    error: str = None

    def __post_init__(self):
        if self.product_links is None:
            self.product_links = []

    def to_text(self) -> str:
        """Convertit en texte concis pour le prompt - BASE SUR LE SITE WEB uniquement"""
        parts = []
        # Priorite au contenu du site web (pas le nom de la page)
        if self.title:
            parts.append(f"Titre: {self.title[:200]}")
        if self.description:
            parts.append(f"Description: {self.description[:400]}")
        if self.h1:
            parts.append(f"H1: {self.h1[:150]}")
        if self.keywords:
            parts.append(f"Keywords: {self.keywords[:200]}")
        if self.product_links:
            links_text = ", ".join(self.product_links[:15])
            parts.append(f"Produits: {links_text[:400]}")

        text = " | ".join(parts)
        return text[:MAX_CONTENT_LENGTH]

    def has_content(self) -> bool:
        """Verifie si on a du contenu utile du site"""
        return bool(self.title or self.description or self.h1 or self.keywords or self.product_links)


@dataclass
class ClassificationResult:
    """Resultat de classification d'un site"""
    page_id: str
    category: str
    subcategory: str
    confidence_score: float
    error: str = None


# ===========================================================================
# SCRAPER OPTIMISE (LOW TOKEN)
# ===========================================================================

def extract_site_content_sync(html: str, page_id: str, url: str, page_name: str = "") -> SiteContent:
    """
    Extrait le contenu minimal d'une page HTML (version synchrone).

    Extrait uniquement :
    - <title>
    - <meta name="description">
    - <meta name="keywords">
    - Premier <h1>
    - 10 premiers liens internes ressemblant a des produits
    """
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            return SiteContent(page_id=page_id, url=url, page_name=page_name, error=f"Parse error: {str(e)[:50]}")

    # Extraire le titre
    title = ""
    title_tag = soup.find('title')
    if title_tag and title_tag.string:
        title = title_tag.string.strip()

    # Extraire la meta description
    description = ""
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        description = meta_desc['content'].strip()

    # Extraire les meta keywords
    keywords = ""
    meta_kw = soup.find('meta', attrs={'name': 'keywords'})
    if meta_kw and meta_kw.get('content'):
        keywords = meta_kw['content'].strip()

    # Extraire le premier H1
    h1 = ""
    h1_tag = soup.find('h1')
    if h1_tag:
        h1 = h1_tag.get_text(strip=True)

    # Extraire les liens produits (heuristique)
    product_links = extract_product_links(soup, url)

    return SiteContent(
        page_id=page_id,
        url=url,
        page_name=page_name,
        title=title,
        description=description,
        keywords=keywords,
        h1=h1,
        product_links=product_links
    )


def extract_product_links(soup, base_url: str, max_links: int = 10) -> List[str]:
    """
    Extrait les textes de liens ressemblant a des produits.

    Heuristiques utilisees :
    - Liens contenant /product/, /produit/, /p/, /shop/, /collection/
    - Liens avec des prix (EUR, $, EUR)
    - Textes de liens avec des patterns produit
    """
    product_patterns = [
        r'/product[s]?/',
        r'/produit[s]?/',
        r'/p/',
        r'/shop/',
        r'/collection[s]?/',
        r'/item[s]?/',
        r'/article[s]?/',
        r'/catalog/',
    ]

    domain = urlparse(base_url).netloc
    product_texts = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        text = a_tag.get_text(strip=True)

        if not text or len(text) < 3 or len(text) > 100:
            continue

        # Verifier si c'est un lien interne
        is_internal = (
            href.startswith('/') or
            href.startswith('#') or
            domain in href
        )

        if not is_internal:
            continue

        # Verifier les patterns produit dans l'URL
        is_product_url = any(re.search(p, href, re.I) for p in product_patterns)

        # Verifier si le texte ressemble a un produit
        has_price = bool(re.search(r'[\d,\.]+\s*[€$£]|[€$£]\s*[\d,\.]+|EUR|USD', text))

        if is_product_url or has_price:
            # Nettoyer le texte
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if clean_text and clean_text not in product_texts:
                product_texts.append(clean_text)

                if len(product_texts) >= max_links:
                    break

    return product_texts


async def fetch_site_content(
    session: aiohttp.ClientSession,
    page_id: str,
    url: str,
    page_name: str = "",
    timeout: int = REQUEST_TIMEOUT,
    retries: int = 2
) -> SiteContent:
    """
    Recupere et parse le contenu d'un site de maniere asynchrone avec retry.
    """
    original_url = url

    # S'assurer que l'URL a un schema
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    last_error = None

    for attempt in range(retries + 1):
        # Headers realistes avec User-Agent aleatoire (different a chaque tentative)
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False,
                allow_redirects=True,
                max_redirects=5
            ) as response:
                if response.status != 200:
                    last_error = f"HTTP {response.status}"
                    if response.status in [403, 429, 503]:
                        # Retry sur ces erreurs
                        if attempt < retries:
                            await asyncio.sleep(1)
                            continue
                    return SiteContent(
                        page_id=page_id,
                        url=original_url,
                        page_name=page_name,
                        error=last_error
                    )

                # Limiter la taille du contenu
                content = await response.text(errors='ignore')
                if len(content) > 500000:  # 500KB max
                    content = content[:500000]

                result = extract_site_content_sync(content, page_id, original_url, page_name)

                # Log si on a trouve du contenu
                if result.has_content():
                    logger.debug(f"Scraped {original_url}: title={bool(result.title)}, desc={bool(result.description)}")
                else:
                    logger.warning(f"No content found for {original_url}")

                return result

        except asyncio.TimeoutError:
            last_error = "Timeout"
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
        except aiohttp.ClientError as e:
            last_error = f"Network: {str(e)[:40]}"
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
        except Exception as e:
            last_error = f"Error: {str(e)[:40]}"
            break

    logger.warning(f"Failed to scrape {original_url}: {last_error}")
    return SiteContent(page_id=page_id, url=original_url, page_name=page_name, error=last_error)


async def scrape_sites_batch(
    sites: List[Dict],
    max_concurrent: int = 10
) -> List[SiteContent]:
    """
    Scrape plusieurs sites en parallele (async version).
    """
    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_site_content(
                session,
                site['page_id'],
                site['url'],
                site.get('page_name', '')
            )
            for site in sites
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convertir les exceptions en SiteContent avec erreur
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(SiteContent(
                    page_id=sites[i]['page_id'],
                    url=sites[i]['url'],
                    page_name=sites[i].get('page_name', ''),
                    error=str(result)[:100]
                ))
            else:
                processed.append(result)

        return processed


# ===========================================================================
# SCRAPER SYNCHRONE AVEC REQUESTS (plus fiable sur Railway)
# ===========================================================================

def fetch_site_content_sync_requests(
    page_id: str,
    url: str,
    page_name: str = "",
    timeout: int = REQUEST_TIMEOUT,
    use_scraperapi: bool = True
) -> SiteContent:
    """
    Recupere le contenu d'un site avec requests (synchrone, plus fiable).
    Utilise ScraperAPI si configure pour eviter les blocages.
    Fallback automatique vers requete directe si ScraperAPI echoue.
    """
    from src.infrastructure.config import SCRAPER_API_KEY, SCRAPER_API_URL

    original_url = url

    # S'assurer que l'URL a un schema
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    def _make_request(use_proxy: bool) -> requests.Response:
        """Helper pour faire la requete avec ou sans proxy."""
        if use_proxy and SCRAPER_API_KEY:
            from urllib.parse import urlencode
            scraper_params = {
                "api_key": SCRAPER_API_KEY,
                "url": url,
                "render": "false",
                "country_code": "fr"
            }
            request_url = f"{SCRAPER_API_URL}?{urlencode(scraper_params)}"
            headers = {}
            req_timeout = 30
            logger.debug(f"ScraperAPI: {original_url[:50]}...")
        else:
            request_url = url
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }
            req_timeout = timeout
            if not use_proxy:
                logger.debug(f"Direct (fallback): {original_url[:50]}...")

        return requests.get(
            request_url,
            headers=headers,
            timeout=req_timeout,
            verify=False,
            allow_redirects=True
        )

    def _process_response(response: requests.Response) -> SiteContent:
        """Helper pour traiter la reponse."""
        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {url}")
            return SiteContent(
                page_id=page_id,
                url=original_url,
                page_name=page_name,
                error=f"HTTP {response.status_code}"
            )

        content = response.text
        if len(content) > 500000:
            content = content[:500000]

        result = extract_site_content_sync(content, page_id, original_url, page_name)

        if result.has_content():
            logger.info(f"OK: {original_url[:50]}... (title={bool(result.title)}, desc={bool(result.description)})")
        else:
            logger.warning(f"Vide: {original_url[:50]}...")

        return result

    # Phase 1: Essayer avec ScraperAPI si configure et active
    proxy_error = None
    if use_scraperapi and SCRAPER_API_KEY:
        try:
            response = _make_request(use_proxy=True)
            return _process_response(response)
        except requests.exceptions.RequestException as e:
            proxy_error = e
            logger.warning(f"ScraperAPI failed for {url[:50]}..., trying direct request")

    # Phase 2: Fallback vers requete directe (ou requete directe si pas de proxy)
    try:
        response = _make_request(use_proxy=False)
        return _process_response(response)
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout: {url[:50]}...")
        return SiteContent(page_id=page_id, url=original_url, page_name=page_name, error="Timeout")
    except requests.exceptions.SSLError as e:
        logger.warning(f"SSL Error: {url[:50]}... - {str(e)[:30]}")
        return SiteContent(page_id=page_id, url=original_url, page_name=page_name, error="SSL Error")
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Connection Error: {url[:50]}... - {str(e)[:30]}")
        return SiteContent(page_id=page_id, url=original_url, page_name=page_name, error="Connection Error")
    except Exception as e:
        logger.warning(f"Error: {url[:50]}... - {str(e)[:30]}")
        return SiteContent(page_id=page_id, url=original_url, page_name=page_name, error=str(e)[:50])


def scrape_sites_sync(
    sites: List[Dict],
    max_workers: int = 5
) -> List[SiteContent]:
    """
    Scrape plusieurs sites en parallele avec ThreadPoolExecutor (synchrone).

    Cette methode est plus fiable sur Railway que l'async avec aiohttp.
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_site = {
            executor.submit(
                fetch_site_content_sync_requests,
                site['page_id'],
                site['url'],
                site.get('page_name', '')
            ): site
            for site in sites
        }

        for future in as_completed(future_to_site):
            site = future_to_site[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(SiteContent(
                    page_id=site['page_id'],
                    url=site['url'],
                    page_name=site.get('page_name', ''),
                    error=str(e)[:100]
                ))

    return results


# ===========================================================================
# CLIENT GEMINI AVEC BATCHING
# ===========================================================================

class GeminiClassifier:
    """
    Client pour classifier les sites e-commerce avec Google Gemini.

    Utilise le batching pour optimiser les couts et la latence.
    """

    def __init__(self, api_key: str = None, model_name: str = None, db=None):
        """
        Initialise le client Gemini.

        Args:
            api_key: Cle API Gemini (ou variable d'env GEMINI_API_KEY)
            model_name: Nom du modele Gemini a utiliser (optionnel, lit depuis settings sinon)
            db: DatabaseManager pour recuperer les settings (optionnel)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY non configuree")

        # Recuperer le modele depuis les settings ou utiliser la valeur par defaut
        if model_name:
            self.model = model_name
        elif db:
            try:
                from src.infrastructure.persistence.database import get_app_setting, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT
                self.model = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)
            except Exception:
                self.model = "gemini-1.5-flash"  # Fallback
        else:
            self.model = "gemini-1.5-flash"  # Default model

        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        print(f"[Gemini] Utilisation du modele: {self.model}")

    def _build_system_prompt(self, taxonomy_text: str) -> str:
        """Construit le prompt systeme avec la taxonomie"""
        return f"""Tu es un expert en classification de sites e-commerce français. Ton rôle est de classifier PRÉCISÉMENT chaque site dans la bonne catégorie.

TAXONOMIE DISPONIBLE:
{taxonomy_text}

RÈGLES DE CLASSIFICATION:
1. Analyse attentivement le titre, la description, le H1 et les produits mentionnés
2. Choisis la catégorie et sous-catégorie les PLUS SPÉCIFIQUES possibles
3. NE PAS utiliser "Divers & Spécialisé/Généraliste" sauf si vraiment impossible à classifier
4. Les indices clés pour identifier la catégorie:
   - Mots dans le titre/description: "bijoux", "montres" → Bijoux & Joaillerie
   - Mots comme "vêtements", "robe", "mode" → Mode & Accessoires
   - Mots comme "smartphone", "tech", "électronique" → High-Tech
   - Mots comme "maison", "décoration", "meuble" → Maison, Jardin & Bricolage
   - Mots comme "cosmétique", "beauté", "skincare" → Beauté & Bien-être
   - Mots comme "jouet", "enfant", "bébé" → Famille & Enfants

CONFIANCE:
- 0.9-1.0: Très clair (ex: site de bijoux avec "bijoux" dans le titre)
- 0.7-0.89: Probable (indices clairs mais pas évidents)
- 0.5-0.69: Incertain mais meilleur choix
- <0.5: Vraiment difficile à classifier

FORMAT DE RÉPONSE:
Réponds UNIQUEMENT avec un tableau JSON, sans markdown, sans backticks:
[{{"id": "ID_EXACT", "category": "Catégorie", "subcategory": "Sous-catégorie", "confidence_score": 0.85}}]

IMPORTANT: Le champ "id" doit correspondre EXACTEMENT à l'ID fourni."""

    def _build_user_prompt(self, sites_data: List[SiteContent]) -> str:
        """Construit le prompt utilisateur avec les donnees des sites - CONTENU SITE UNIQUEMENT"""
        lines = ["Voici les sites e-commerce à classifier (basé sur leur contenu web) :\n"]

        for site in sites_data:
            # UNIQUEMENT le contenu du site web
            site_text = site.to_text()

            if site.has_content():
                lines.append(f"ID: {site.page_id} | {site_text}")
            else:
                # Si pas de contenu, on indique l'URL mais on ne peut pas classifier
                domain = urlparse(site.url).netloc.replace('www.', '')
                lines.append(f"ID: {site.page_id} | Site: {domain} | (contenu non disponible)")

        return "\n".join(lines)

    async def classify_batch_async(
        self,
        sites_data: List[SiteContent],
        taxonomy_text: str
    ) -> List[ClassificationResult]:
        """
        Classifie un batch de sites avec Gemini (async).
        """
        if not sites_data:
            return []

        system_prompt = self._build_system_prompt(taxonomy_text)
        user_prompt = self._build_user_prompt(sites_data)

        logger.info(f"Gemini prompt: {len(system_prompt)} chars system, {len(user_prompt)} chars user")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
                "maxOutputTokens": 4096,
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        url = f"{self.api_url}?key={self.api_key}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=GEMINI_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini API error: {response.status} - {error_text[:200]}")
                        # Retourner des resultats par defaut
                        return [
                            ClassificationResult(
                                page_id=s.page_id,
                                category="Divers & Spécialisé",
                                subcategory="Généraliste",
                                confidence_score=0.0,
                                error=f"API error: {response.status}"
                            )
                            for s in sites_data
                        ]

                    result = await response.json()
                    return self._parse_gemini_response(result, sites_data)

            except asyncio.TimeoutError:
                logger.error("Gemini API timeout")
                return [
                    ClassificationResult(
                        page_id=s.page_id,
                        category="Divers & Spécialisé",
                        subcategory="Généraliste",
                        confidence_score=0.0,
                        error="API timeout"
                    )
                    for s in sites_data
                ]
            except Exception as e:
                logger.error(f"Gemini API exception: {e}")
                return [
                    ClassificationResult(
                        page_id=s.page_id,
                        category="Divers & Spécialisé",
                        subcategory="Généraliste",
                        confidence_score=0.0,
                        error=str(e)[:100]
                    )
                    for s in sites_data
                ]

    def _parse_gemini_response(
        self,
        response: Dict,
        sites_data: List[SiteContent]
    ) -> List[ClassificationResult]:
        """Parse la reponse Gemini et extrait les classifications"""
        results = []

        try:
            # Extraire le texte de la reponse
            text = response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            # Nettoyer le texte (supprimer markdown si present)
            text = text.strip()
            if text.startswith('```'):
                # Supprimer les backticks markdown
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            # Parser le JSON
            classifications = json.loads(text)

            if not isinstance(classifications, list):
                raise ValueError("Response is not a list")

            # Mapper les resultats
            result_map = {}
            for c in classifications:
                page_id = str(c.get('id', ''))
                result_map[page_id] = ClassificationResult(
                    page_id=page_id,
                    category=c.get('category', 'Divers & Spécialisé'),
                    subcategory=c.get('subcategory', 'Généraliste'),
                    confidence_score=float(c.get('confidence_score', 0.5))
                )

            # S'assurer que tous les sites ont un resultat
            for site in sites_data:
                if site.page_id in result_map:
                    results.append(result_map[site.page_id])
                else:
                    results.append(ClassificationResult(
                        page_id=site.page_id,
                        category="Divers & Spécialisé",
                        subcategory="Généraliste",
                        confidence_score=0.0,
                        error="Not in response"
                    ))

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            # Fallback pour tous les sites
            for site in sites_data:
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    category="Divers & Spécialisé",
                    subcategory="Généraliste",
                    confidence_score=0.0,
                    error=f"JSON parse error: {str(e)[:50]}"
                ))
        except Exception as e:
            logger.error(f"Parse error: {e}")
            for site in sites_data:
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    category="Divers & Spécialisé",
                    subcategory="Généraliste",
                    confidence_score=0.0,
                    error=str(e)[:100]
                ))

        return results

    def classify_batch_sync(
        self,
        sites_data: List[SiteContent],
        taxonomy_text: str
    ) -> List[ClassificationResult]:
        """Version synchrone de classify_batch_async"""
        return asyncio.run(self.classify_batch_async(sites_data, taxonomy_text))


# ===========================================================================
# FONCTIONS D'INTEGRATION
# ===========================================================================

async def classify_pages_async(
    pages: List[Dict],
    taxonomy_text: str,
    batch_size: int = BATCH_SIZE,
    progress_callback: callable = None,
    use_sync_scraper: bool = True  # Utiliser le scraper synchrone par defaut (plus fiable)
) -> List[ClassificationResult]:
    """
    Classifie une liste de pages de maniere asynchrone.
    """
    if not pages:
        return []

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configuree")

    classifier = GeminiClassifier(api_key)
    all_results = []

    # Etape 1: Scraper tous les sites
    if progress_callback:
        progress_callback(0, len(pages), "Extraction du contenu des sites...")

    # Utiliser le scraper synchrone (requests) qui est plus fiable sur Railway
    if use_sync_scraper:
        logger.info("Utilisation du scraper synchrone (requests)")
        scraped_contents = scrape_sites_sync(pages, max_workers=5)
    else:
        logger.info("Utilisation du scraper async (aiohttp)")
        scraped_contents = await scrape_sites_batch(pages, max_concurrent=10)

    # Statistiques de scraping
    with_content = [c for c in scraped_contents if c.has_content()]
    with_errors = [c for c in scraped_contents if c.error]
    no_content = [c for c in scraped_contents if not c.has_content() and not c.error]

    logger.info(f"Scraping stats: {len(with_content)} OK, {len(with_errors)} erreurs, {len(no_content)} vides")

    # Log des erreurs detaillees
    if with_errors:
        error_types = {}
        for c in with_errors:
            err = c.error or "Unknown"
            error_types[err] = error_types.get(err, 0) + 1
        logger.info(f"Detail erreurs: {error_types}")

    # Seuls les sites avec du contenu seront classifies correctement
    valid_contents = with_content

    if progress_callback:
        progress_callback(len(pages), len(pages), f"{len(valid_contents)}/{len(pages)} sites avec contenu")

    # Etape 2: Classifier par batches
    total_batches = (len(valid_contents) + batch_size - 1) // batch_size

    for i in range(0, len(valid_contents), batch_size):
        batch = valid_contents[i:i + batch_size]
        batch_num = i // batch_size + 1

        if progress_callback:
            progress_callback(
                i,
                len(valid_contents),
                f"Classification batch {batch_num}/{total_batches}..."
            )

        batch_results = await classifier.classify_batch_async(batch, taxonomy_text)
        all_results.extend(batch_results)

        # Rate limiting: attendre 4.5s entre chaque appel Gemini (15 RPM max)
        if i + batch_size < len(valid_contents):
            logger.info(f"Rate limit: attente de {RATE_LIMIT_DELAY}s avant le prochain batch...")
            await asyncio.sleep(RATE_LIMIT_DELAY)

    # Ajouter les erreurs de scraping comme resultats par defaut
    scraped_ids = {c.page_id for c in valid_contents}
    for content in scraped_contents:
        if content.page_id not in scraped_ids:
            all_results.append(ClassificationResult(
                page_id=content.page_id,
                category="Divers & Spécialisé",
                subcategory="Généraliste",
                confidence_score=0.0,
                error=content.error
            ))

    if progress_callback:
        progress_callback(len(pages), len(pages), f"Classification terminee: {len(all_results)} pages")

    return all_results


def classify_pages_sync(
    pages: List[Dict],
    taxonomy_text: str,
    batch_size: int = BATCH_SIZE,
    progress_callback: callable = None
) -> List[ClassificationResult]:
    """Version synchrone de classify_pages_async"""
    return asyncio.run(classify_pages_async(pages, taxonomy_text, batch_size, progress_callback))


def classify_and_save(
    db,
    pages: List[Dict] = None,
    limit: int = 100,
    progress_callback: callable = None
) -> Dict:
    """
    Classifie des pages et sauvegarde les resultats en base.
    """
    # Import local pour eviter les imports circulaires
    from src.infrastructure.persistence.database import (
        get_pages_for_classification,
        update_pages_classification_batch,
        build_taxonomy_prompt,
        init_default_taxonomy
    )

    # Initialiser la taxonomie si necessaire
    init_default_taxonomy(db)

    # Recuperer la taxonomie
    taxonomy_text = build_taxonomy_prompt(db)
    if not taxonomy_text:
        return {"error": "Aucune taxonomie configuree", "classified": 0}

    # Recuperer les pages a classifier
    if pages is None:
        page_ids = None
        pages = get_pages_for_classification(db, limit=limit)
    else:
        page_ids = [p['page_id'] for p in pages]
        pages = get_pages_for_classification(db, page_ids=page_ids, limit=limit)

    if not pages:
        return {"message": "Aucune page a classifier", "classified": 0}

    # Classifier
    results = classify_pages_sync(pages, taxonomy_text, progress_callback=progress_callback)

    # Preparer les donnees pour la mise a jour
    classifications = [
        {
            "page_id": r.page_id,
            "category": r.category,
            "subcategory": r.subcategory,
            "confidence": r.confidence_score
        }
        for r in results
    ]

    # Sauvegarder
    updated = update_pages_classification_batch(db, classifications)

    # Statistiques
    errors = sum(1 for r in results if r.error)
    high_confidence = sum(1 for r in results if r.confidence_score >= 0.7)

    return {
        "total_pages": len(pages),
        "classified": updated,
        "errors": errors,
        "high_confidence": high_confidence,
        "results": results
    }


def classify_with_extracted_content(
    db,
    pages_data: List[Dict],
    progress_callback: callable = None
) -> Dict:
    """
    Classifie des pages en utilisant le contenu DEJA EXTRAIT pendant l'analyse web.
    Evite de re-scraper les sites en reutilisant les donnees de la phase 6.
    """
    # Import local pour eviter les imports circulaires
    from src.infrastructure.persistence.database import (
        update_pages_classification_batch,
        build_taxonomy_prompt,
        init_default_taxonomy
    )

    if not pages_data:
        return {"message": "Aucune page a classifier", "classified": 0}

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {"error": "GEMINI_API_KEY non configuree", "classified": 0}

    # Initialiser la taxonomie si necessaire
    init_default_taxonomy(db)

    # Recuperer la taxonomie
    taxonomy_text = build_taxonomy_prompt(db)
    if not taxonomy_text:
        return {"error": "Aucune taxonomie configuree", "classified": 0}

    # Creer les SiteContent a partir des donnees pre-extraites (sans scraping!)
    scraped_contents = []
    for page in pages_data:
        content = SiteContent(
            page_id=str(page.get('page_id', '')),
            url=page.get('url', ''),
            title=page.get('site_title', ''),
            description=page.get('site_description', ''),
            h1=page.get('site_h1', ''),
            keywords=page.get('site_keywords', ''),
            product_links=[]
        )
        scraped_contents.append(content)

    # Filtrer les sites avec du contenu
    valid_contents = [c for c in scraped_contents if c.has_content()]

    logger.info(f"Classification avec contenu pre-extrait: {len(valid_contents)}/{len(pages_data)} sites avec contenu")

    if not valid_contents:
        return {"message": "Aucun site avec contenu a classifier", "classified": 0}

    if progress_callback:
        progress_callback(0, len(valid_contents), "Classification en cours...")

    # Classifier par batches (utilise le modele configure en settings)
    classifier = GeminiClassifier(api_key, db=db)
    all_results = []
    batch_size = BATCH_SIZE

    for i in range(0, len(valid_contents), batch_size):
        batch = valid_contents[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(valid_contents) + batch_size - 1) // batch_size

        if progress_callback:
            progress_callback(i, len(valid_contents), f"Batch {batch_num}/{total_batches}")

        try:
            batch_results = classifier.classify_batch_sync(batch, taxonomy_text)
            all_results.extend(batch_results)
        except Exception as e:
            logger.error(f"Erreur batch {batch_num}: {e}")
            for content in batch:
                all_results.append(ClassificationResult(
                    page_id=content.page_id,
                    category="Divers & Spécialisé",
                    subcategory="Généraliste",
                    confidence_score=0.0,
                    error=str(e)[:100]
                ))

        # Respecter le rate limit
        if i + batch_size < len(valid_contents):
            time.sleep(RATE_LIMIT_DELAY)

    # Ajouter les sites sans contenu avec classification par defaut
    valid_ids = {c.page_id for c in valid_contents}
    for content in scraped_contents:
        if content.page_id not in valid_ids:
            all_results.append(ClassificationResult(
                page_id=content.page_id,
                category="Divers & Spécialisé",
                subcategory="Généraliste",
                confidence_score=0.0,
                error="No content"
            ))

    # Preparer les donnees pour la mise a jour
    classifications = [
        {
            "page_id": r.page_id,
            "category": r.category,
            "subcategory": r.subcategory,
            "confidence": r.confidence_score
        }
        for r in all_results
    ]

    # Sauvegarder
    updated = update_pages_classification_batch(db, classifications)

    # Statistiques
    errors = sum(1 for r in all_results if r.error)
    high_confidence = sum(1 for r in all_results if r.confidence_score >= 0.7)

    if progress_callback:
        progress_callback(len(valid_contents), len(valid_contents), f"Termine: {updated} classifiees")

    return {
        "total_pages": len(pages_data),
        "classified": updated,
        "errors": errors,
        "high_confidence": high_confidence,
        "results": all_results
    }


def classify_pages_batch(
    db,
    pages_data: List[Dict],
    progress_callback: callable = None
) -> Dict[str, Dict]:
    """
    Classifie des pages et retourne les resultats SANS mise a jour DB.
    Utilise pendant la phase 6 pour classifier immediatement apres scraping.
    """
    # Import local pour eviter les imports circulaires
    from src.infrastructure.persistence.database import build_taxonomy_prompt, init_default_taxonomy

    if not pages_data:
        return {}

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.warning("GEMINI_API_KEY non configuree - classification skippee")
        return {}

    # Initialiser la taxonomie si necessaire
    init_default_taxonomy(db)

    # Recuperer la taxonomie
    taxonomy_text = build_taxonomy_prompt(db)
    if not taxonomy_text:
        logger.warning("Aucune taxonomie configuree - classification skippee")
        return {}

    # Creer les SiteContent a partir des donnees extraites
    scraped_contents = []
    for page in pages_data:
        content = SiteContent(
            page_id=str(page.get('page_id', '')),
            url=page.get('url', ''),
            title=page.get('site_title', ''),
            description=page.get('site_description', ''),
            h1=page.get('site_h1', ''),
            keywords=page.get('site_keywords', ''),
            product_links=[]
        )
        scraped_contents.append(content)
        # Log detaille pour debug
        logger.info(f"Page {content.page_id}: title='{content.title[:50] if content.title else 'VIDE'}', has_content={content.has_content()}")

    # Filtrer les sites avec du contenu
    valid_contents = [c for c in scraped_contents if c.has_content()]

    logger.info(f"Classification batch: {len(valid_contents)}/{len(pages_data)} sites avec contenu")

    if not valid_contents:
        # Retourner classification par defaut pour tous
        return {
            str(p.get('page_id', '')): {
                "category": "Divers & Spécialisé",
                "subcategory": "Généraliste",
                "confidence": 0.0
            }
            for p in pages_data
        }

    if progress_callback:
        progress_callback(0, len(valid_contents), "Classification Gemini...")

    # Classifier par batches
    classifier = GeminiClassifier(api_key, db=db)
    all_results = []
    batch_size = BATCH_SIZE

    for i in range(0, len(valid_contents), batch_size):
        batch = valid_contents[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(valid_contents) + batch_size - 1) // batch_size

        if progress_callback:
            progress_callback(i, len(valid_contents), f"Gemini batch {batch_num}/{total_batches}")

        try:
            logger.info(f"Envoi batch {batch_num} a Gemini ({len(batch)} sites)...")
            batch_results = classifier.classify_batch_sync(batch, taxonomy_text)
            all_results.extend(batch_results)
            logger.info(f"Batch {batch_num} recu: {len(batch_results)} resultats")
            for r in batch_results[:3]:  # Log 3 premiers resultats
                logger.info(f"   -> {r.page_id}: {r.category}/{r.subcategory} (conf={r.confidence_score:.2f})")
        except Exception as e:
            logger.error(f"Erreur classification batch {batch_num}: {e}")
            # Classification par defaut en cas d'erreur
            for content in batch:
                all_results.append(ClassificationResult(
                    page_id=content.page_id,
                    category="Divers & Spécialisé",
                    subcategory="Généraliste",
                    confidence_score=0.0,
                    error=str(e)[:100]
                ))

        # Respecter le rate limit
        if i + batch_size < len(valid_contents):
            time.sleep(RATE_LIMIT_DELAY)

    # Construire le dict de resultats
    results_dict = {}

    # Ajouter les resultats classifies
    for r in all_results:
        results_dict[r.page_id] = {
            "category": r.category,
            "subcategory": r.subcategory,
            "confidence": r.confidence_score
        }

    # Ajouter classification par defaut pour les sites sans contenu
    valid_ids = {c.page_id for c in valid_contents}
    for content in scraped_contents:
        if content.page_id not in valid_ids and content.page_id not in results_dict:
            results_dict[content.page_id] = {
                "category": "Divers & Spécialisé",
                "subcategory": "Généraliste",
                "confidence": 0.0
            }

    if progress_callback:
        progress_callback(len(valid_contents), len(valid_contents), f"{len(results_dict)} classifiees")

    logger.info(f"Classification terminee: {len(results_dict)} pages")
    return results_dict
