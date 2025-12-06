"""
Module de scrapers et detecteurs web.

Fournit des outils pour analyser les sites web:
- Detection de CMS (Shopify, WooCommerce, etc.)
- Analyse complete de sites web
- Extraction d'informations
"""

from src.infrastructure.scrapers.cms_detector import (
    detect_cms_from_url,
    check_shopify_http,
    get_shopify_details,
)

from src.infrastructure.scrapers.web_analyzer import (
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
    # CMS Detector
    "detect_cms_from_url",
    "check_shopify_http",
    "get_shopify_details",
    # Web Analyzer
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
