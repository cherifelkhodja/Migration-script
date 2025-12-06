"""
Module de scrapers et detecteurs web.

Fournit des outils pour analyser les sites web:
- Detection de CMS (Shopify, WooCommerce, etc.)
- Extraction d'informations
"""

from src.infrastructure.scrapers.cms_detector import (
    detect_cms_from_url,
    check_shopify_http,
    get_shopify_details,
)

__all__ = [
    "detect_cms_from_url",
    "check_shopify_http",
    "get_shopify_details",
]
