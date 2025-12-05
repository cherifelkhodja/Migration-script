"""
Module de classification automatique des sites e-commerce avec Google Gemini.

Fonctionnalités :
- Scraper optimisé low-token (extraction minimale)
- Client Gemini avec batching asynchrone
- Intégration avec la taxonomie configurable
"""
import os
import re
import json
import asyncio
import aiohttp
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes
MAX_CONTENT_LENGTH = 2000  # Max caractères par site
BATCH_SIZE = 20  # Nombre de sites par requête Gemini
REQUEST_TIMEOUT = 30  # Timeout pour le scraping
GEMINI_TIMEOUT = 60  # Timeout pour Gemini
RATE_LIMIT_DELAY = 4.5  # Délai entre appels Gemini (15 RPM max = 4s minimum, 4.5s pour sécurité)


@dataclass
class SiteContent:
    """Contenu extrait d'un site"""
    page_id: str
    url: str
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
        """Convertit en texte concis pour le prompt"""
        parts = []
        if self.title:
            parts.append(f"Titre: {self.title[:200]}")
        if self.description:
            parts.append(f"Description: {self.description[:300]}")
        if self.h1:
            parts.append(f"H1: {self.h1[:100]}")
        if self.keywords:
            parts.append(f"Keywords: {self.keywords[:150]}")
        if self.product_links:
            links_text = ", ".join(self.product_links[:10])
            parts.append(f"Produits: {links_text[:300]}")

        text = " | ".join(parts)
        return text[:MAX_CONTENT_LENGTH]


@dataclass
class ClassificationResult:
    """Résultat de classification d'un site"""
    page_id: str
    category: str
    subcategory: str
    confidence_score: float
    error: str = None


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER OPTIMISÉ (LOW TOKEN)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_site_content_sync(html: str, page_id: str, url: str) -> SiteContent:
    """
    Extrait le contenu minimal d'une page HTML (version synchrone).

    Extrait uniquement :
    - <title>
    - <meta name="description">
    - <meta name="keywords">
    - Premier <h1>
    - 10 premiers liens internes ressemblant à des produits

    Args:
        html: Contenu HTML de la page
        page_id: ID de la page
        url: URL du site

    Returns:
        SiteContent avec les données extraites
    """
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            return SiteContent(page_id=page_id, url=url, error=f"Parse error: {str(e)[:50]}")

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
        title=title,
        description=description,
        keywords=keywords,
        h1=h1,
        product_links=product_links
    )


