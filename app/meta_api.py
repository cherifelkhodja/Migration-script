"""
Module Meta API - Shim de compatibilite.

Ce module redirige vers src.infrastructure.external_services pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.infrastructure.external_services.meta_api import (  # noqa: F401
    # Classes
    TokenRotator,
    MetaAdsClient,
    # Singleton functions
    get_token_rotator,
    init_token_rotator,
    clear_token_rotator,
    # Search functions
    search_keywords_parallel,
    # Extraction functions
    extract_website_from_ads,
    extract_currency_from_ads,
    # Cache functions
    cached_search_ads,
    cached_fetch_ads_for_page,
)

__all__ = [
    # Classes
    "TokenRotator",
    "MetaAdsClient",
    # Singleton functions
    "get_token_rotator",
    "init_token_rotator",
    "clear_token_rotator",
    # Search functions
    "search_keywords_parallel",
    # Extraction functions
    "extract_website_from_ads",
    "extract_currency_from_ads",
    # Cache functions
    "cached_search_ads",
    "cached_fetch_ads_for_page",
]
