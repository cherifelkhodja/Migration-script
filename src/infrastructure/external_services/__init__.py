"""
Adapters pour les services externes.

Ce module expose les adapters pour les services externes
(Meta API, Gemini, Web Analyzer).
"""

from src.infrastructure.external_services.meta_ads_adapter import MetaAdsSearchAdapter

# Gemini Classifier (migre depuis app/)
from src.infrastructure.external_services.gemini_classifier import (
    SiteContent,
    ClassificationResult,
    GeminiClassifier,
    extract_site_content_sync,
    extract_product_links,
    fetch_site_content,
    scrape_sites_batch,
    fetch_site_content_sync_requests,
    scrape_sites_sync,
    classify_pages_async,
    classify_pages_sync,
    classify_and_save,
    classify_with_extracted_content,
    classify_pages_batch,
)

# Meta API (migre depuis app/)
from src.infrastructure.external_services.meta_api import (
    TokenRotator,
    MetaAdsClient,
    get_token_rotator,
    init_token_rotator,
    clear_token_rotator,
    search_keywords_parallel,
    extract_website_from_ads,
    extract_currency_from_ads,
    cached_search_ads,
    cached_fetch_ads_for_page,
)

__all__ = [
    "MetaAdsSearchAdapter",
    # Gemini Classifier
    "SiteContent",
    "ClassificationResult",
    "GeminiClassifier",
    "extract_site_content_sync",
    "extract_product_links",
    "fetch_site_content",
    "scrape_sites_batch",
    "fetch_site_content_sync_requests",
    "scrape_sites_sync",
    "classify_pages_async",
    "classify_pages_sync",
    "classify_and_save",
    "classify_with_extracted_content",
    "classify_pages_batch",
    # Meta API
    "TokenRotator",
    "MetaAdsClient",
    "get_token_rotator",
    "init_token_rotator",
    "clear_token_rotator",
    "search_keywords_parallel",
    "extract_website_from_ads",
    "extract_currency_from_ads",
    "cached_search_ads",
    "cached_fetch_ads_for_page",
]
