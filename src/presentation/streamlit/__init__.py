"""
Presentation layer - Streamlit Dashboard.

Ce module contient l'application Streamlit principale
pour l'interface utilisateur.
"""

from src.presentation.streamlit.components import (
    # Charts
    CHART_COLORS,
    CHART_LAYOUT,
    info_card,
    chart_header,
    create_horizontal_bar_chart,
    create_donut_chart,
    create_trend_chart,
    create_gauge_chart,
    create_metric_card,
    create_comparison_bars,
    # Badges
    STATE_COLORS,
    CMS_COLORS,
    get_state_badge,
    get_cms_badge,
    format_state_for_df,
    apply_custom_css,
    # Filters
    COUNTRY_NAMES,
    DATE_FILTER_OPTIONS,
    render_classification_filters,
    render_date_filter,
    apply_classification_filters,
    render_state_filter,
    render_cms_filter,
)

__all__ = [
    # Charts
    "CHART_COLORS",
    "CHART_LAYOUT",
    "info_card",
    "chart_header",
    "create_horizontal_bar_chart",
    "create_donut_chart",
    "create_trend_chart",
    "create_gauge_chart",
    "create_metric_card",
    "create_comparison_bars",
    # Badges
    "STATE_COLORS",
    "CMS_COLORS",
    "get_state_badge",
    "get_cms_badge",
    "format_state_for_df",
    "apply_custom_css",
    # Filters
    "COUNTRY_NAMES",
    "DATE_FILTER_OPTIONS",
    "render_classification_filters",
    "render_date_filter",
    "apply_classification_filters",
    "render_state_filter",
    "render_cms_filter",
]
