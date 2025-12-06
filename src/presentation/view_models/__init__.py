"""
View Models - Modeles de vue pour la presentation.

Les View Models encapsulent la logique de presentation
et fournissent des donnees formatees pour l'interface utilisateur.
"""

from src.presentation.view_models.search_view_model import SearchViewModel
from src.presentation.view_models.page_view_model import PageViewModel

__all__ = [
    "SearchViewModel",
    "PageViewModel",
]
