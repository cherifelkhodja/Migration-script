"""
Design System - Composants Atomiques.

Ce module contient les composants de base (atomes) du Design System :
- Boutons (primary, secondary, ghost, danger)
- Badges (état, CMS, statut)
- Tags (info, success, warning, danger)
- Indicateurs (score, delta, loading)
- Labels et textes formatés

Usage:
    from src.presentation.streamlit.ui.atoms import (
        primary_button, state_badge, status_tag, score_indicator
    )

Principes:
    - Chaque atome est une fonction pure qui retourne du HTML ou utilise st.*
    - Tous les styles viennent de theme.py
    - Les atomes sont composables pour créer des molécules
"""

import streamlit as st
from typing import Literal, Optional, Callable, Any

from .theme import (
    COLORS, STATE_COLORS, CMS_COLORS, ICONS,
    TYPOGRAPHY, BORDERS, SPACING,
    get_state_color, get_cms_color, is_dark_mode
)


# ═══════════════════════════════════════════════════════════════════════════════
# BOUTONS
# ═══════════════════════════════════════════════════════════════════════════════

def primary_button(
    label: str,
    key: str,
    icon: str = None,
    disabled: bool = False,
    full_width: bool = True,
    on_click: Callable = None,
    args: tuple = None,
) -> bool:
    """
    Bouton d'action principale (CTA).

    Args:
        label: Texte du bouton
        key: Clé unique Streamlit
        icon: Emoji optionnel (ex: "🚀")
        disabled: Désactiver le bouton
        full_width: Prendre toute la largeur
        on_click: Callback optionnel
        args: Arguments pour le callback

    Returns:
        True si cliqué
    """
    display_label = f"{icon} {label}" if icon else label

    return st.button(
        display_label,
        key=key,
        type="primary",
        disabled=disabled,
        use_container_width=full_width,
        on_click=on_click,
        args=args or (),
    )


def secondary_button(
    label: str,
    key: str,
    icon: str = None,
    disabled: bool = False,
    full_width: bool = True,
    on_click: Callable = None,
    args: tuple = None,
) -> bool:
    """
    Bouton d'action secondaire.

    Args:
        label: Texte du bouton
        key: Clé unique Streamlit
        icon: Emoji optionnel
        disabled: Désactiver le bouton
        full_width: Prendre toute la largeur
        on_click: Callback optionnel
        args: Arguments pour le callback

    Returns:
        True si cliqué
    """
    display_label = f"{icon} {label}" if icon else label

    return st.button(
        display_label,
        key=key,
        type="secondary",
        disabled=disabled,
        use_container_width=full_width,
        on_click=on_click,
        args=args or (),
    )


def ghost_button(
    label: str,
    key: str,
    icon: str = None,
    disabled: bool = False,
    help_text: str = None,
) -> bool:
    """
    Bouton transparent/ghost pour actions tertiaires.

    Args:
        label: Texte du bouton
        key: Clé unique Streamlit
        icon: Emoji optionnel
        disabled: Désactiver le bouton
        help_text: Tooltip

    Returns:
        True si cliqué
    """
    display_label = f"{icon} {label}" if icon else label

    return st.button(
        display_label,
        key=key,
        type="secondary",
        disabled=disabled,
        help=help_text,
    )


def danger_button(
    label: str,
    key: str,
    icon: str = "🗑️",
    disabled: bool = False,
    confirm: bool = True,
) -> bool:
    """
    Bouton pour actions destructives (suppression, etc.).

    Args:
        label: Texte du bouton
        key: Clé unique Streamlit
        icon: Emoji (défaut: poubelle)
        disabled: Désactiver le bouton
        confirm: Demander confirmation (affiche un popover)

    Returns:
        True si cliqué (et confirmé si confirm=True)
    """
    display_label = f"{icon} {label}" if icon else label

    if confirm:
        with st.popover(display_label, disabled=disabled):
            st.warning("Cette action est irréversible.")
            if st.button("Confirmer la suppression", key=f"{key}_confirm", type="primary"):
                return True
        return False
    else:
        return st.button(
            display_label,
            key=key,
            type="secondary",
            disabled=disabled,
        )


