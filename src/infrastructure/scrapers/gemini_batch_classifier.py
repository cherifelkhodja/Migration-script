"""
Gemini Batch Classifier - Classification IA optimisee par batch.

Optimisations:
- Batch de 10 sites max (evite hallucinations)
- custom_id unique par site pour eviter desynchronisation
- Fallback unitaire si erreur batch
- Rate limiting integre

Usage:
    classifier = GeminiBatchClassifier(api_key)
    results = classifier.classify_batch(sites_data)
"""

import os
import re
import json
import time
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================================================================
# CONFIGURATION
# ===========================================================================

# Taille max du batch (au-dela, risque d'hallucination)
MAX_BATCH_SIZE = 10

# Rate limiting (Gemini Flash: 15 RPM)
RATE_LIMIT_DELAY = 4.5  # secondes entre appels

# Timeout
GEMINI_TIMEOUT = 60

# Modele par defaut (charge depuis BDD si disponible)
DEFAULT_MODEL = "gemini-2.5-flash-lite"


# ===========================================================================
# DATA CLASSES
# ===========================================================================

@dataclass
class SiteData:
    """Donnees d'un site pour classification."""
    page_id: str
    url: str = ""
    title: str = ""
    description: str = ""
    h1: str = ""
    product_titles: List[str] = None

    def __post_init__(self):
        if self.product_titles is None:
            self.product_titles = []

    def to_prompt_text(self) -> str:
        """Formate les donnees pour le prompt (URL + metadata uniquement)."""
        parts = []
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.title:
            parts.append(f"Title: {self.title[:200]}")
        if self.description:
            parts.append(f"Description: {self.description[:300]}")
        if self.h1:
            parts.append(f"H1: {self.h1[:100]}")
        # Note: product_titles n'est plus utilise pour la classification
        return "\n".join(parts) if parts else "(no content)"

    def has_content(self) -> bool:
        """Verifie si on a assez de contenu pour classifier."""
        return bool(self.url or self.title or self.description or self.h1)


@dataclass
class ClassificationResult:
    """Resultat de classification."""
    page_id: str
    category: str = "Divers & Spécialisé"
    subcategory: str = "Généraliste"
    confidence: float = 0.0
    error: Optional[str] = None


# ===========================================================================
# GEMINI BATCH CLASSIFIER
# ===========================================================================

