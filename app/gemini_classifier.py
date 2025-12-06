"""
Module Gemini Classifier - Shim de compatibilite.

Ce module redirige vers src.infrastructure.external_services pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.infrastructure.external_services.gemini_classifier import (  # noqa: F401
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
    # Constantes
    MAX_CONTENT_LENGTH,
    BATCH_SIZE,
    REQUEST_TIMEOUT,
    GEMINI_TIMEOUT,
    RATE_LIMIT_DELAY,
    USER_AGENTS,
)

__all__ = [
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
    "MAX_CONTENT_LENGTH",
    "BATCH_SIZE",
    "REQUEST_TIMEOUT",
    "GEMINI_TIMEOUT",
    "RATE_LIMIT_DELAY",
    "USER_AGENTS",
]
