"""
Modeles SQLAlchemy pour les pages et leur suivi.

Multi-tenancy:
--------------
Toutes les tables ont une colonne user_id pour isoler les donnees par utilisateur.
user_id = None signifie donnees systeme/partagees.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID

from src.infrastructure.persistence.models.base import Base


class PageRecherche(Base):
    """Table liste_page_recherche - Toutes les pages analysées"""
    __tablename__ = "liste_page_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    lien_site = Column(String(500))
    lien_fb_ad_library = Column(String(500))
    keywords = Column(Text)
    thematique = Column(String(100))
    subcategory = Column(String(100))
    classification_confidence = Column(Float)
    classified_at = Column(DateTime)
    type_produits = Column(Text)
    moyens_paiements = Column(Text)
    pays = Column(String(255))
    langue = Column(String(50))
    cms = Column(String(50))
    template = Column(String(100))
    devise = Column(String(10))
    etat = Column(String(20))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    dernier_scan = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    site_title = Column(String(255))
    site_description = Column(Text)
    site_h1 = Column(String(200))
    site_keywords = Column(String(300))
    last_search_log_id = Column(Integer, nullable=True, index=True)
    was_created_in_last_search = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_page_user', 'user_id'),
        Index('idx_page_user_page', 'user_id', 'page_id', unique=True),  # Unique par user
        Index('idx_page_etat', 'etat'),
        Index('idx_page_cms', 'cms'),
        Index('idx_page_dernier_scan', 'dernier_scan'),
        Index('idx_page_cms_etat', 'cms', 'etat'),
        Index('idx_page_etat_ads', 'etat', 'nombre_ads_active'),
        Index('idx_page_created', 'created_at'),
        Index('idx_page_thematique', 'thematique'),
    )


class SuiviPage(Base):
    """Table suivi_page - Historique des pages avec >= 10 ads actives"""
    __tablename__ = "suivi_page"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    cle_suivi = Column(String(100))
    page_id = Column(String(50), nullable=False, index=True)
    nom_site = Column(String(255))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_suivi_user', 'user_id'),
        Index('idx_suivi_page_date', 'page_id', 'date_scan'),
    )


class SuiviPageArchive(Base):
    """Archive de suivi_page - Données historiques >90 jours"""
    __tablename__ = "suivi_page_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Multi-tenancy
    original_id = Column(Integer)
    cle_suivi = Column(String(100))
    page_id = Column(String(50), nullable=False, index=True)
    nom_site = Column(String(255))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)
