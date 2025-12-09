"""
Design System - Layouts de pages.

Ce module contient les layouts réutilisables pour structurer les pages :
- page_header: En-tête de page avec titre, breadcrumb et actions
- page_layout: Layout complet avec header, filtres et contenu
- two_column_layout: Layout à deux colonnes
- dashboard_layout: Layout pour tableaux de bord avec KPIs

Usage:
    from src.presentation.streamlit.ui.layouts import (
        page_header, page_layout, dashboard_layout
    )

Principes:
    - Chaque page doit utiliser un layout standard
    - Les layouts garantissent la cohérence visuelle
    - Ils gèrent le responsive (via Streamlit)
"""

import streamlit as st
from typing import Literal, Optional, List, Dict, Any, Callable

from .theme import (
    COLORS, ICONS, SPACING, TYPOGRAPHY,
    apply_theme, is_dark_mode
)
from .atoms import divider
from .molecules import (
    filter_bar, active_filters_display, section_header,
    stats_row, empty_state
)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════

def page_header(
    title: str,
    subtitle: str = None,
    icon: str = None,
    breadcrumb: List[str] = None,
    actions: List[Dict[str, Any]] = None,
    show_divider: bool = True,
):
    """
    En-tête de page standardisé.

    Args:
        title: Titre de la page
        subtitle: Description sous le titre
        icon: Icône emoji
        breadcrumb: Fil d'Ariane ["Accueil", "Section", "Page"]
        actions: Boutons d'action [{label, icon, callback, key, primary}]
        show_divider: Afficher la ligne de séparation

    Example:
        page_header(
            title="Winning Ads",
            subtitle="Annonces performantes détectées",
            icon="🏆",
            actions=[{"label": "Exporter", "icon": "📥", "callback": export_fn}]
        )
    """
    # Breadcrumb
    if breadcrumb:
        crumbs = " > ".join(breadcrumb)
        st.caption(f"📍 {crumbs}")

    # Header row avec titre et actions
    if actions:
        col_title, col_actions = st.columns([3, 2])
    else:
        col_title = st.container()
        col_actions = None

    with col_title:
        # Titre avec icône
        display_title = f"{icon} {title}" if icon else title
        st.title(display_title)

        # Sous-titre
        if subtitle:
            st.markdown(f"*{subtitle}*")

    # Actions
    if actions and col_actions:
        with col_actions:
            action_cols = st.columns(len(actions))
            for i, action in enumerate(actions):
                with action_cols[i]:
                    btn_type = "primary" if action.get("primary") else "secondary"
                    label = f"{action.get('icon', '')} {action.get('label', '')}".strip()

                    if st.button(
                        label,
                        key=action.get("key", f"header_action_{i}"),
                        type=btn_type,
                        use_container_width=True
                    ):
                        if action.get("callback"):
                            action["callback"]()

    if show_divider:
        st.markdown("---")


def page_subheader(
    title: str,
    subtitle: str = None,
    icon: str = None,
    help_text: str = None,
):
    """
    Sous-titre de section dans une page.

    Args:
        title: Titre de la section
        subtitle: Description
        icon: Icône emoji
        help_text: Tooltip d'aide
    """
    display_title = f"{icon} {title}" if icon else title

    if help_text:
        col1, col2 = st.columns([10, 1])
        with col1:
            st.subheader(display_title)
        with col2:
            st.markdown(f"<span title='{help_text}' style='cursor: help;'>ℹ️</span>", unsafe_allow_html=True)
    else:
        st.subheader(display_title)

    if subtitle:
        st.caption(subtitle)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUTS
# ═══════════════════════════════════════════════════════════════════════════════

