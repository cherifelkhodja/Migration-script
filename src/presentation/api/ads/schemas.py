"""
Ads Schemas - Modeles Pydantic pour les endpoints ads.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les endpoints ads.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class SearchAdsRequest(BaseModel):
    """
    Requete de recherche d'annonces.

    Example:
        {"keywords": ["bijoux", "montres"], "countries": ["FR"], "min_ads": 3}
    """

    keywords: list[str] = Field(..., min_length=1, description="Mots-cles a rechercher")
    countries: list[str] = Field(default=["FR"], description="Codes pays")
    languages: list[str] = Field(default=["fr"], description="Codes langues")
    min_ads: int = Field(default=1, ge=1, description="Nombre minimum d'ads par page")
    cms_filter: list[str] = Field(default=[], description="Filtrer par CMS")
    exclude_blacklisted: bool = Field(default=True, description="Exclure pages blacklistees")


class AdResponse(BaseModel):
    """Representation d'une annonce."""

    id: str
    page_id: str
    page_name: str
    ad_creative_link_title: Optional[str] = None
    ad_delivery_start_time: Optional[datetime] = None
    eu_total_reach: Optional[int] = None
    snapshot_url: Optional[str] = None


class PageWithAdsResponse(BaseModel):
    """Page avec ses annonces."""

    page_id: str
    page_name: str
    ads_count: int
    ads: list[AdResponse]
    keywords_found: list[str]


class SearchAdsResponse(BaseModel):
    """Reponse de recherche d'annonces."""

    pages: list[PageWithAdsResponse]
    total_ads_found: int
    unique_ads_count: int
    pages_count: int
    search_duration_ms: int
    keywords_stats: dict[str, int]


class WinningAdResponse(BaseModel):
    """Representation d'une winning ad."""

    id: Optional[int] = None
    ad_id: str
    page_id: str
    page_name: str
    reach: int
    days_active: int
    winning_score: float
    matched_criteria: str
    detected_at: datetime
    snapshot_url: Optional[str] = None


class DetectWinningRequest(BaseModel):
    """Requete de detection de winning ads."""

    search_log_id: Optional[int] = None
    custom_criteria: Optional[list[tuple[int, int]]] = None


class DetectWinningResponse(BaseModel):
    """Reponse de detection de winning ads."""

    winning_ads: list[WinningAdResponse]
    total_analyzed: int
    detection_rate: float
    criteria_distribution: dict[str, int]
    saved_count: int
    skipped_count: int


class WinningAdsListResponse(BaseModel):
    """Liste paginee de winning ads."""

    items: list[WinningAdResponse]
    total: int
    page: int
    page_size: int
    pages: int