class GeminiBatchClassifier:
    """
    Classificateur Gemini avec batching optimise.

    Features:
    - Batch de 10 sites max pour eviter les hallucinations
    - custom_id pour chaque site (evite desynchronisation)
    - Fallback unitaire si le batch echoue
    - Rate limiting automatique
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        taxonomy_text: str = None
    ):
        """
        Initialise le classificateur.

        Args:
            api_key: Cle API Gemini (ou env GEMINI_API_KEY)
            model: Nom du modele (defaut: gemini-1.5-flash)
            taxonomy_text: Taxonomie pour la classification
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY non configuree")

        self.model = model or DEFAULT_MODEL
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.taxonomy_text = taxonomy_text or self._get_default_taxonomy()

        logger.info(f"GeminiBatchClassifier initialized with model: {self.model}")

    def classify_sites(
        self,
        sites: List[SiteData],
        progress_callback: callable = None
    ) -> List[ClassificationResult]:
        """
        Classifie une liste de sites par batches.

        Args:
            sites: Liste de SiteData
            progress_callback: Callback(current, total, message)

        Returns:
            Liste de ClassificationResult
        """
        if not sites:
            return []

        all_results = []
        total_batches = (len(sites) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE

        for i in range(0, len(sites), MAX_BATCH_SIZE):
            batch = sites[i:i + MAX_BATCH_SIZE]
            batch_num = i // MAX_BATCH_SIZE + 1

            if progress_callback:
                progress_callback(i, len(sites), f"Classification batch {batch_num}/{total_batches}")

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} sites)")

            # Essayer le batch
            batch_results = self._classify_batch(batch)

            # Verifier si le batch a reussi
            if self._batch_has_errors(batch_results, batch):
                logger.warning(f"Batch {batch_num} has errors, retrying individually")
                batch_results = self._classify_individually(batch)

            all_results.extend(batch_results)

            # Rate limiting entre les batches
            if i + MAX_BATCH_SIZE < len(sites):
                logger.debug(f"Rate limit: waiting {RATE_LIMIT_DELAY}s")
                time.sleep(RATE_LIMIT_DELAY)

        if progress_callback:
            progress_callback(len(sites), len(sites), f"Classification terminee: {len(all_results)} sites")

        return all_results

    def classify_dict(
        self,
        sites_data: List[Dict[str, Any]],
        progress_callback: callable = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Version dict pour compatibilite avec l'existant.

        Args:
            sites_data: Liste de {"page_id", "url", "site_title", ...}
            progress_callback: Callback

        Returns:
            Dict {page_id: {"category", "subcategory", "confidence"}}
        """
        # Convertir en SiteData
        sites = []
        for data in sites_data:
            site = SiteData(
                page_id=str(data.get("page_id", "")),
                url=data.get("url", ""),
                title=data.get("site_title", ""),
                description=data.get("site_description", ""),
                h1=data.get("site_h1", ""),
                product_titles=data.get("product_titles", []),
            )
            sites.append(site)

        # Classifier
        results = self.classify_sites(sites, progress_callback)

        # Convertir en dict
        return {
            r.page_id: {
                "category": r.category,
                "subcategory": r.subcategory,
                "confidence": r.confidence,
            }
            for r in results
        }

    def _classify_batch(self, sites: List[SiteData]) -> List[ClassificationResult]:
        """Classifie un batch de sites."""
        # Filtrer les sites avec contenu
        sites_with_content = [s for s in sites if s.has_content()]

        if not sites_with_content:
            return [
                ClassificationResult(page_id=s.page_id, error="No content")
                for s in sites
            ]

        # Construire le prompt
        prompt = self._build_batch_prompt(sites_with_content)

        # Appeler Gemini
        try:
            response = self._call_gemini(prompt)
            results = self._parse_response(response, sites_with_content)

            # Ajouter les resultats par defaut pour les sites sans contenu
            result_ids = {r.page_id for r in results}
            for site in sites:
                if site.page_id not in result_ids:
                    results.append(ClassificationResult(
                        page_id=site.page_id,
                        error="No content"
                    ))

            return results

        except Exception as e:
            logger.error(f"Batch classification error: {e}")
            return [
                ClassificationResult(page_id=s.page_id, error=str(e)[:100])
                for s in sites
            ]

    def _classify_individually(self, sites: List[SiteData]) -> List[ClassificationResult]:
        """Fallback: classifie chaque site individuellement."""
        results = []

        for site in sites:
            if not site.has_content():
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    error="No content"
                ))
                continue

            try:
                prompt = self._build_single_prompt(site)
                response = self._call_gemini(prompt)
                result = self._parse_single_response(response, site)
                results.append(result)

                # Rate limit
                time.sleep(RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Individual classification error for {site.page_id}: {e}")
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    error=str(e)[:100]
                ))

        return results

    def _batch_has_errors(
        self,
        results: List[ClassificationResult],
        expected_sites: List[SiteData]
    ) -> bool:
        """Verifie si le batch a des erreurs necessitant un retry."""
        if not results:
            return True

        # Verifier le count
        expected_with_content = sum(1 for s in expected_sites if s.has_content())
        actual_count = sum(1 for r in results if not r.error)

        if actual_count < expected_with_content * 0.8:  # 80% minimum
            return True

        return False

    def _build_batch_prompt(self, sites: List[SiteData]) -> str:
        """Construit le prompt pour un batch."""
        input_section = "\n---\n".join([
            f"ID: SITE_{i:02d}\nPage_ID: {site.page_id}\n{site.to_prompt_text()}"
            for i, site in enumerate(sites, 1)
        ])

        return f"""Tu es un expert E-commerce. Analyse ces sites web et classifie-les par thematique.
Tu recois pour chaque site: URL, Title, Description, H1.
Renvoie UNIQUEMENT une liste JSON d'objets, sans markdown, sans backticks.

TAXONOMIE DISPONIBLE:
{self.taxonomy_text}

SITES A CLASSIFIER:
---
{input_section}
---

OUTPUT FORMAT ATTENDU (JSON strict):
[
  {{"id": "SITE_01", "page_id": "123456", "niche": "Categorie", "subcategory": "Sous-categorie", "confidence": 0.85}},
  {{"id": "SITE_02", "page_id": "789012", "niche": "Categorie", "subcategory": "Sous-categorie", "confidence": 0.75}}
]

REGLES:
1. Analyse l'URL, le titre, la description et le H1 pour determiner la thematique
2. Le champ "id" doit correspondre EXACTEMENT a l'ID fourni (SITE_01, SITE_02, etc.)
3. Le champ "page_id" doit correspondre EXACTEMENT au Page_ID fourni
4. Choisis la categorie la plus SPECIFIQUE possible basee sur les metadonnees
5. Confidence: 0.9+ si tres clair, 0.7-0.89 si probable, 0.5-0.69 si incertain
6. Si impossible a classifier: niche="Divers & Specialise", subcategory="Generaliste"

IMPORTANT: Renvoie EXACTEMENT {len(sites)} objets JSON, un pour chaque site."""

    def _build_single_prompt(self, site: SiteData) -> str:
        """Construit le prompt pour un site unique."""
        return f"""Tu es un expert E-commerce. Classifie ce site web par thematique.
Tu recois: URL, Title, Description, H1.
Renvoie UNIQUEMENT un objet JSON, sans markdown, sans backticks.

TAXONOMIE DISPONIBLE:
{self.taxonomy_text}

SITE A CLASSIFIER:
Page_ID: {site.page_id}
{site.to_prompt_text()}

OUTPUT FORMAT ATTENDU (JSON strict):
{{"page_id": "{site.page_id}", "niche": "Categorie", "subcategory": "Sous-categorie", "confidence": 0.85}}

REGLES:
1. Analyse l'URL, le titre, la description et le H1 pour determiner la thematique
2. Le champ "page_id" doit etre EXACTEMENT "{site.page_id}"
3. Choisis la categorie la plus SPECIFIQUE possible basee sur les metadonnees
4. Confidence: 0.9+ si tres clair, 0.7-0.89 si probable, 0.5-0.69 si incertain"""

    def _call_gemini(self, prompt: str) -> Dict:
        """Appelle l'API Gemini."""
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
                "maxOutputTokens": 4096,
            }
        }

        url = f"{self.api_url}?key={self.api_key}"

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=GEMINI_TIMEOUT
        )

        if response.status_code != 200:
            raise Exception(f"Gemini API error: {response.status_code} - {response.text[:200]}")

        return response.json()

    def _parse_response(
        self,
        response: Dict,
        sites: List[SiteData]
    ) -> List[ClassificationResult]:
        """Parse la reponse batch de Gemini."""
        results = []

        try:
            text = response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Nettoyer le JSON
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            classifications = json.loads(text)

            if not isinstance(classifications, list):
                raise ValueError("Response is not a list")

            # Mapper par page_id
            page_id_map = {str(c.get("page_id", "")): c for c in classifications}

            for site in sites:
                if site.page_id in page_id_map:
                    c = page_id_map[site.page_id]
                    results.append(ClassificationResult(
                        page_id=site.page_id,
                        category=c.get("niche", "Divers & Spécialisé"),
                        subcategory=c.get("subcategory", "Généraliste"),
                        confidence=float(c.get("confidence", 0.5)),
                    ))
                else:
                    # Essayer de matcher par ID (SITE_XX)
                    for c in classifications:
                        c_page_id = c.get("page_id", "")
                        if str(c_page_id) == site.page_id:
                            results.append(ClassificationResult(
                                page_id=site.page_id,
                                category=c.get("niche", "Divers & Spécialisé"),
                                subcategory=c.get("subcategory", "Généraliste"),
                                confidence=float(c.get("confidence", 0.5)),
                            ))
                            break
                    else:
                        results.append(ClassificationResult(
                            page_id=site.page_id,
                            error="Not found in response"
                        ))

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            for site in sites:
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    error=f"JSON parse error"
                ))
        except Exception as e:
            logger.error(f"Parse error: {e}")
            for site in sites:
                results.append(ClassificationResult(
                    page_id=site.page_id,
                    error=str(e)[:50]
                ))

        return results

    def _parse_single_response(
        self,
        response: Dict,
        site: SiteData
    ) -> ClassificationResult:
        """Parse la reponse pour un site unique."""
        try:
            text = response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Nettoyer le JSON
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

            c = json.loads(text)

            return ClassificationResult(
                page_id=site.page_id,
                category=c.get("niche", "Divers & Spécialisé"),
                subcategory=c.get("subcategory", "Généraliste"),
                confidence=float(c.get("confidence", 0.5)),
            )

        except Exception as e:
            logger.error(f"Parse error: {e}")
            return ClassificationResult(
                page_id=site.page_id,
                error=str(e)[:50]
            )

    def _get_default_taxonomy(self) -> str:
        """Retourne la taxonomie par defaut."""
        return """
- Mode & Accessoires: Bijoux, Montres, Sacs, Chaussures, Vêtements
- Beauté & Bien-être: Cosmétiques, Soins, Parfums, Compléments
- Maison & Décoration: Mobilier, Luminaires, Textile, Art
- High-Tech & Gadgets: Électronique, Accessoires Tech, Domotique
- Sport & Loisirs: Fitness, Outdoor, Équipement sportif
- Famille & Enfants: Jouets, Puériculture, Vêtements enfants
- Animaux: Accessoires, Alimentation, Soins
- Alimentation: Épicerie, Boissons, Bio, Gourmet
- Divers & Spécialisé: Généraliste, Niche spécifique
"""


