"""
Interfaces des services externes.

Ces interfaces definissent les operations des services
externes que les adapters doivent implementer.
"""

from src.application.ports.services.ads_search_service import AdsSearchService
from src.application.ports.services.website_analyzer_service import WebsiteAnalyzerService
from src.application.ports.services.classification_service import ClassificationService

__all__ = [
    "AdsSearchService",
    "WebsiteAnalyzerService",
    "ClassificationService",
]
