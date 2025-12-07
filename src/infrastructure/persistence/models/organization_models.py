"""
Modeles SQLAlchemy pour l'organisation: tags, notes, favoris, collections, blacklist, filtres.

Multi-tenancy:
--------------
Les tables suivantes supportent l'isolation par utilisateur via owner_id:
- Tag: Tags personnels de l'utilisateur
- Favorite: Pages favorites de l'utilisateur
- Collection: Collections de l'utilisateur
- SavedFilter: Filtres sauvegardes
- ScheduledScan: Scans programmes
- Blacklist: Blacklist personnelle

owner_id est nullable pour la retrocompatibilite.
Les enregistrements sans owner_id sont consideres comme publics (SYSTEM_USER).
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from src.infrastructure.persistence.models.base import Base


class Tag(Base):
    """
    Table tags - Tags personnalises pour organiser les pages.

    Multi-tenancy: Chaque utilisateur a ses propres tags.
    Les tags sans owner_id sont partages (systeme).
    """
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    color = Column(String(20), default="#3B82F6")
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_tag_owner_name', 'owner_id', 'name', unique=True),
    )


class PageTag(Base):
    """Table page_tags - Association pages <-> tags"""
    __tablename__ = "page_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_tag_unique', 'page_id', 'tag_id', unique=True),
    )


class PageNote(Base):
    """
    Table page_notes - Notes sur les pages.

    Multi-tenancy: Chaque utilisateur a ses propres notes.
    """
    __tablename__ = "page_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(Base):
    """
    Table favorites - Pages favorites.

    Multi-tenancy: Chaque utilisateur a ses propres favoris.
    L'unicite est par (owner_id, page_id).
    """
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_favorite_owner_page', 'owner_id', 'page_id', unique=True),
    )


class Collection(Base):
    """
    Table collections - Dossiers/Collections de pages.

    Multi-tenancy: Chaque utilisateur a ses propres collections.
    """
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(20), default="#6366F1")
    icon = Column(String(10), default="📁")
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollectionPage(Base):
    """Table collection_pages - Association collections <-> pages"""
    __tablename__ = "collection_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_collection_page_unique', 'collection_id', 'page_id', unique=True),
    )


class Blacklist(Base):
    """
    Table blacklist - Pages a exclure des recherches.

    Multi-tenancy: Chaque utilisateur a sa propre blacklist.
    L'unicite est par (owner_id, page_id).
    """
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    raison = Column(String(255))
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_blacklist_page_name', 'page_name'),
        Index('idx_blacklist_owner_page', 'owner_id', 'page_id', unique=True),
    )


class SavedFilter(Base):
    """
    Table saved_filters - Filtres de recherche sauvegardes.

    Multi-tenancy: Chaque utilisateur a ses propres filtres.
    """
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    filter_type = Column(String(50), default="pages")
    filters_json = Column(Text)
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledScan(Base):
    """
    Table scheduled_scans - Scans programmes.

    Multi-tenancy: Chaque utilisateur a ses propres scans programmes.
    """
    __tablename__ = "scheduled_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    keywords = Column(Text)
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    frequency = Column(String(20), default="daily")
    is_active = Column(Integer, default=1)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    owner_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
