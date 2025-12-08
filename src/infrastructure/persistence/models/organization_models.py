"""
Modeles SQLAlchemy pour l'organisation: tags, notes, favoris, collections, blacklist, filtres.

Multi-tenancy:
--------------
Toutes les tables ont une colonne user_id pour isoler les donnees par utilisateur.
user_id = None signifie donnees systeme/partagees.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from src.infrastructure.persistence.models.base import Base


class Tag(Base):
    """
    Table tags - Tags personnalises pour organiser les pages.
    """
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    name = Column(String(50), nullable=False)
    color = Column(String(20), default="#3B82F6")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_tag_user', 'user_id'),
        Index('idx_tag_user_name', 'user_id', 'name', unique=True),  # Unique par user
    )


class PageTag(Base):
    """Table page_tags - Association pages <-> tags"""
    __tablename__ = "page_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    page_id = Column(String(50), nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_tag_user', 'user_id'),
        Index('idx_page_tag_unique', 'user_id', 'page_id', 'tag_id', unique=True),
    )


class PageNote(Base):
    """
    Table page_notes - Notes sur les pages.
    """
    __tablename__ = "page_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    page_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_note_user', 'user_id'),
    )


class Favorite(Base):
    """
    Table favorites - Pages favorites.
    """
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    page_id = Column(String(50), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_favorite_user', 'user_id'),
        Index('idx_favorite_user_page', 'user_id', 'page_id', unique=True),  # Unique par user
    )


class Collection(Base):
    """
    Table collections - Dossiers/Collections de pages.
    """
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(20), default="#6366F1")
    icon = Column(String(10), default="📁")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_collection_user', 'user_id'),
    )


class CollectionPage(Base):
    """Table collection_pages - Association collections <-> pages"""
    __tablename__ = "collection_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    collection_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_collection_page_user', 'user_id'),
        Index('idx_collection_page_unique', 'user_id', 'collection_id', 'page_id', unique=True),
    )


class Blacklist(Base):
    """
    Table blacklist - Pages a exclure des recherches.
    """
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    raison = Column(String(255))
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_blacklist_user', 'user_id'),
        Index('idx_blacklist_user_page', 'user_id', 'page_id', unique=True),  # Unique par user
        Index('idx_blacklist_page_name', 'page_name'),
    )


class SavedFilter(Base):
    """
    Table saved_filters - Filtres de recherche sauvegardes.
    """
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    name = Column(String(100), nullable=False)
    filter_type = Column(String(50), default="pages")
    filters_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_saved_filter_user', 'user_id'),
    )


class ScheduledScan(Base):
    """
    Table scheduled_scans - Scans programmes.
    """
    __tablename__ = "scheduled_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column('owner_id', UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy (mapped to owner_id in DB)
    name = Column(String(100), nullable=False)
    keywords = Column(Text)
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    frequency = Column(String(20), default="daily")
    is_active = Column(Integer, default=1)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_scheduled_scan_user', 'owner_id'),
    )
