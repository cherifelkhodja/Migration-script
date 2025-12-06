"""
Module Background Worker - Shim de compatibilite.

Ce module redirige vers src.infrastructure.workers pour la compatibilite
avec le code existant.
"""

# Re-export depuis la nouvelle localisation
from src.infrastructure.workers import (  # noqa: F401
    SearchTask,
    BackgroundSearchWorker,
    get_worker,
    init_worker,
    shutdown_worker,
)

__all__ = [
    "SearchTask",
    "BackgroundSearchWorker",
    "get_worker",
    "init_worker",
    "shutdown_worker",
]
