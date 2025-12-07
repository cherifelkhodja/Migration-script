"""
Pages Schemas - Modeles Pydantic pour les endpoints pages.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les endpoints pages (shops).
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class PageResponse(BaseModel):
    """Representation d'une page/shop."""

    page_id: str
    name: str
    website: Optional[str] = None
    cms: Optional[str] = None
    theme: Optional[str] = None
    etat: Optional[str] = None
    active_ads_count: int = 0
    product_count: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    currency: Optional[str] = None
    is_favorite: bool = False
    is_blacklisted: bool = False
    keywords: list[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_scan_at: Optional[datetime] = None


class PageListResponse(BaseModel):
    """Liste paginee de pages."""

    items: list[PageResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CreatePageRequest(BaseModel):
    """Requete de creation de page."""

    page_id: str = Field(..., min_length=1, description="ID unique de la page")
    name: str = Field(..., min_length=1, description="Nom de la page")
    website: Optional[str] = Field(None, description="URL du site")


class UpdatePageRequest(BaseModel):
    """Requete de mise a jour de page."""

    name: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_blacklisted: Optional[bool] = None


class UpdateClassificationRequest(BaseModel):
    """Requete de mise a jour de classification."""

    category: str = Field(..., min_length=1)
    subcategory: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PageStatsResponse(BaseModel):
    """Statistiques des pages."""

    total_pages: int
    total_with_website: int
    total_with_cms: int
    total_favorites: int
    total_blacklisted: int
    etat_distribution: dict[str, int]
    cms_distribution: dict[str, int]
    category_distribution: dict[str, int]


class PageFilters(BaseModel):
    """Filtres pour la recherche de pages."""

    etats: Optional[list[str]] = None
    cms_types: Optional[list[str]] = None
    category: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_blacklisted: Optional[bool] = None
    min_ads: Optional[int] = None
    query: Optional[str] = None
