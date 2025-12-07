"""
Module de scrapers et detecteurs web.

Fournit des outils pour analyser les sites web:
- Detection de CMS (Shopify, WooCommerce, etc.)
- Analyse complete de sites web
- Extraction d'informations

V2 (MarketSpy):
- Analyse optimisee avec 1 requete homepage
- Streaming sitemap avec limites budgetaires
- Classification Gemini batch (10 sites/appel)
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

# MarketSpy V2 - Optimized analyzers
from src.infrastructure.scrapers.market_spy import (
    MarketSpy,
    ThemeDetector,
    SitemapAnalyzer,
    HttpClient,
    HomepageData,
    SitemapData,
    AnalysisResult,
    analyze_website_v2,
    analyze_homepage_v2,
    analyze_sitemap_v2,
    analyze_batch_v2,
)

from src.infrastructure.scrapers.gemini_batch_classifier import (
    GeminiBatchClassifier,
    SiteData,
    ClassificationResult,
    classify_pages_batch_v2,
)

__all__ = [
    # CMS Detector
    "detect_cms_from_url",
    "check_shopify_http",
    "get_shopify_details",
    # Web Analyzer (legacy)
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
    # MarketSpy V2
    "MarketSpy",
    "ThemeDetector",
    "SitemapAnalyzer",
    "HttpClient",
    "HomepageData",
    "SitemapData",
    "AnalysisResult",
    "analyze_website_v2",
    "analyze_homepage_v2",
    "analyze_sitemap_v2",
    "analyze_batch_v2",
    # Gemini Batch Classifier V2
    "GeminiBatchClassifier",
    "SiteData",
    "ClassificationResult",
    "classify_pages_batch_v2",
]
