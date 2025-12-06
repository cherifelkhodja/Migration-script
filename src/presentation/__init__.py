"""
Presentation Layer - Interface utilisateur.

Cette couche contient les composants de l'interface utilisateur
qui interagissent avec les use cases de l'application.
"""

from src.presentation.view_models.search_view_model import SearchViewModel
from src.presentation.view_models.page_view_model import PageViewModel

__all__ = [
    "SearchViewModel",
    "PageViewModel",
]
