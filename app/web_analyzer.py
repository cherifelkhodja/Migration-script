"""
Module Web Analyzer - Shim de compatibilite.

Ce module redirige vers src.infrastructure.scrapers pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.infrastructure.scrapers import (  # noqa: F401
    ensure_url,
    get_web,
    detect_cms,
    detect_theme,
    detect_payments,
    classify,
    try_get,
    collect_text_for_classification,
    count_products_shopify_by_country,
    extract_currency_from_html,
    analyze_website_complete,
)

__all__ = [
    "ensure_url",
    "get_web",
    "detect_cms",
    "detect_theme",
    "detect_payments",
    "classify",
    "try_get",
    "collect_text_for_classification",
    "count_products_shopify_by_country",
    "extract_currency_from_html",
    "analyze_website_complete",
]
