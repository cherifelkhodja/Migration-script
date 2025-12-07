"""
Pages du dashboard Streamlit.

Structure modulaire pour les differentes sections de l'application.
"""

from src.presentation.streamlit.pages.blacklist import render_blacklist
from src.presentation.streamlit.pages.favorites import render_favorites
from src.presentation.streamlit.pages.collections import render_collections
from src.presentation.streamlit.pages.tags import render_tags
from src.presentation.streamlit.pages.scheduled_scans import render_scheduled_scans

__all__ = [
    "render_blacklist",
    "render_favorites",
    "render_collections",
    "render_tags",
    "render_scheduled_scans",
]
