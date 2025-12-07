"""
Pages du dashboard Streamlit.

Structure modulaire pour les differentes sections de l'application.
"""

from src.presentation.streamlit.pages.blacklist import render_blacklist
from src.presentation.streamlit.pages.favorites import render_favorites
from src.presentation.streamlit.pages.collections import render_collections
from src.presentation.streamlit.pages.tags import render_tags
from src.presentation.streamlit.pages.scheduled_scans import render_scheduled_scans
from src.presentation.streamlit.pages.settings import render_settings
from src.presentation.streamlit.pages.winning_ads import render_winning_ads
from src.presentation.streamlit.pages.analytics import render_analytics
from src.presentation.streamlit.pages.search_logs import render_search_logs

__all__ = [
    "render_blacklist",
    "render_favorites",
    "render_collections",
    "render_tags",
    "render_scheduled_scans",
    "render_settings",
    "render_winning_ads",
    "render_analytics",
    "render_search_logs",
]
