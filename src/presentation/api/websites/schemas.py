"""
Websites Schemas - Modeles Pydantic pour les endpoints websites.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour l'analyse de sites.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


class AnalyzeWebsiteRequest(BaseModel):
    """
    Requete d'analyse d'un site web.

    Example:
        {"url": "https://example-shop.com", "country_code": "FR"}
    """

    url: str = Field(..., description="URL du site a analyser")
    country_code: str = Field(default="FR", description="Code pays pour le sitemap")


class AnalyzeBatchRequest(BaseModel):
    """
    Requete d'analyse de plusieurs sites.

    Example:
        {"urls": ["https://shop1.com", "https://shop2.com"]}
    """

    urls: list[str] = Field(..., min_length=1, max_length=50, description="URLs a analyser")
    country_code: str = Field(default="FR", description="Code pays")
    max_concurrent: int = Field(default=5, ge=1, le=10, description="Requetes paralleles max")


class WebsiteAnalysisResponse(BaseModel):
    """Resultat d'analyse d'un site."""

    url: str
    is_success: bool
    cms: Optional[str] = None
    theme: Optional[str] = None
    product_count: int = 0
    currency: Optional[str] = None
    error: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.now)


class AnalyzeBatchResponse(BaseModel):
    """Reponse d'analyse batch."""

    results: list[WebsiteAnalysisResponse]
    analyzed_count: int
    success_count: int
    error_count: int
    cms_distribution: dict[str, int]
