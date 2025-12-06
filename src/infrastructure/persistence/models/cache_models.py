"""
Modeles SQLAlchemy pour le cache API.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Index

from src.infrastructure.persistence.models.base import Base


class APICache(Base):
    """Cache pour les appels API Meta"""
    __tablename__ = "api_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    cache_type = Column(String(50))
    response_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    hit_count = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_cache_expires', 'expires_at'),
        Index('idx_cache_type', 'cache_type'),
    )
