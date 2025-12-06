"""
Modeles SQLAlchemy pour les recherches: logs, queue, historique.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Index, Boolean

from src.infrastructure.persistence.models.base import Base


class SearchLog(Base):
    """Table search_logs - Historique complet des recherches"""
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keywords = Column(Text)
    countries = Column(String(100))
    languages = Column(String(100))
    min_ads = Column(Integer, default=1)
    selected_cms = Column(String(200))

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    duration_seconds = Column(Float)

    status = Column(String(20), default="running")
    error_message = Column(Text)
    phases_data = Column(Text)

    total_ads_found = Column(Integer, default=0)
    total_pages_found = Column(Integer, default=0)
    pages_after_filter = Column(Integer, default=0)
    pages_shopify = Column(Integer, default=0)
    pages_other_cms = Column(Integer, default=0)
    winning_ads_count = Column(Integer, default=0)
    blacklisted_ads_skipped = Column(Integer, default=0)

    pages_saved = Column(Integer, default=0)
    ads_saved = Column(Integer, default=0)
    new_pages_count = Column(Integer, default=0)
    existing_pages_updated = Column(Integer, default=0)
    new_winning_ads_count = Column(Integer, default=0)
    existing_winning_ads_updated = Column(Integer, default=0)

    meta_api_calls = Column(Integer, default=0)
    scraper_api_calls = Column(Integer, default=0)
    web_requests = Column(Integer, default=0)

    meta_api_errors = Column(Integer, default=0)
    scraper_api_errors = Column(Integer, default=0)
    web_errors = Column(Integer, default=0)
    rate_limit_hits = Column(Integer, default=0)

    meta_api_avg_time = Column(Float, default=0)
    scraper_api_avg_time = Column(Float, default=0)
    web_avg_time = Column(Float, default=0)

    scraper_api_cost = Column(Float, default=0)
    api_details = Column(Text)
    errors_list = Column(Text)
    scraper_errors_by_type = Column(Text)

    __table_args__ = (
        Index('idx_search_log_date', 'started_at'),
        Index('idx_search_log_status', 'status'),
        Index('idx_search_log_status_date', 'status', 'started_at'),
    )


class PageSearchHistory(Base):
    """Table de liaison many-to-many entre SearchLog et PageRecherche."""
    __tablename__ = "page_search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    found_at = Column(DateTime, default=datetime.utcnow)
    was_new = Column(Boolean, default=True)
    ads_count_at_discovery = Column(Integer, default=0)
    keyword_matched = Column(String(255))

    __table_args__ = (
        Index('idx_page_search_history_search', 'search_log_id'),
        Index('idx_page_search_history_page', 'page_id'),
        Index('idx_page_search_history_composite', 'search_log_id', 'page_id'),
    )


class WinningAdSearchHistory(Base):
    """Table de liaison many-to-many entre SearchLog et WinningAds."""
    __tablename__ = "winning_ad_search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, nullable=False, index=True)
    ad_id = Column(String(50), nullable=False, index=True)
    found_at = Column(DateTime, default=datetime.utcnow)
    was_new = Column(Boolean, default=True)
    reach_at_discovery = Column(Integer, default=0)
    age_days_at_discovery = Column(Integer, default=0)
    matched_criteria = Column(String(100))

    __table_args__ = (
        Index('idx_winning_ad_search_history_search', 'search_log_id'),
        Index('idx_winning_ad_search_history_ad', 'ad_id'),
        Index('idx_winning_ad_search_history_composite', 'search_log_id', 'ad_id'),
    )


class SearchQueue(Base):
    """Table search_queue - File d'attente des recherches en arrière-plan"""
    __tablename__ = "search_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default="pending", index=True)

    keywords = Column(Text)
    cms_filter = Column(Text)
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    ads_min = Column(Integer, default=3)

    current_phase = Column(Integer, default=0)
    current_phase_name = Column(String(100))
    progress_percent = Column(Integer, default=0)
    progress_message = Column(Text)
    phases_data = Column(Text)

    search_log_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_session = Column(String(100), nullable=True, index=True)
    priority = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_search_queue_status', 'status'),
        Index('idx_search_queue_user', 'user_session'),
        Index('idx_search_queue_created', 'created_at'),
    )


class APICallLog(Base):
    """Table api_call_logs - Détails de chaque appel API"""
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, index=True)

    api_type = Column(String(50))
    endpoint = Column(String(500))
    method = Column(String(10), default="GET")

    keyword = Column(String(200))
    page_id = Column(String(50))
    site_url = Column(String(500))

    status_code = Column(Integer)
    success = Column(Boolean, default=True)
    error_type = Column(String(100))
    error_message = Column(Text)

    response_time_ms = Column(Float)
    response_size = Column(Integer)
    items_returned = Column(Integer, default=0)

    called_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_api_call_search', 'search_log_id'),
        Index('idx_api_call_type', 'api_type'),
        Index('idx_api_call_date', 'called_at'),
    )
