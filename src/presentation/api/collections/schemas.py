"""
Collections Schemas - Modeles Pydantic pour les endpoints collections.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les collections.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CollectionResponse(BaseModel):
    """Representation d'une collection."""

    id: int
    name: str
    description: Optional[str] = None
    page_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectionDetailResponse(BaseModel):
    """Collection avec ses pages."""

    id: int
    name: str
    description: Optional[str] = None
    page_ids: list[str] = []
    page_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CollectionListResponse(BaseModel):
    """Liste de collections."""

    items: list[CollectionResponse]
    total: int


class CreateCollectionRequest(BaseModel):
    """Requete de creation de collection."""

    name: str = Field(..., min_length=1, max_length=100, description="Nom de la collection")
    description: Optional[str] = Field(None, max_length=500, description="Description")


class UpdateCollectionRequest(BaseModel):
    """Requete de mise a jour de collection."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AddPageToCollectionRequest(BaseModel):
    """Requete d'ajout de page a une collection."""

    page_id: str = Field(..., min_length=1, description="ID de la page a ajouter")
