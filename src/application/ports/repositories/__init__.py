"""
Interfaces des repositories (persistance).

Ces interfaces definissent les operations de persistance
que les adapters de base de donnees doivent implementer.
"""

from src.application.ports.repositories.page_repository import PageRepository
from src.application.ports.repositories.ad_repository import AdRepository
from src.application.ports.repositories.winning_ad_repository import WinningAdRepository
from src.application.ports.repositories.collection_repository import CollectionRepository
from src.application.ports.repositories.search_log_repository import SearchLogRepository

__all__ = [
    "PageRepository",
    "AdRepository",
    "WinningAdRepository",
    "CollectionRepository",
    "SearchLogRepository",
]
