"""
Ports (Interfaces) de l'application.

Les ports definissent les contrats que les adapters
de l'infrastructure doivent implementer.

Types de ports:
    - repositories/: Interfaces pour la persistance des donnees
    - services/: Interfaces pour les services externes
"""

from src.application.ports.repositories import (
    AdRepository,
    CollectionRepository,
    PageRepository,
    SearchLogRepository,
    WinningAdRepository,
)
from src.application.ports.services import (
    AdsSearchService,
    ClassificationService,
    WebsiteAnalyzerService,
)

__all__ = [
    # Repositories
    "PageRepository",
    "AdRepository",
    "WinningAdRepository",
    "CollectionRepository",
    "SearchLogRepository",
    # Services
    "AdsSearchService",
    "WebsiteAnalyzerService",
    "ClassificationService",
]