def page_layout(
    title: str,
    subtitle: str = None,
    icon: str = None,
    show_filters: bool = False,
    filter_config: Dict[str, bool] = None,
    db=None,
    user_id: str = None,
    key_prefix: str = "",
) -> Dict[str, Any]:
    """
    Layout de page standard avec header et filtres optionnels.

    Args:
        title: Titre de la page
        subtitle: Description
        icon: Icône
        show_filters: Afficher la barre de filtres
        filter_config: Configuration des filtres {show_thematique, show_pays, ...}
        db: DatabaseManager pour les filtres
        user_id: ID utilisateur
        key_prefix: Préfixe pour les clés

    Returns:
        Dict avec les valeurs des filtres si activés

    Example:
        filters = page_layout(
            title="Pages / Shops",
            icon="🏪",
            show_filters=True,
            filter_config={"show_state": True, "show_cms": True},
            db=db
        )
        # Utiliser filters["state"], filters["cms"], etc.
    """
    # Appliquer le thème
    apply_theme()

    # Header
    page_header(title=title, subtitle=subtitle, icon=icon)

    # Filtres
    filters = {}
    if show_filters and db:
        config = filter_config or {}
        with st.container():
            st.markdown("#### 🔍 Filtres")
            filters = filter_bar(
                db=db,
                key_prefix=key_prefix or title.lower().replace(" ", "_"),
                user_id=user_id,
                **config
            )
            active_filters_display(filters)
            st.markdown("---")

    return filters


