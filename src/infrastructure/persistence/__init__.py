"""
Adapters pour la persistence des donnees.
"""

from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository
from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
    SQLAlchemyWinningAdRepository,
)

__all__ = [
    "SQLAlchemyPageRepository",
    "SQLAlchemyWinningAdRepository",
]
