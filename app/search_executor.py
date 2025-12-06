"""
Module Search Executor - Shim de compatibilite.

Ce module redirige vers src.application.use_cases pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.application.use_cases.search_executor import (  # noqa: F401
    BackgroundProgressTracker,
    execute_background_search,
)

__all__ = [
    "BackgroundProgressTracker",
    "execute_background_search",
]
