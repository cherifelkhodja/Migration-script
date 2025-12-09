"""
Design System - Molécules (Composants composés).

Ce module contient les molécules du Design System, composées d'atomes :
- Cards (page, métrique, info)
- Filtres (classification, période, état, CMS)
- Sections (header, contenu, actions)
- Alertes et feedbacks
- Empty states
- Data displays

Usage:
    from src.presentation.streamlit.ui.molecules import (
        page_card, metric_card, filter_bar, section_header, empty_state
    )

Principes:
    - Les molécules combinent plusieurs atomes
    - Elles représentent des patterns UI récurrents
    - Elles sont autonomes et configurables
"""

import streamlit as st
import pandas as pd
from typing import Literal, Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta

from .theme import (
    COLORS, STATE_COLORS, CMS_COLORS, ICONS, COUNTRY_NAMES,
    SPACING, BORDERS, TYPOGRAPHY,
    get_state_color, get_cms_color, get_country_display
)
from .atoms import (
    state_badge, cms_badge, status_tag, score_badge,
    format_number, format_percentage, truncate_text,
    primary_button, secondary_button,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CARDS
# ═══════════════════════════════════════════════════════════════════════════════

def page_card(
    page_name: str,
    page_id: str,
    cms: str = "Unknown",
    state: str = "XS",
    ads_count: int = 0,
    winning_count: int = 0,
    site_url: str = None,
    score: int = None,
    thematique: str = None,
    on_click: Callable = None,
    actions: List[Dict] = None,
    key_prefix: str = "",
):
    """
    Carte de présentation d'une page Facebook/Shop.

    Args:
        page_name: Nom de la page
        page_id: ID Facebook de la page
        cms: CMS détecté (Shopify, WooCommerce, etc.)
        state: État de la page (XXL, XL, L, M, S, XS)
        ads_count: Nombre d'ads actives
        winning_count: Nombre de winning ads
        site_url: URL du site
        score: Score de la page (0-100)
        thematique: Catégorie thématique
        on_click: Callback au clic
        actions: Liste d'actions [{label, icon, callback, key}]
        key_prefix: Préfixe pour les clés Streamlit
    """
    with st.container():
        # Header avec nom et badges
        col_main, col_badges = st.columns([3, 2])

        with col_main:
            # Nom de la page (cliquable si callback)
            if on_click:
                if st.button(f"**{truncate_text(page_name, 40)}**", key=f"{key_prefix}_name_{page_id}"):
                    on_click(page_id)
            else:
                st.markdown(f"**{truncate_text(page_name, 40)}**")

            # Sous-titre avec site
            if site_url:
                st.caption(f"🔗 {truncate_text(site_url, 35)}")

        with col_badges:
            # Badges état et CMS
            badges_html = f"{state_badge(state)} {cms_badge(cms)}"
            st.markdown(badges_html, unsafe_allow_html=True)

        # Métriques
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric("Ads", format_number(ads_count))
        with m2:
            st.metric("Winning", winning_count, delta=None if winning_count == 0 else f"+{winning_count}")
        with m3:
            if score is not None:
                st.markdown(score_badge(score), unsafe_allow_html=True)
            else:
                st.metric("Score", "-")
        with m4:
            if thematique:
                st.caption(f"🏷️ {truncate_text(thematique, 15)}")

        # Actions
        if actions:
            action_cols = st.columns(len(actions))
            for i, action in enumerate(actions):
                with action_cols[i]:
                    label = f"{action.get('icon', '')} {action.get('label', '')}"
                    if st.button(label, key=f"{key_prefix}_action_{i}_{page_id}"):
                        if action.get("callback"):
                            action["callback"](page_id)

        st.markdown("---")


def metric_card(
    label: str,
    value: Any,
    delta: Any = None,
    delta_suffix: str = "",
    icon: str = None,
    help_text: str = None,
    variant: Literal["default", "success", "warning", "danger"] = "default",
):
    """
    Carte de métrique stylisée.

    Args:
        label: Label de la métrique
        value: Valeur à afficher
        delta: Variation (optionnel)
        delta_suffix: Suffixe du delta (ex: "%", " ads")
        icon: Icône emoji
        help_text: Texte d'aide
        variant: Variante de couleur
    """
    # Déterminer la couleur du delta
    delta_color = "normal"
    if variant == "danger" or (isinstance(delta, (int, float)) and delta < 0):
        delta_color = "inverse"

    # Formater le delta
    delta_str = None
    if delta is not None:
        if isinstance(delta, (int, float)):
            sign = "+" if delta > 0 else ""
            delta_str = f"{sign}{delta}{delta_suffix}"
        else:
            delta_str = str(delta)

    # Afficher avec ou sans icône
    display_label = f"{icon} {label}" if icon else label

    st.metric(
        label=display_label,
        value=value,
        delta=delta_str,
        delta_color=delta_color,
        help=help_text,
    )


def info_card(
    title: str,
    content: str,
    icon: str = "💡",
    expanded: bool = False,
):
    """
    Carte d'information expandable.

    Args:
        title: Titre de la carte
        content: Contenu HTML
        icon: Icône emoji
        expanded: Ouverte par défaut
    """
    with st.expander(f"{icon} {title}", expanded=expanded):
        st.markdown(
            f'<p style="color: {COLORS["neutral_600"]}; font-size: 14px; line-height: 1.6;">{content}</p>',
            unsafe_allow_html=True
        )


def stat_card(
    title: str,
    stats: List[Dict[str, Any]],
    columns: int = 4,
):
    """
    Carte avec plusieurs statistiques.

    Args:
        title: Titre de la section
        stats: Liste de stats [{label, value, delta, icon}]
        columns: Nombre de colonnes
    """
    if title:
        st.markdown(f"**{title}**")

    cols = st.columns(columns)
    for i, stat in enumerate(stats):
        with cols[i % columns]:
            metric_card(
                label=stat.get("label", ""),
                value=stat.get("value", "-"),
                delta=stat.get("delta"),
                icon=stat.get("icon"),
                help_text=stat.get("help"),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# FILTRES
# ═══════════════════════════════════════════════════════════════════════════════

def filter_bar(
    db,
    key_prefix: str = "",
    show_thematique: bool = True,
    show_subcategory: bool = True,
    show_pays: bool = True,
    show_period: bool = False,
    show_state: bool = False,
    show_cms: bool = False,
    show_search: bool = False,
    columns: int = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Barre de filtres unifiée et réutilisable.

    Args:
        db: DatabaseManager
        key_prefix: Préfixe pour les clés Streamlit
        show_thematique: Afficher filtre thématique
        show_subcategory: Afficher filtre sous-catégorie
        show_pays: Afficher filtre pays
        show_period: Afficher filtre période
        show_state: Afficher filtre état
        show_cms: Afficher filtre CMS
        show_search: Afficher champ de recherche
        columns: Nombre de colonnes (auto si None)
        user_id: ID utilisateur pour multi-tenancy

    Returns:
        Dict avec toutes les valeurs de filtres
    """
    from src.infrastructure.persistence.database import (
        get_taxonomy_categories, get_all_subcategories, get_all_countries
    )

    result = {
        "thematique": None,
        "subcategory": None,
        "pays": None,
        "period_days": 0,
        "state": None,
        "cms": None,
        "search": None,
    }

    # Compter les filtres actifs pour déterminer le nombre de colonnes
    active_filters = sum([
        show_thematique, show_subcategory, show_pays,
        show_period, show_state, show_cms, show_search
    ])

    if active_filters == 0:
        return result

    num_cols = columns or min(active_filters, 4)
    cols = st.columns(num_cols)
    col_idx = 0

    # Recherche textuelle
    if show_search:
        with cols[col_idx % num_cols]:
            result["search"] = st.text_input(
                "🔍 Rechercher",
                placeholder="Nom, ID, URL...",
                key=f"{key_prefix}_search"
            )
        col_idx += 1

    # Thématique
    selected_thematique = "Toutes"
    if show_thematique:
        with cols[col_idx % num_cols]:
            categories = get_taxonomy_categories(db, user_id=user_id) if db else []
            options = ["Toutes"] + categories
            selected_thematique = st.selectbox(
                "🏷️ Thématique",
                options,
                index=0,
                key=f"{key_prefix}_thematique"
            )
            if selected_thematique != "Toutes":
                result["thematique"] = selected_thematique
        col_idx += 1

    # Sous-catégorie (dépend de la thématique)
    if show_subcategory:
        with cols[col_idx % num_cols]:
            if db:
                if selected_thematique != "Toutes":
                    subcategories = get_all_subcategories(db, category=selected_thematique, user_id=user_id)
                else:
                    subcategories = get_all_subcategories(db, user_id=user_id)
            else:
                subcategories = []

            options = ["Toutes"] + subcategories
            selected = st.selectbox(
                "📂 Classification",
                options,
                index=0,
                key=f"{key_prefix}_subcategory"
            )
            if selected != "Toutes":
                result["subcategory"] = selected
        col_idx += 1

    # Pays
    if show_pays:
        with cols[col_idx % num_cols]:
            countries = get_all_countries(db, user_id=user_id) if db else list(COUNTRY_NAMES.keys())
            display_options = ["Tous"] + [get_country_display(c) for c in countries]
            values = [None] + countries

            selected_idx = st.selectbox(
                "🌍 Pays",
                range(len(display_options)),
                format_func=lambda i: display_options[i],
                index=0,
                key=f"{key_prefix}_pays"
            )
            if selected_idx > 0:
                result["pays"] = values[selected_idx]
        col_idx += 1

    # Période
    if show_period:
        with cols[col_idx % num_cols]:
            period_options = {
                "Toutes": 0,
                "24h": 1,
                "7 jours": 7,
                "30 jours": 30,
                "90 jours": 90,
            }
            selected = st.selectbox(
                "📅 Période",
                list(period_options.keys()),
                index=3,  # 30 jours par défaut
                key=f"{key_prefix}_period"
            )
            result["period_days"] = period_options[selected]
        col_idx += 1

    # État
    if show_state:
        with cols[col_idx % num_cols]:
            state_options = ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"]
            selected = st.selectbox(
                "📊 État",
                state_options,
                index=0,
                key=f"{key_prefix}_state"
            )
            if selected != "Tous":
                result["state"] = selected
        col_idx += 1

    # CMS
    if show_cms:
        with cols[col_idx % num_cols]:
            cms_options = ["Tous"] + list(CMS_COLORS.keys())
            selected = st.selectbox(
                "🛒 CMS",
                cms_options,
                index=0,
                key=f"{key_prefix}_cms"
            )
            if selected != "Tous":
                result["cms"] = selected
        col_idx += 1

    return result


def active_filters_display(filters: Dict[str, Any]):
    """
    Affiche les filtres actifs sous forme de tags.

    Args:
        filters: Dict de filtres (de filter_bar)
    """
    active = []

    if filters.get("search"):
        active.append(f"🔍 \"{filters['search']}\"")
    if filters.get("thematique"):
        active.append(f"🏷️ {filters['thematique']}")
    if filters.get("subcategory"):
        active.append(f"📂 {filters['subcategory']}")
    if filters.get("pays"):
        active.append(get_country_display(filters['pays']))
    if filters.get("period_days") and filters["period_days"] > 0:
        active.append(f"📅 {filters['period_days']}j")
    if filters.get("state"):
        active.append(f"📊 {filters['state']}")
    if filters.get("cms"):
        active.append(f"🛒 {filters['cms']}")

    if active:
        st.caption(f"Filtres actifs : {' • '.join(active)}")


def period_selector(
    key_prefix: str = "",
    default_days: int = 30,
    options: List[int] = None,
) -> int:
    """
    Sélecteur de période simplifié.

    Args:
        key_prefix: Préfixe pour la clé Streamlit
        default_days: Jours par défaut
        options: Liste des options en jours

    Returns:
        Nombre de jours sélectionné
    """
    if options is None:
        options = [7, 14, 30, 60, 90]

    labels = {d: f"{d} jours" for d in options}

    # Trouver l'index par défaut
    default_idx = options.index(default_days) if default_days in options else 2

    selected = st.selectbox(
        "📅 Période",
        options,
        format_func=lambda x: labels.get(x, f"{x} jours"),
        index=default_idx,
        key=f"{key_prefix}_period_selector"
    )

    return selected


# ═══════════════════════════════════════════════════════════════════════════════
# SECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def section_header(
    title: str,
    subtitle: str = None,
    icon: str = None,
    help_text: str = None,
    action_label: str = None,
    action_callback: Callable = None,
    action_key: str = None,
):
    """
    Header de section avec titre, sous-titre et action optionnelle.

    Args:
        title: Titre principal
        subtitle: Sous-titre descriptif
        icon: Icône emoji
        help_text: Texte d'aide au survol
        action_label: Label du bouton d'action
        action_callback: Callback de l'action
        action_key: Clé du bouton
    """
    col_title, col_action = st.columns([4, 1])

    with col_title:
        display_title = f"{icon} {title}" if icon else title
        if help_text:
            st.markdown(f"### {display_title}")
            st.caption(f"ℹ️ {help_text}")
        else:
            st.markdown(f"### {display_title}")

        if subtitle:
            st.caption(subtitle)

    with col_action:
        if action_label and action_callback:
            if st.button(action_label, key=action_key or f"section_action_{title}"):
                action_callback()


def collapsible_section(
    title: str,
    icon: str = None,
    expanded: bool = True,
    badge_count: int = None,
):
    """
    Section collapsible avec compteur optionnel.

    Args:
        title: Titre de la section
        icon: Icône emoji
        expanded: Ouverte par défaut
        badge_count: Compteur à afficher dans le titre

    Returns:
        Context manager pour le contenu
    """
    display_title = f"{icon} {title}" if icon else title
    if badge_count is not None:
        display_title += f" ({badge_count})"

    return st.expander(display_title, expanded=expanded)


def tabs_section(
    tabs: List[Dict[str, Any]],
    key_prefix: str = "",
) -> str:
    """
    Section avec onglets.

    Args:
        tabs: Liste de tabs [{label, icon, count}]
        key_prefix: Préfixe pour les clés

    Returns:
        Label du tab sélectionné
    """
    tab_labels = []
    for tab in tabs:
        label = f"{tab.get('icon', '')} {tab['label']}"
        if tab.get("count") is not None:
            label += f" ({tab['count']})"
        tab_labels.append(label)

    return st.tabs(tab_labels)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERTES ET FEEDBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def alert(
    message: str,
    variant: Literal["info", "success", "warning", "error"] = "info",
    icon: str = None,
    dismissible: bool = False,
    key: str = None,
):
    """
    Alerte stylisée.

    Args:
        message: Message de l'alerte
        variant: Type d'alerte
        icon: Icône personnalisée
        dismissible: Peut être fermée
        key: Clé pour l'état dismissed
    """
    # Vérifier si dismissée
    if dismissible and key:
        if st.session_state.get(f"alert_dismissed_{key}", False):
            return

    # Icônes par défaut
    default_icons = {
        "info": ICONS["info"],
        "success": ICONS["success"],
        "warning": ICONS["warning"],
        "error": ICONS["error"],
    }

    display_icon = icon or default_icons.get(variant, "")
    display_message = f"{display_icon} {message}" if display_icon else message

    if variant == "success":
        st.success(display_message)
    elif variant == "warning":
        st.warning(display_message)
    elif variant == "error":
        st.error(display_message)
    else:
        st.info(display_message)

    if dismissible and key:
        if st.button("✕ Fermer", key=f"dismiss_{key}"):
            st.session_state[f"alert_dismissed_{key}"] = True
            st.rerun()


def toast(message: str, icon: str = None):
    """
    Notification toast.

    Args:
        message: Message à afficher
        icon: Icône emoji
    """
    st.toast(message, icon=icon)


def feedback_message(
    state: Literal["loading", "success", "error", "empty"],
    message: str = None,
    details: str = None,
):
    """
    Message de feedback contextuel.

    Args:
        state: État du feedback
        message: Message principal
        details: Détails supplémentaires
    """
    default_messages = {
        "loading": "Chargement en cours...",
        "success": "Opération réussie !",
        "error": "Une erreur est survenue",
        "empty": "Aucun résultat trouvé",
    }

    display_message = message or default_messages.get(state, "")

    if state == "loading":
        with st.spinner(display_message):
            pass
    elif state == "success":
        st.success(display_message)
    elif state == "error":
        st.error(display_message)
        if details:
            with st.expander("Détails de l'erreur"):
                st.code(details)
    elif state == "empty":
        empty_state(
            title=display_message,
            description=details,
            icon="📭",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EMPTY STATES
# ═══════════════════════════════════════════════════════════════════════════════

def empty_state(
    title: str = "Aucun résultat",
    description: str = None,
    icon: str = "📭",
    action_label: str = None,
    action_callback: Callable = None,
    action_key: str = None,
):
    """
    État vide avec message et action optionnelle.

    Args:
        title: Titre principal
        description: Description
        icon: Icône/emoji
        action_label: Label du bouton d'action
        action_callback: Callback de l'action
        action_key: Clé du bouton
    """
    st.markdown(f'''
        <div style="
            text-align: center;
            padding: {SPACING["2xl"]} {SPACING["xl"]};
            color: {COLORS["neutral_500"]};
        ">
            <div style="font-size: 3rem; margin-bottom: {SPACING["md"]}; opacity: 0.5;">
                {icon}
            </div>
            <div style="
                font-size: {TYPOGRAPHY["text_lg"]};
                font-weight: {TYPOGRAPHY["font_semibold"]};
                color: {COLORS["neutral_700"]};
                margin-bottom: {SPACING["sm"]};
            ">
                {title}
            </div>
            {f'<div style="font-size: {TYPOGRAPHY["text_sm"]}; color: {COLORS["neutral_500"]};">{description}</div>' if description else ''}
        </div>
    ''', unsafe_allow_html=True)

    if action_label and action_callback:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(action_label, key=action_key or "empty_state_action", type="primary"):
                action_callback()


def no_data_state(
    message: str = "Pas encore de données",
    suggestion: str = "Lancez une recherche pour commencer",
):
    """
    État sans données spécifique.

    Args:
        message: Message principal
        suggestion: Suggestion d'action
    """
    empty_state(
        title=message,
        description=suggestion,
        icon="📊",
    )


def no_results_state(
    search_term: str = None,
    suggestion: str = "Essayez avec d'autres critères",
):
    """
    État sans résultats de recherche.

    Args:
        search_term: Terme recherché
        suggestion: Suggestion
    """
    title = f"Aucun résultat pour \"{search_term}\"" if search_term else "Aucun résultat"
    empty_state(
        title=title,
        description=suggestion,
        icon="🔍",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA DISPLAY
# ═══════════════════════════════════════════════════════════════════════════════

def data_table(
    data: pd.DataFrame,
    columns_config: Dict[str, Any] = None,
    height: int = None,
    hide_index: bool = True,
    selection_mode: Literal["single", "multi", None] = None,
    key: str = None,
) -> Any:
    """
    Tableau de données stylisé.

    Args:
        data: DataFrame à afficher
        columns_config: Configuration des colonnes Streamlit
        height: Hauteur en pixels
        hide_index: Masquer l'index
        selection_mode: Mode de sélection
        key: Clé Streamlit

    Returns:
        Sélection si selection_mode actif
    """
    if data is None or len(data) == 0:
        no_results_state()
        return None

    return st.dataframe(
        data,
        column_config=columns_config,
        height=height,
        hide_index=hide_index,
        use_container_width=True,
        key=key,
    )


def key_value_list(
    items: List[Dict[str, Any]],
    columns: int = 2,
):
    """
    Liste clé-valeur en colonnes.

    Args:
        items: Liste de [{key, value, icon}]
        columns: Nombre de colonnes
    """
    cols = st.columns(columns)
    for i, item in enumerate(items):
        with cols[i % columns]:
            icon = item.get("icon", "")
            key = item.get("key", "")
            value = item.get("value", "-")

            st.markdown(f'''
                <div style="margin-bottom: {SPACING["sm"]};">
                    <div style="
                        font-size: {TYPOGRAPHY["text_xs"]};
                        color: {COLORS["neutral_500"]};
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                    ">{icon} {key}</div>
                    <div style="
                        font-size: {TYPOGRAPHY["text_base"]};
                        font-weight: {TYPOGRAPHY["font_semibold"]};
                        color: {COLORS["neutral_800"]};
                    ">{value}</div>
                </div>
            ''', unsafe_allow_html=True)


def export_button(
    data: Any,
    filename: str,
    label: str = "Exporter CSV",
    icon: str = "📥",
    key: str = None,
):
    """
    Bouton d'export CSV.

    Args:
        data: Données à exporter (DataFrame ou list of dicts)
        filename: Nom du fichier
        label: Label du bouton
        icon: Icône
        key: Clé Streamlit
    """
    if isinstance(data, pd.DataFrame):
        csv = data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    elif isinstance(data, list):
        df = pd.DataFrame(data)
        csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    else:
        return

    st.download_button(
        label=f"{icon} {label}",
        data=csv,
        file_name=filename,
        mime="text/csv",
        key=key or f"export_{filename}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS
# ═══════════════════════════════════════════════════════════════════════════════

def step_progress(
    current_step: int,
    total_steps: int,
    step_labels: List[str] = None,
):
    """
    Indicateur de progression par étapes.

    Args:
        current_step: Étape actuelle (1-indexed)
        total_steps: Nombre total d'étapes
        step_labels: Labels des étapes
    """
    progress = current_step / total_steps if total_steps > 0 else 0
    st.progress(progress)

    if step_labels and current_step <= len(step_labels):
        st.caption(f"Étape {current_step}/{total_steps} : {step_labels[current_step - 1]}")
    else:
        st.caption(f"Étape {current_step}/{total_steps}")


def stats_row(
    stats: List[Dict[str, Any]],
    columns: int = None,
):
    """
    Ligne de statistiques rapide.

    Args:
        stats: Liste de [{label, value, delta, icon}]
        columns: Nombre de colonnes (auto si None)
    """
    num_cols = columns or len(stats)
    cols = st.columns(num_cols)

    for i, stat in enumerate(stats):
        with cols[i % num_cols]:
            st.metric(
                label=f"{stat.get('icon', '')} {stat.get('label', '')}".strip(),
                value=stat.get("value", "-"),
                delta=stat.get("delta"),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Cards
    "page_card",
    "metric_card",
    "info_card",
    "stat_card",

    # Filtres
    "filter_bar",
    "active_filters_display",
    "period_selector",

    # Sections
    "section_header",
    "collapsible_section",
    "tabs_section",

    # Alertes
    "alert",
    "toast",
    "feedback_message",

    # Empty states
    "empty_state",
    "no_data_state",
    "no_results_state",

    # Data display
    "data_table",
    "key_value_list",
    "export_button",

    # Progress
    "step_progress",
    "stats_row",
]