def extract_product_links(soup, base_url: str, max_links: int = 10) -> List[str]:
    """
    Extrait les textes de liens ressemblant à des produits.

    Heuristiques utilisées :
    - Liens contenant /product/, /produit/, /p/, /shop/, /collection/
    - Liens avec des prix (€, $, EUR)
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

        # Vérifier si c'est un lien interne
        is_internal = (
            href.startswith('/') or
            href.startswith('#') or
            domain in href
        )

        if not is_internal:
            continue

        # Vérifier les patterns produit dans l'URL
        is_product_url = any(re.search(p, href, re.I) for p in product_patterns)

        # Vérifier si le texte ressemble à un produit
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
    timeout: int = REQUEST_TIMEOUT
) -> SiteContent:
    """
    Récupère et parse le contenu d'un site de manière asynchrone.

    Args:
        session: Session aiohttp
        page_id: ID de la page
        url: URL à scraper
        timeout: Timeout en secondes

    Returns:
        SiteContent avec les données extraites
    """
    # S'assurer que l'URL a un schéma
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    }

    try:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
            ssl=False,
            allow_redirects=True
        ) as response:
            if response.status != 200:
                return SiteContent(
                    page_id=page_id,
                    url=url,
                    error=f"HTTP {response.status}"
                )

            # Limiter la taille du contenu
            content = await response.text(errors='ignore')
            if len(content) > 500000:  # 500KB max
                content = content[:500000]

            return extract_site_content_sync(content, page_id, url)

    except asyncio.TimeoutError:
        return SiteContent(page_id=page_id, url=url, error="Timeout")
    except aiohttp.ClientError as e:
        return SiteContent(page_id=page_id, url=url, error=f"Network error: {str(e)[:50]}")
    except Exception as e:
        return SiteContent(page_id=page_id, url=url, error=f"Error: {str(e)[:50]}")


async def scrape_sites_batch(
    sites: List[Dict],
    max_concurrent: int = 10
) -> List[SiteContent]:
    """
    Scrape plusieurs sites en parallèle.

    Args:
        sites: Liste de dicts avec page_id et url
        max_concurrent: Nombre max de requêtes simultanées

    Returns:
        Liste de SiteContent
    """
    connector = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_site_content(session, site['page_id'], site['url'])
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
                    error=str(result)[:100]
                ))
            else:
                processed.append(result)

        return processed


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT GEMINI AVEC BATCHING
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiClassifier:
    """
    Client pour classifier les sites e-commerce avec Google Gemini.

    Utilise le batching pour optimiser les coûts et la latence.
    """

    def __init__(self, api_key: str = None):
        """
        Initialise le client Gemini.

        Args:
            api_key: Clé API Gemini (ou variable d'env GEMINI_API_KEY)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY non configurée")

        self.model = "gemini-2.5-flash-lite"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def _build_system_prompt(self, taxonomy_text: str) -> str:
        """Construit le prompt système avec la taxonomie"""
        return f"""Tu es un expert en e-commerce. Analyse la liste des sites fournis (Titre, Description, H1) et classe-les selon cette taxonomie :
{taxonomy_text}

INSTRUCTION DE SORTIE :
Tu dois répondre UNIQUEMENT par un tableau JSON strict (Array of Objects), sans markdown, sans backticks.
Format attendu : [{{"id": "id_interne_site", "category": "...", "subcategory": "...", "confidence_score": 0.0-1.0}}]

IMPORTANT:
- Le champ "id" doit correspondre EXACTEMENT à l'ID fourni dans les données
- confidence_score doit être entre 0.0 et 1.0
- Si tu ne peux pas classifier un site, utilise category="Divers & Spécialisé" et subcategory="Généraliste"
- Réponds UNIQUEMENT avec le JSON, rien d'autre"""

    def _build_user_prompt(self, sites_data: List[SiteContent]) -> str:
        """Construit le prompt utilisateur avec les données des sites"""
        lines = ["Voici les sites à classifier :\n"]

        for site in sites_data:
            if site.error:
                lines.append(f"ID: {site.page_id} | URL: {site.url} | Erreur: {site.error}")
            else:
                lines.append(f"ID: {site.page_id} | {site.to_text()}")

        return "\n".join(lines)

    async def classify_batch_async(
        self,
        sites_data: List[SiteContent],
        taxonomy_text: str
    ) -> List[ClassificationResult]:
        """
        Classifie un batch de sites avec Gemini (async).

        Args:
            sites_data: Liste de SiteContent à classifier
            taxonomy_text: Texte de la taxonomie pour le prompt

        Returns:
            Liste de ClassificationResult
        """
        if not sites_data:
            return []

        system_prompt = self._build_system_prompt(taxonomy_text)
        user_prompt = self._build_user_prompt(sites_data)

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
                        # Retourner des résultats par défaut
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
        """Parse la réponse Gemini et extrait les classifications"""
        results = []
        site_ids = {s.page_id for s in sites_data}

        try:
            # Extraire le texte de la réponse
            text = response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

            # Nettoyer le texte (supprimer markdown si présent)
            text = text.strip()
            if text.startswith('```'):
                # Supprimer les backticks markdown
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            # Parser le JSON
            classifications = json.loads(text)

            if not isinstance(classifications, list):
                raise ValueError("Response is not a list")

            # Mapper les résultats
            result_map = {}
            for c in classifications:
                page_id = str(c.get('id', ''))
                result_map[page_id] = ClassificationResult(
                    page_id=page_id,
                    category=c.get('category', 'Divers & Spécialisé'),
                    subcategory=c.get('subcategory', 'Généraliste'),
                    confidence_score=float(c.get('confidence_score', 0.5))
                )

            # S'assurer que tous les sites ont un résultat
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


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS D'INTÉGRATION
# ═══════════════════════════════════════════════════════════════════════════════

async def classify_pages_async(
    pages: List[Dict],
    taxonomy_text: str,
    batch_size: int = BATCH_SIZE,
    progress_callback: callable = None
) -> List[ClassificationResult]:
    """
    Classifie une liste de pages de manière asynchrone.

    Args:
        pages: Liste de dicts avec page_id et url
        taxonomy_text: Texte de la taxonomie
        batch_size: Taille des batches pour Gemini
        progress_callback: Callback(current, total, message)

    Returns:
        Liste de ClassificationResult
    """
    if not pages:
        return []

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurée")

    classifier = GeminiClassifier(api_key)
    all_results = []

    # Étape 1: Scraper tous les sites
    if progress_callback:
        progress_callback(0, len(pages), "Extraction du contenu des sites...")

    scraped_contents = await scrape_sites_batch(pages, max_concurrent=10)

    # Filtrer les contenus valides
    valid_contents = [c for c in scraped_contents if not c.error or c.title or c.description]

    if progress_callback:
        progress_callback(len(pages), len(pages), f"{len(valid_contents)} sites analysés")

    # Étape 2: Classifier par batches
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

    # Ajouter les erreurs de scraping comme résultats par défaut
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
        progress_callback(len(pages), len(pages), f"Classification terminée: {len(all_results)} pages")

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
    Classifie des pages et sauvegarde les résultats en base.

    Args:
        db: DatabaseManager
        pages: Liste de pages à classifier (ou None pour les non classifiées)
        limit: Limite si pages=None
        progress_callback: Callback de progression

    Returns:
        Dict avec les statistiques
    """
    from app.database import (
        get_pages_for_classification,
        update_pages_classification_batch,
        build_taxonomy_prompt,
        init_default_taxonomy
    )

    # Initialiser la taxonomie si nécessaire
    init_default_taxonomy(db)

    # Récupérer la taxonomie
    taxonomy_text = build_taxonomy_prompt(db)
    if not taxonomy_text:
        return {"error": "Aucune taxonomie configurée", "classified": 0}

    # Récupérer les pages à classifier
    if pages is None:
        page_ids = None
        pages = get_pages_for_classification(db, limit=limit)
    else:
        page_ids = [p['page_id'] for p in pages]
        pages = get_pages_for_classification(db, page_ids=page_ids, limit=limit)

    if not pages:
        return {"message": "Aucune page à classifier", "classified": 0}

    # Classifier
    results = classify_pages_sync(pages, taxonomy_text, progress_callback=progress_callback)

    # Préparer les données pour la mise à jour
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
