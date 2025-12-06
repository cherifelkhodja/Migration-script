"""
Adapters pour les services externes.

Ce module expose les adapters pour les services externes
(Meta API, Gemini, Web Analyzer).
"""

from src.infrastructure.external_services.meta_ads_adapter import MetaAdsSearchAdapter

# Bridges vers app/
try:
    from app.meta_api import MetaAPIClient
except ImportError:
    MetaAPIClient = None  # type: ignore

try:
    from app.gemini_classifier import GeminiClassifier
except ImportError:
    GeminiClassifier = None  # type: ignore

try:
    from app.web_analyzer import WebAnalyzer
except ImportError:
    WebAnalyzer = None  # type: ignore

try:
    from app.shopify_detector import ShopifyDetector
except ImportError:
    ShopifyDetector = None  # type: ignore

__all__ = [
    "MetaAdsSearchAdapter",
    "MetaAPIClient",
    "GeminiClassifier",
    "WebAnalyzer",
    "ShopifyDetector",
]