def icon_button(
    icon: str,
    key: str,
    tooltip: str = None,
    disabled: bool = False,
) -> bool:
    """
    Bouton icône seul (actions rapides).

    Args:
        icon: Emoji du bouton
        key: Clé unique Streamlit
        tooltip: Texte d'aide au survol
        disabled: Désactiver le bouton

    Returns:
        True si cliqué
    """
    return st.button(
        icon,
        key=key,
        disabled=disabled,
        help=tooltip,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BADGES - ÉTATS
# ═══════════════════════════════════════════════════════════════════════════════

def state_badge(state: str, show_description: bool = False) -> str:
    """
    Badge HTML pour l'état d'une page (XXL, XL, L, M, S, XS, inactif).

    Args:
        state: État de la page
        show_description: Afficher la description (ex: "150+ ads")

    Returns:
        HTML du badge
    """
    state_data = STATE_COLORS.get(state, STATE_COLORS["inactif"])
    bg_color = state_data["bg"]
    text_color = state_data["text"]

    label = state
    if show_description:
        label = f"{state} ({state_data['description']})"

    return f'''<span style="
        background-color: {bg_color};
        color: {text_color};
        padding: 3px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
        line-height: 1.4;
    ">{label}</span>'''


def render_state_badge(state: str, show_description: bool = False):
    """Affiche un badge d'état dans Streamlit."""
    st.markdown(state_badge(state, show_description), unsafe_allow_html=True)


def state_indicator(state: str) -> str:
    """
    Indicateur d'état avec emoji pour les DataFrames.

    Args:
        state: État de la page

    Returns:
        String formaté avec emoji
    """
    indicators = {
        "XXL": "🟣 XXL",
        "XL": "🔵 XL",
        "L": "🔷 L",
        "M": "🟢 M",
        "S": "🟠 S",
        "XS": "🔴 XS",
        "inactif": "⚫ Inactif"
    }
    return indicators.get(state, state)


# ═══════════════════════════════════════════════════════════════════════════════
# BADGES - CMS
# ═══════════════════════════════════════════════════════════════════════════════

def cms_badge(cms: str, show_icon: bool = True) -> str:
    """
    Badge HTML pour le CMS d'un site.

    Args:
        cms: Nom du CMS
        show_icon: Afficher l'icône

    Returns:
        HTML du badge
    """
    cms_data = CMS_COLORS.get(cms, CMS_COLORS["Unknown"])
    bg_color = cms_data["bg"]
    text_color = cms_data["text"]
    icon = cms_data.get("icon", "")

    label = f"{icon} {cms}" if show_icon and icon else cms

    return f'''<span style="
        background-color: {bg_color};
        color: {text_color};
        padding: 2px 10px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 500;
        display: inline-block;
        line-height: 1.4;
    ">{label}</span>'''


def render_cms_badge(cms: str, show_icon: bool = True):
    """Affiche un badge CMS dans Streamlit."""
    st.markdown(cms_badge(cms, show_icon), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAGS - STATUTS
# ═══════════════════════════════════════════════════════════════════════════════

StatusVariant = Literal["success", "warning", "danger", "info", "neutral"]


def status_tag(
    label: str,
    variant: StatusVariant = "neutral",
    icon: str = None,
) -> str:
    """
    Tag de statut coloré.

    Args:
        label: Texte du tag
        variant: Variante de couleur (success, warning, danger, info, neutral)
        icon: Emoji optionnel

    Returns:
        HTML du tag
    """
    colors_map = {
        "success": {"bg": COLORS["success_light"], "text": COLORS["success"], "border": COLORS["success"]},
        "warning": {"bg": COLORS["warning_light"], "text": COLORS["warning_hover"], "border": COLORS["warning"]},
        "danger": {"bg": COLORS["danger_light"], "text": COLORS["danger"], "border": COLORS["danger"]},
        "info": {"bg": COLORS["info_light"], "text": COLORS["info_hover"], "border": COLORS["info"]},
        "neutral": {"bg": COLORS["neutral_100"], "text": COLORS["neutral_600"], "border": COLORS["neutral_300"]},
    }

    style = colors_map.get(variant, colors_map["neutral"])
    display_label = f"{icon} {label}" if icon else label

    return f'''<span style="
        background-color: {style["bg"]};
        color: {style["text"]};
        border: 1px solid {style["border"]};
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        display: inline-block;
        line-height: 1.4;
    ">{display_label}</span>'''


def render_status_tag(label: str, variant: StatusVariant = "neutral", icon: str = None):
    """Affiche un tag de statut dans Streamlit."""
    st.markdown(status_tag(label, variant, icon), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATEURS DE SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def score_badge(score: int, max_score: int = 100) -> str:
    """
    Badge de score avec grade (S, A, B, C, D).

    Args:
        score: Score actuel
        max_score: Score maximum

    Returns:
        HTML du badge avec grade
    """
    # Déterminer le grade
    percentage = (score / max_score) * 100 if max_score > 0 else 0

    if percentage >= 80:
        grade, color = "S", COLORS["success"]
    elif percentage >= 60:
        grade, color = "A", "#22C55E"  # Vert clair
    elif percentage >= 40:
        grade, color = "B", COLORS["warning"]
    elif percentage >= 20:
        grade, color = "C", "#F97316"  # Orange
    else:
        grade, color = "D", COLORS["danger"]

    return f'''<span style="
        background-color: {color};
        color: white;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        display: inline-block;
    ">{grade} {score}</span>'''


def render_score_badge(score: int, max_score: int = 100):
    """Affiche un badge de score dans Streamlit."""
    st.markdown(score_badge(score, max_score), unsafe_allow_html=True)


def get_score_grade(score: int, max_score: int = 100) -> tuple:
    """
    Calcule le grade d'un score.

    Returns:
        Tuple (grade, couleur)
    """
    percentage = (score / max_score) * 100 if max_score > 0 else 0

    if percentage >= 80:
        return "S", COLORS["success"]
    elif percentage >= 60:
        return "A", "#22C55E"
    elif percentage >= 40:
        return "B", COLORS["warning"]
    elif percentage >= 20:
        return "C", "#F97316"
    else:
        return "D", COLORS["danger"]


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATEURS DE DELTA / TENDANCE
# ═══════════════════════════════════════════════════════════════════════════════

def delta_indicator(
    value: int | float,
    suffix: str = "",
    inverse: bool = False,
) -> str:
    """
    Indicateur de variation (delta) avec couleur.

    Args:
        value: Valeur du delta
        suffix: Suffixe (ex: "%", " ads")
        inverse: Inverser les couleurs (vert pour négatif)

    Returns:
        HTML de l'indicateur
    """
    if value > 0:
        color = COLORS["danger"] if inverse else COLORS["success"]
        arrow = "↑"
        sign = "+"
    elif value < 0:
        color = COLORS["success"] if inverse else COLORS["danger"]
        arrow = "↓"
        sign = ""
    else:
        color = COLORS["neutral_500"]
        arrow = "→"
        sign = ""

    return f'''<span style="
        color: {color};
        font-size: 12px;
        font-weight: 500;
    ">{arrow} {sign}{value}{suffix}</span>'''


def render_delta_indicator(value: int | float, suffix: str = "", inverse: bool = False):
    """Affiche un indicateur de delta dans Streamlit."""
    st.markdown(delta_indicator(value, suffix, inverse), unsafe_allow_html=True)


def trend_icon(trend: Literal["up", "down", "stable"]) -> str:
    """
    Icône de tendance.

    Args:
        trend: Direction de la tendance

    Returns:
        Emoji de tendance
    """
    icons = {
        "up": "📈",
        "down": "📉",
        "stable": "➡️",
    }
    return icons.get(trend, "➡️")


# ═══════════════════════════════════════════════════════════════════════════════
# LOADING / ÉTATS
# ═══════════════════════════════════════════════════════════════════════════════

def loading_spinner(message: str = "Chargement..."):
    """
    Affiche un spinner de chargement.

    Args:
        message: Message à afficher
    """
    st.spinner(message)


def loading_indicator(message: str = "Chargement en cours..."):
    """
    Indicateur de chargement inline.

    Args:
        message: Message à afficher
    """
    st.markdown(f'''
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            color: {COLORS["neutral_500"]};
            font-size: 14px;
        ">
            <span style="animation: spin 1s linear infinite;">⏳</span>
            {message}
        </div>
        <style>
            @keyframes spin {{
                from {{ transform: rotate(0deg); }}
                to {{ transform: rotate(360deg); }}
            }}
        </style>
    ''', unsafe_allow_html=True)


def progress_indicator(current: int, total: int, label: str = ""):
    """
    Indicateur de progression numérique.

    Args:
        current: Valeur actuelle
        total: Valeur totale
        label: Label optionnel
    """
    percentage = (current / total * 100) if total > 0 else 0
    display_label = f"{label}: " if label else ""

    st.markdown(f'''
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: {COLORS["neutral_600"]};
        ">
            <span>{display_label}{current}/{total}</span>
            <span style="color: {COLORS["neutral_400"]};">({percentage:.0f}%)</span>
        </div>
    ''', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TEXTES FORMATÉS
# ═══════════════════════════════════════════════════════════════════════════════

def text_muted(text: str) -> str:
    """Texte grisé/atténué."""
    return f'<span style="color: {COLORS["neutral_500"]}; font-size: 14px;">{text}</span>'


def text_small(text: str) -> str:
    """Texte petit."""
    return f'<span style="font-size: 12px; color: {COLORS["neutral_600"]};">{text}</span>'


def text_bold(text: str) -> str:
    """Texte en gras."""
    return f'<strong style="font-weight: 600;">{text}</strong>'


def text_highlight(text: str, color: str = None) -> str:
    """Texte surligné."""
    bg_color = color or COLORS["primary_light"]
    return f'<span style="background-color: {bg_color}; padding: 2px 6px; border-radius: 4px;">{text}</span>'


def render_text(text: str, variant: Literal["muted", "small", "bold", "highlight"] = None):
    """Affiche du texte formaté dans Streamlit."""
    if variant == "muted":
        st.markdown(text_muted(text), unsafe_allow_html=True)
    elif variant == "small":
        st.markdown(text_small(text), unsafe_allow_html=True)
    elif variant == "bold":
        st.markdown(text_bold(text), unsafe_allow_html=True)
    elif variant == "highlight":
        st.markdown(text_highlight(text), unsafe_allow_html=True)
    else:
        st.markdown(text)


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATAGE DE NOMBRES
# ═══════════════════════════════════════════════════════════════════════════════

def format_number(value: int | float, locale: str = "fr") -> str:
    """
    Formate un nombre avec séparateurs de milliers.

    Args:
        value: Nombre à formater
        locale: Locale (fr = espace, en = virgule)

    Returns:
        String formaté
    """
    if value is None:
        return "-"

    separator = " " if locale == "fr" else ","
    return f"{value:,}".replace(",", separator)


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Formate un pourcentage.

    Args:
        value: Valeur (0-100 ou 0-1)
        decimals: Nombre de décimales

    Returns:
        String formaté avec %
    """
    if value is None:
        return "-"

    # Si la valeur est entre 0 et 1, convertir en pourcentage
    if 0 <= value <= 1:
        value = value * 100

    return f"{value:.{decimals}f}%"


def format_currency(value: float, currency: str = "EUR") -> str:
    """
    Formate une valeur monétaire.

    Args:
        value: Montant
        currency: Code devise

    Returns:
        String formaté
    """
    if value is None:
        return "-"

    symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
    }
    symbol = symbols.get(currency, currency)

    return f"{value:,.2f} {symbol}".replace(",", " ")


def format_time_elapsed(seconds: float) -> str:
    """
    Formate une durée en format lisible.

    Args:
        seconds: Durée en secondes

    Returns:
        String formaté (ex: "2m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Tronque un texte s'il dépasse la longueur max.

    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        suffix: Suffixe de troncature

    Returns:
        Texte tronqué ou original
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# ═══════════════════════════════════════════════════════════════════════════════
# LINKS
# ═══════════════════════════════════════════════════════════════════════════════

def external_link(url: str, label: str = None, icon: str = "🔗") -> str:
    """
    Lien externe avec icône.

    Args:
        url: URL du lien
        label: Texte du lien (défaut: URL tronquée)
        icon: Icône (défaut: 🔗)

    Returns:
        HTML du lien
    """
    display_label = label or truncate_text(url, 40)
    return f'''<a href="{url}" target="_blank" style="
        color: {COLORS["primary"]};
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    ">{icon} {display_label}</a>'''


def render_external_link(url: str, label: str = None, icon: str = "🔗"):
    """Affiche un lien externe dans Streamlit."""
    st.markdown(external_link(url, label, icon), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DIVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

def divider():
    """Ligne de séparation standard."""
    st.markdown("---")


def divider_with_text(text: str):
    """Ligne de séparation avec texte centré."""
    st.markdown(f'''
        <div style="
            display: flex;
            align-items: center;
            margin: 16px 0;
        ">
            <div style="flex: 1; height: 1px; background-color: {COLORS["neutral_200"]};"></div>
            <span style="
                padding: 0 16px;
                color: {COLORS["neutral_500"]};
                font-size: 12px;
                font-weight: 500;
            ">{text}</span>
            <div style="flex: 1; height: 1px; background-color: {COLORS["neutral_200"]};"></div>
        </div>
    ''', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Boutons
    "primary_button",
    "secondary_button",
    "ghost_button",
    "danger_button",
    "icon_button",

    # Badges états
    "state_badge",
    "render_state_badge",
    "state_indicator",

    # Badges CMS
    "cms_badge",
    "render_cms_badge",

    # Tags statuts
    "status_tag",
    "render_status_tag",
    "StatusVariant",

    # Scores
    "score_badge",
    "render_score_badge",
    "get_score_grade",

    # Deltas
    "delta_indicator",
    "render_delta_indicator",
    "trend_icon",

    # Loading
    "loading_spinner",
    "loading_indicator",
    "progress_indicator",

    # Textes
    "text_muted",
    "text_small",
    "text_bold",
    "text_highlight",
    "render_text",

    # Formatage
    "format_number",
    "format_percentage",
    "format_currency",
    "format_time_elapsed",
    "truncate_text",

    # Links
    "external_link",
    "render_external_link",

    # Dividers
    "divider",
    "divider_with_text",
]
