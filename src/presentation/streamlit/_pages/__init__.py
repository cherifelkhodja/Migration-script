"""
Pages du dashboard Streamlit.

Structure modulaire pour les differentes sections de l'application.
"""

from src.presentation.streamlit._pages.blacklist import render_blacklist
from src.presentation.streamlit._pages.favorites import render_favorites
from src.presentation.streamlit._pages.collections import render_collections
from src.presentation.streamlit._pages.tags import render_tags
from src.presentation.streamlit._pages.scheduled_scans import render_scheduled_scans
from src.presentation.streamlit._pages.settings import render_settings
from src.presentation.streamlit._pages.winning_ads import render_winning_ads
from src.presentation.streamlit._pages.analytics import render_analytics
from src.presentation.streamlit._pages.search_logs import render_search_logs
from src.presentation.streamlit._pages.pages_shops import render_pages_shops
from src.presentation.streamlit._pages.monitoring import (
    render_watchlists, render_alerts, render_monitoring,
    detect_trends, generate_alerts
)
from src.presentation.streamlit._pages.creative import (
    render_creative_analysis, render_background_searches
)
# Search module (split into submodules)
from src.presentation.streamlit._pages.search import render_search_ads
from src.presentation.streamlit._pages.search_keyword import (
    render_keyword_search, run_search_process
)
from src.presentation.streamlit._pages.search_page_id import (
    render_page_id_search, run_page_id_search
)
from src.presentation.streamlit._pages.search_results import render_preview_results
from src.presentation.streamlit._pages.layout import (
    render_sidebar, render_dashboard
)

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
    "render_pages_shops",
    "render_watchlists",
    "render_alerts",
    "render_monitoring",
    "render_creative_analysis",
    "render_background_searches",
    "render_search_ads",
    "render_keyword_search",
    "render_page_id_search",
    "render_preview_results",
    "run_search_process",
    "run_page_id_search",
    "render_sidebar",
    "render_dashboard",
    "detect_trends",
    "generate_alerts",
]
