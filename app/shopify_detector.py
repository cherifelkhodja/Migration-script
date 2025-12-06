"""
Module Shopify Detector - Shim de compatibilite.

Ce module redirige vers src.infrastructure.scrapers pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.infrastructure.scrapers import (  # noqa: F401
    detect_cms_from_url,
    check_shopify_http,
    get_shopify_details,
)

__all__ = [
    "detect_cms_from_url",
    "check_shopify_http",
    "get_shopify_details",
]
