"""
Design System UI - Meta Ads Analyzer.

Ce package contient le Design System complet de l'application,
organisé selon les principes de l'Atomic Design :

- theme.py: Tokens de design (couleurs, espacements, typographies)
- atoms.py: Composants atomiques (boutons, badges, tags)
- molecules.py: Molécules (cards, filtres, sections)
- layouts.py: Layouts de pages
- organisms.py: Composants complexes (navigation, formulaires)

Usage rapide:
    from src.presentation.streamlit.ui import (
        # Theme
        apply_theme, COLORS, STATE_COLORS, ICONS,

        # Atoms
        primary_button, state_badge, cms_badge, format_number,

        # Molecules
        page_card, filter_bar, section_header, empty_state,

        # Layouts
        page_layout, dashboard_layout, results_layout,

        # Organisms
        render_navigation, search_form,
    )

    # Dans votre page:
    apply_theme()
    filters = page_layout(
        title="Ma Page",
        icon="📊",
        show_filters=True,
        db=db
    )

Architecture:
    Atoms → Molécules → Organismes → Pages

    Les atomes sont les briques de base (boutons, badges).
    Les molécules combinent plusieurs atomes (cards, filtres).
    Les organismes sont des sections complètes (navigation, formulaires).
    Les pages utilisent tous ces composants.

Conventions:
    - Toutes les couleurs viennent de theme.py
    - Les composants sont des fonctions pures quand possible
    - Les noms sont explicites et cohérents
    - Les docstrings documentent tous les paramètres
"""

# ═══════════════════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════════════════

from .theme import (
    # Palettes
    COLORS,
    COLORS_DARK,
    STATE_COLORS,
    STATE_ORDER,
    CMS_COLORS,
    CHART_COLORS,
    CHART_LAYOUT,

    # Design tokens
    SPACING,
    CONTAINER_PADDING,
    TYPOGRAPHY,
    BORDERS,
    SHADOWS,
    ICONS,
    COUNTRY_NAMES,

    # Fonctions
    get_color,
    get_state_color,
    get_cms_color,
    get_country_display,
    is_dark_mode,
    apply_theme,
    get_base_css,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ATOMS
# ═══════════════════════════════════════════════════════════════════════════════

from .atoms import (
    # Boutons
    primary_button,
    secondary_button,
    ghost_button,
    danger_button,
    icon_button,

    # Badges états
    state_badge,
    render_state_badge,
    state_indicator,

    # Badges CMS
    cms_badge,
    render_cms_badge,

    # Tags statuts
    status_tag,
    render_status_tag,
    StatusVariant,

    # Scores
    score_badge,
    render_score_badge,
    get_score_grade,

    # Deltas
    delta_indicator,
    render_delta_indicator,
    trend_icon,

    # Loading
    loading_spinner,
    loading_indicator,
    progress_indicator,

    # Textes
    text_muted,
    text_small,
    text_bold,
    text_highlight,
    render_text,

    # Formatage
    format_number,
    format_percentage,
    format_currency,
    format_time_elapsed,
    truncate_text,

    # Links
    external_link,
    render_external_link,

    # Dividers
    divider,
    divider_with_text,
)

# ═══════════════════════════════════════════════════════════════════════════════
# MOLECULES
# ═══════════════════════════════════════════════════════════════════════════════

from .molecules import (
    # Cards
    page_card,
    metric_card,
    info_card,
    stat_card,

    # Filtres
    filter_bar,
    active_filters_display,
    period_selector,

    # Sections
    section_header,
    collapsible_section,
    tabs_section,

    # Alertes
    alert,
    toast,
    feedback_message,

    # Empty states
    empty_state,
    no_data_state,
    no_results_state,

    # Data display
    data_table,
    key_value_list,
    export_button,

    # Progress
    step_progress,
    stats_row,
)

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUTS
# ═══════════════════════════════════════════════════════════════════════════════

from .layouts import (
    # Page headers
    page_header,
    page_subheader,

    # Page layouts
    page_layout,
    results_layout,

    # Dashboard
    dashboard_layout,
    kpi_row,

    # Multi-column
    two_column_layout,
    three_column_layout,
    sidebar_main_layout,

    # Forms
    form_section,
    form_row,
    form_actions,

    # Tabs
    tabbed_layout,

    # Cards
    card_grid,

    # Dialogs
    dialog_layout,
    confirmation_dialog,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ORGANISMS
# ═══════════════════════════════════════════════════════════════════════════════

from .organisms import (
    # Navigation
    NAVIGATION_CONFIG,
    render_navigation,
    render_simple_sidebar,

    # Header
    render_app_header,

    # Forms
    search_form,

    # Tables
    paginated_table,
    sortable_table,
)

# ═══════════════════════════════════════════════════════════════════════════════
# VERSION
# ═══════════════════════════════════════════════════════════════════════════════

__version__ = "1.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Theme
    "COLORS",
    "COLORS_DARK",
    "STATE_COLORS",
    "STATE_ORDER",
    "CMS_COLORS",
    "CHART_COLORS",
    "CHART_LAYOUT",
    "SPACING",
    "CONTAINER_PADDING",
    "TYPOGRAPHY",
    "BORDERS",
    "SHADOWS",
    "ICONS",
    "COUNTRY_NAMES",
    "get_color",
    "get_state_color",
    "get_cms_color",
    "get_country_display",
    "is_dark_mode",
    "apply_theme",
    "get_base_css",

    # Atoms
    "primary_button",
    "secondary_button",
    "ghost_button",
    "danger_button",
    "icon_button",
    "state_badge",
    "render_state_badge",
    "state_indicator",
    "cms_badge",
    "render_cms_badge",
    "status_tag",
    "render_status_tag",
    "StatusVariant",
    "score_badge",
    "render_score_badge",
    "get_score_grade",
    "delta_indicator",
    "render_delta_indicator",
    "trend_icon",
    "loading_spinner",
    "loading_indicator",
    "progress_indicator",
    "text_muted",
    "text_small",
    "text_bold",
    "text_highlight",
    "render_text",
    "format_number",
    "format_percentage",
    "format_currency",
    "format_time_elapsed",
    "truncate_text",
    "external_link",
    "render_external_link",
    "divider",
    "divider_with_text",

    # Molecules
    "page_card",
    "metric_card",
    "info_card",
    "stat_card",
    "filter_bar",
    "active_filters_display",
    "period_selector",
    "section_header",
    "collapsible_section",
    "tabs_section",
    "alert",
    "toast",
    "feedback_message",
    "empty_state",
    "no_data_state",
    "no_results_state",
    "data_table",
    "key_value_list",
    "export_button",
    "step_progress",
    "stats_row",

    # Layouts
    "page_header",
    "page_subheader",
    "page_layout",
    "results_layout",
    "dashboard_layout",
    "kpi_row",
    "two_column_layout",
    "three_column_layout",
    "sidebar_main_layout",
    "form_section",
    "form_row",
    "form_actions",
    "tabbed_layout",
    "card_grid",
    "dialog_layout",
    "confirmation_dialog",

    # Organisms
    "NAVIGATION_CONFIG",
    "render_navigation",
    "render_simple_sidebar",
    "render_app_header",
    "search_form",
    "paginated_table",
    "sortable_table",
]
