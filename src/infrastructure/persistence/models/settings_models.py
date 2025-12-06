"""
Modeles SQLAlchemy pour les parametres et tokens.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Index

from src.infrastructure.persistence.models.base import Base


class UserSettings(Base):
    """Table user_settings - Parametres utilisateur"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClassificationTaxonomy(Base):
    """Table classification_taxonomy - Taxonomie pour la classification automatique"""
    __tablename__ = "classification_taxonomy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False)
    subcategory = Column(String(100), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_taxonomy_category', 'category'),
        Index('idx_taxonomy_active', 'is_active'),
    )


class MetaToken(Base):
    """Table meta_tokens - Gestion des tokens Meta API"""
    __tablename__ = "meta_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    token = Column(Text, nullable=False)
    proxy_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    # Statistiques d'utilisation
    total_calls = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    rate_limit_hits = Column(Integer, default=0)

    # Etat actuel
    last_used_at = Column(DateTime)
    last_error_at = Column(DateTime)
    last_error_message = Column(Text)
    rate_limited_until = Column(DateTime)

    # Metadonnees
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_meta_token_active', 'is_active'),
    )


class TokenUsageLog(Base):
    """Logs detailles d'utilisation des tokens Meta API"""
    __tablename__ = "token_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(Integer, nullable=False, index=True)
    token_name = Column(String(100))

    action_type = Column(String(50))
    keyword = Column(String(255))
    countries = Column(String(100))
    page_id = Column(String(50))

    success = Column(Boolean, default=True)
    ads_count = Column(Integer, default=0)
    error_message = Column(Text)
    response_time_ms = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_token_log_date', 'created_at'),
        Index('idx_token_log_token', 'token_id', 'created_at'),
    )


class AppSettings(Base):
    """Table app_settings - Parametres persistants de l'application"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