# ===========================================================================
# FONCTIONS UTILITAIRES
# ===========================================================================

def classify_pages_batch_v2(
    db,
    pages_data: List[Dict[str, Any]],
    progress_callback: callable = None
) -> Dict[str, Dict[str, Any]]:
    """
    Fonction de remplacement pour classify_pages_batch.

    Args:
        db: DatabaseManager (pour recuperer la taxonomie)
        pages_data: Liste de {"page_id", "url", "site_title", ...}
        progress_callback: Callback

    Returns:
        Dict {page_id: {"category", "subcategory", "confidence"}}
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY non configuree - classification skippee")
        return {}

    # Recuperer la taxonomie et le modele depuis la DB si disponible
    taxonomy_text = None
    model_name = None
    if db:
        try:
            from src.infrastructure.persistence.database import (
                build_taxonomy_prompt, init_default_taxonomy,
                get_app_setting, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT
            )
            init_default_taxonomy(db)
            taxonomy_text = build_taxonomy_prompt(db)
            # Charger le modele configure en BDD
            model_name = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)
            if model_name:
                logger.info(f"Using Gemini model from settings: {model_name}")
        except Exception as e:
            logger.warning(f"Could not load settings from DB: {e}")

    # Classifier avec le modele configure
    classifier = GeminiBatchClassifier(api_key=api_key, model=model_name, taxonomy_text=taxonomy_text)
    return classifier.classify_dict(pages_data, progress_callback)
