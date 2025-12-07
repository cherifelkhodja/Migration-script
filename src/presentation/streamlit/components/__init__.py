"""
Composants réutilisables pour le dashboard Streamlit.

Ce module expose les composants UI comme les graphiques,
badges, filtres et autres éléments d'interface.
"""

from src.presentation.streamlit.components.charts import (
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
)

from src.presentation.streamlit.components.badges import (
    STATE_COLORS,
    CMS_COLORS,
    get_state_badge,
    get_cms_badge,
    format_state_for_df,
    apply_custom_css,
)

from src.presentation.streamlit.components.filters import (
    COUNTRY_NAMES,
    DATE_FILTER_OPTIONS,
    render_classification_filters,
    render_date_filter,
    apply_classification_filters,
    render_state_filter,
    render_cms_filter,
)

from src.presentation.streamlit.components.utils import (
    calculate_page_score,
    get_score_color,
    get_score_level,
    export_to_csv,
    df_to_csv,
    format_number,
    format_percentage,
    format_time_elapsed,
    truncate_text,
    get_delta_indicator,
)

from src.presentation.streamlit.components.progress import (
    SearchProgressTracker,
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
    # Utils
    "calculate_page_score",
    "get_score_color",
    "get_score_level",
    "export_to_csv",
    "df_to_csv",
    "format_number",
    "format_percentage",
    "format_time_elapsed",
    "truncate_text",
    "get_delta_indicator",
    # Progress
    "SearchProgressTracker",
]