def results_layout(
    data: Any,
    columns_config: Dict = None,
    empty_message: str = "Aucun résultat",
    empty_suggestion: str = None,
    empty_icon: str = "📭",
    show_count: bool = True,
    show_export: bool = True,
    export_filename: str = "export.csv",
    height: int = None,
):
    """
    Layout pour afficher des résultats avec export.

    Args:
        data: DataFrame ou liste de dicts
        columns_config: Configuration des colonnes
        empty_message: Message si pas de données
        empty_suggestion: Suggestion si vide
        empty_icon: Icône pour état vide
        show_count: Afficher le compteur
        show_export: Afficher le bouton d'export
        export_filename: Nom du fichier d'export
        height: Hauteur du tableau
    """
    import pandas as pd

    # Convertir en DataFrame si nécessaire
    if isinstance(data, list):
        df = pd.DataFrame(data) if data else pd.DataFrame()
    else:
        df = data if data is not None else pd.DataFrame()

    # État vide
    if df is None or len(df) == 0:
        empty_state(
            title=empty_message,
            description=empty_suggestion,
            icon=empty_icon
        )
        return

    # Header avec count et export
    col1, col2 = st.columns([3, 1])

    with col1:
        if show_count:
            st.caption(f"📊 {len(df)} résultat(s)")

    with col2:
        if show_export:
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                "📥 Exporter",
                csv,
                export_filename,
                "text/csv",
                key=f"export_{export_filename}",
            )

    # Tableau
    st.dataframe(
        df,
        column_config=columns_config,
        height=height,
        hide_index=True,
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

def dashboard_layout(
    title: str = "Dashboard",
    subtitle: str = None,
    icon: str = "🏠",
    kpis: List[Dict[str, Any]] = None,
    show_filters: bool = False,
    filter_config: Dict = None,
    db=None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Layout pour tableau de bord avec KPIs.

    Args:
        title: Titre
        subtitle: Description
        icon: Icône
        kpis: Liste de KPIs [{label, value, delta, icon}]
        show_filters: Afficher les filtres
        filter_config: Config des filtres
        db: DatabaseManager
        user_id: ID utilisateur

    Returns:
        Dict des filtres
    """
    # Appliquer le thème
    apply_theme()

    # Header
    page_header(title=title, subtitle=subtitle, icon=icon)

    # Filtres
    filters = {}
    if show_filters and db:
        config = filter_config or {}
        filters = filter_bar(
            db=db,
            key_prefix="dashboard",
            user_id=user_id,
            **config
        )
        if any(filters.values()):
            active_filters_display(filters)
        st.markdown("---")

    # KPIs
    if kpis:
        stats_row(kpis)
        st.markdown("---")

    return filters


def kpi_row(
    kpis: List[Dict[str, Any]],
    columns: int = None,
):
    """
    Ligne de KPIs pour dashboard.

    Args:
        kpis: Liste [{label, value, delta, delta_suffix, icon, help}]
        columns: Nombre de colonnes (auto si None)
    """
    num_cols = columns or min(len(kpis), 5)
    cols = st.columns(num_cols)

    for i, kpi in enumerate(kpis):
        with cols[i % num_cols]:
            label = kpi.get("label", "")
            if kpi.get("icon"):
                label = f"{kpi['icon']} {label}"

            delta = None
            if kpi.get("delta") is not None:
                delta = kpi["delta"]
                if kpi.get("delta_suffix"):
                    delta = f"{delta}{kpi['delta_suffix']}"

            st.metric(
                label=label,
                value=kpi.get("value", "-"),
                delta=delta,
                help=kpi.get("help"),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-COLUMN LAYOUTS
# ═══════════════════════════════════════════════════════════════════════════════

def two_column_layout(
    left_width: int = 2,
    right_width: int = 1,
    gap: str = "medium",
):
    """
    Layout à deux colonnes.

    Args:
        left_width: Poids de la colonne gauche
        right_width: Poids de la colonne droite
        gap: Espacement (small, medium, large)

    Returns:
        Tuple (left_col, right_col)
    """
    return st.columns([left_width, right_width], gap=gap)


def three_column_layout(
    weights: List[int] = None,
    gap: str = "medium",
):
    """
    Layout à trois colonnes.

    Args:
        weights: Poids des colonnes [1, 2, 1]
        gap: Espacement

    Returns:
        Tuple des colonnes
    """
    weights = weights or [1, 1, 1]
    return st.columns(weights, gap=gap)


def sidebar_main_layout():
    """
    Layout sidebar + contenu principal.

    Returns:
        Tuple (sidebar, main)

    Note:
        Utiliser avec st.sidebar pour la sidebar
    """
    return st.sidebar, st.container()


# ═══════════════════════════════════════════════════════════════════════════════
# FORM LAYOUTS
# ═══════════════════════════════════════════════════════════════════════════════

def form_section(
    title: str,
    description: str = None,
    icon: str = None,
):
    """
    Section de formulaire.

    Args:
        title: Titre de la section
        description: Description
        icon: Icône

    Returns:
        Container pour le contenu
    """
    display_title = f"{icon} {title}" if icon else title
    st.markdown(f"**{display_title}**")

    if description:
        st.caption(description)

    return st.container()


def form_row(columns: int = 2):
    """
    Ligne de formulaire avec colonnes.

    Args:
        columns: Nombre de colonnes

    Returns:
        Colonnes
    """
    return st.columns(columns)


def form_actions(
    submit_label: str = "Enregistrer",
    submit_icon: str = "💾",
    cancel_label: str = "Annuler",
    cancel_callback: Callable = None,
    disabled: bool = False,
    key_prefix: str = "form",
) -> bool:
    """
    Boutons d'action de formulaire.

    Args:
        submit_label: Label du bouton submit
        submit_icon: Icône du submit
        cancel_label: Label du bouton annuler
        cancel_callback: Callback d'annulation
        disabled: Désactiver les boutons
        key_prefix: Préfixe des clés

    Returns:
        True si submit cliqué
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        submitted = st.button(
            f"{submit_icon} {submit_label}",
            type="primary",
            disabled=disabled,
            use_container_width=True,
            key=f"{key_prefix}_submit"
        )

    with col2:
        if cancel_callback:
            if st.button(
                cancel_label,
                type="secondary",
                use_container_width=True,
                key=f"{key_prefix}_cancel"
            ):
                cancel_callback()

    return submitted


# ═══════════════════════════════════════════════════════════════════════════════
# TABS LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

def tabbed_layout(
    tabs: List[Dict[str, Any]],
) -> List:
    """
    Layout avec onglets.

    Args:
        tabs: Liste de [{label, icon, count}]

    Returns:
        Liste des conteneurs de tabs

    Example:
        tab_pages, tab_ads, tab_winning = tabbed_layout([
            {"label": "Pages", "icon": "📄", "count": 10},
            {"label": "Ads", "icon": "📢", "count": 100},
            {"label": "Winning", "icon": "🏆", "count": 5},
        ])

        with tab_pages:
            st.write("Contenu pages")
    """
    labels = []
    for tab in tabs:
        label = f"{tab.get('icon', '')} {tab['label']}".strip()
        if tab.get("count") is not None:
            label += f" ({tab['count']})"
        labels.append(label)

    return st.tabs(labels)


# ═══════════════════════════════════════════════════════════════════════════════
# CARD GRID
# ═══════════════════════════════════════════════════════════════════════════════

def card_grid(
    items: List[Dict[str, Any]],
    columns: int = 3,
    render_func: Callable = None,
    key_prefix: str = "card",
):
    """
    Grille de cartes.

    Args:
        items: Liste d'items à afficher
        columns: Nombre de colonnes
        render_func: Fonction de rendu pour chaque item
        key_prefix: Préfixe des clés

    Example:
        card_grid(
            items=pages,
            columns=3,
            render_func=lambda item, key: page_card(**item, key_prefix=key)
        )
    """
    if not items:
        empty_state("Aucun élément à afficher")
        return

    rows = [items[i:i + columns] for i in range(0, len(items), columns)]

    for row_idx, row in enumerate(rows):
        cols = st.columns(columns)
        for col_idx, item in enumerate(row):
            with cols[col_idx]:
                if render_func:
                    render_func(item, f"{key_prefix}_{row_idx}_{col_idx}")
                else:
                    st.write(item)


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL-LIKE LAYOUTS
# ═══════════════════════════════════════════════════════════════════════════════

def dialog_layout(
    title: str,
    icon: str = None,
    width: Literal["small", "medium", "large"] = "medium",
):
    """
    Layout de type dialog/modal (via expander).

    Args:
        title: Titre du dialog
        icon: Icône
        width: Largeur (small, medium, large)

    Returns:
        Container pour le contenu
    """
    display_title = f"{icon} {title}" if icon else title

    # Simuler différentes largeurs avec colonnes
    if width == "small":
        _, col, _ = st.columns([1, 2, 1])
    elif width == "large":
        col = st.container()
    else:  # medium
        _, col, _ = st.columns([1, 4, 1])

    with col:
        with st.expander(display_title, expanded=True):
            return st.container()


def confirmation_dialog(
    message: str,
    confirm_label: str = "Confirmer",
    cancel_label: str = "Annuler",
    danger: bool = False,
    key: str = "confirm",
) -> Optional[bool]:
    """
    Dialog de confirmation.

    Args:
        message: Message de confirmation
        confirm_label: Label du bouton confirmer
        cancel_label: Label du bouton annuler
        danger: Style danger pour action destructive
        key: Clé unique

    Returns:
        True si confirmé, False si annulé, None si pas encore répondu
    """
    st.warning(message) if danger else st.info(message)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            confirm_label,
            type="primary" if not danger else "secondary",
            use_container_width=True,
            key=f"{key}_confirm"
        ):
            return True

    with col2:
        if st.button(
            cancel_label,
            type="secondary",
            use_container_width=True,
            key=f"{key}_cancel"
        ):
            return False

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Page headers
    "page_header",
    "page_subheader",

    # Page layouts
    "page_layout",
    "results_layout",

    # Dashboard
    "dashboard_layout",
    "kpi_row",

    # Multi-column
    "two_column_layout",
    "three_column_layout",
    "sidebar_main_layout",

    # Forms
    "form_section",
    "form_row",
    "form_actions",

    # Tabs
    "tabbed_layout",

    # Cards
    "card_grid",

    # Dialogs
    "dialog_layout",
    "confirmation_dialog",
]
