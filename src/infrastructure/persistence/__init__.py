"""
Adapters pour la persistence des donnees.
"""

from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository

__all__ = [
    "SQLAlchemyPageRepository",
]
