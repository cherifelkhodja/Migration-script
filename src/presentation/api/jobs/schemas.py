"""
Jobs Schemas - Modeles Pydantic pour les endpoints jobs.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les background jobs.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class JobResponse(BaseModel):
    """Representation d'un job."""

    id: UUID
    type: str
    status: str
    params: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    progress: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class JobListResponse(BaseModel):
    """Liste de jobs."""

    items: list[JobResponse]
    total: int
    counts: dict[str, int]


class CreateSearchJobRequest(BaseModel):
    """Requete de creation de job de recherche."""

    keywords: list[str] = Field(..., min_length=1, description="Mots-cles")
    countries: list[str] = Field(default=["FR"], description="Pays")
    languages: list[str] = Field(default=["fr"], description="Langues")


class CreateAnalyzeJobRequest(BaseModel):
    """Requete de creation de job d'analyse."""

    urls: list[str] = Field(..., min_length=1, max_length=50, description="URLs")
    country_code: str = Field(default="FR", description="Code pays")


class CreateExportJobRequest(BaseModel):
    """Requete de creation de job d'export."""

    export_type: str = Field(..., description="Type d'export (csv, excel, json)")
    filters: Optional[dict[str, Any]] = Field(default=None, description="Filtres")


class JobStatusCountsResponse(BaseModel):
    """Compteurs de jobs par statut."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
