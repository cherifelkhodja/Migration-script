"""
Module de gestion des workers en arriere-plan.

Fournit des workers pour executer des taches asynchrones
comme les recherches en arriere-plan.
"""

from src.infrastructure.workers.background_worker import (
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
