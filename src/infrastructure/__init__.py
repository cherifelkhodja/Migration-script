"""
Infrastructure Layer - Adapters pour les services externes.

Cette couche contient les implementations concretes des ports definis
dans la couche application. Elle gere les interactions avec:
- Base de donnees PostgreSQL
- API Meta Ads
- API Gemini (classification)
- Web scraping
"""

from src.infrastructure.container import Container, get_container, reset_container
from src.infrastructure.external_services.meta_ads_adapter import MetaAdsSearchAdapter
from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository

__all__ = [
    "Container",
    "get_container",
    "reset_container",
    "MetaAdsSearchAdapter",
    "SQLAlchemyPageRepository",
]
