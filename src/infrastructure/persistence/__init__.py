"""
Adapters pour la persistence des donnees.

Ce module expose les repositories et le DatabaseManager
pour l'architecture hexagonale.
"""

from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository
from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
    SQLAlchemyWinningAdRepository,
)

# Bridge vers app.database
try:
    from app.database import DatabaseManager, Base
except ImportError:
    DatabaseManager = None  # type: ignore
    Base = None  # type: ignore

__all__ = [
    "SQLAlchemyPageRepository",
    "SQLAlchemyWinningAdRepository",
    "DatabaseManager",
    "Base",
]
