"""
Use Cases de l'application.

Les Use Cases orchestrent les entites du domaine et les services
externes pour realiser les fonctionnalites de l'application.

Chaque Use Case:
    - A une seule responsabilite
    - Utilise les ports (interfaces) pour les dependances
    - Ne connait pas les details d'implementation
"""

from src.application.use_cases.analyze_website import AnalyzeWebsiteUseCase
from src.application.use_cases.classify_sites import ClassifySitesUseCase
from src.application.use_cases.detect_winning_ads import DetectWinningAdsUseCase
from src.application.use_cases.search_ads import SearchAdsUseCase

__all__ = [
    "SearchAdsUseCase",
    "AnalyzeWebsiteUseCase",
    "ClassifySitesUseCase",
    "DetectWinningAdsUseCase",
]
