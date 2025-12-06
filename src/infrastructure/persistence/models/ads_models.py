"""
Modeles SQLAlchemy pour les annonces et winning ads.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Index, Boolean

from src.infrastructure.persistence.models.base import Base


class AdsRecherche(Base):
    """Table liste_ads_recherche - Annonces des pages avec >= 20 ads"""
    __tablename__ = "liste_ads_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    eu_total_reach = Column(String(100))
    languages = Column(String(100))
    country = Column(String(50))
    publisher_platforms = Column(String(200))
    target_ages = Column(String(100))
    target_gender = Column(String(50))
    beneficiary_payers = Column(Text)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_ads_page', 'page_id'),
        Index('idx_ads_date', 'date_scan'),
    )


class WinningAds(Base):
    """Table winning_ads - Annonces performantes détectées"""
    __tablename__ = "winning_ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), unique=True, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_age_days = Column(Integer)
    eu_total_reach = Column(Integer)
    matched_criteria = Column(String(100))
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    lien_site = Column(String(500))
    date_scan = Column(DateTime, default=datetime.utcnow)
    search_log_id = Column(Integer, nullable=True, index=True)
    is_new = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_winning_ads_page', 'page_id'),
        Index('idx_winning_ads_date', 'date_scan'),
        Index('idx_winning_ads_ad', 'ad_id', 'date_scan'),
        Index('idx_winning_ads_page_date', 'page_id', 'date_scan'),
        Index('idx_winning_ads_reach', 'eu_total_reach'),
    )


class AdsRechercheArchive(Base):
    """Archive de liste_ads_recherche - Données historiques >90 jours"""
    __tablename__ = "liste_ads_recherche_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    eu_total_reach = Column(String(100))
    languages = Column(String(100))
    country = Column(String(50))
    publisher_platforms = Column(String(200))
    target_ages = Column(String(100))
    target_gender = Column(String(50))
    beneficiary_payers = Column(Text)
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)


class WinningAdsArchive(Base):
    """Archive de winning_ads - Données historiques >90 jours"""
    __tablename__ = "winning_ads_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_age_days = Column(Integer)
    eu_total_reach = Column(Integer)
    matched_criteria = Column(String(100))
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    lien_site = Column(String(500))
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)
