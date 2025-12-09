"""
Design System - Tokens de design centralisés.

Ce module centralise tous les tokens de design (couleurs, espacements, typographies)
pour garantir une cohérence visuelle dans toute l'application.

Usage:
    from src.presentation.streamlit.ui.theme import COLORS, STATE_COLORS, apply_theme

Architecture:
    - COLORS: Palette de couleurs principales (primary, secondary, success, etc.)
    - STATE_COLORS: Couleurs des états de pages (XXL, XL, L, M, S, XS)
    - CMS_COLORS: Couleurs des plateformes e-commerce
    - SPACING: Système d'espacements cohérent
    - TYPOGRAPHY: Configuration des polices
    - apply_theme(): Applique le CSS global

Craft Standards:
    - Tous les composants UI doivent utiliser ces tokens
    - Ne jamais hardcoder de couleurs dans les composants
    - Utiliser les fonctions get_color() pour accéder aux couleurs
"""

import streamlit as st
from typing import Literal, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PALETTE DE COULEURS PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    # Actions principales
    "primary": "#3B82F6",        # Bleu - CTAs, liens, éléments interactifs
    "primary_hover": "#2563EB",  # Bleu foncé - Hover state
    "primary_light": "#DBEAFE",  # Bleu très clair - Background highlights

    # Actions secondaires
    "secondary": "#6B7280",      # Gris - Boutons secondaires
    "secondary_hover": "#4B5563",
    "secondary_light": "#F3F4F6",

    # États sémantiques
    "success": "#10B981",        # Vert - Succès, validation
    "success_hover": "#059669",
    "success_light": "#D1FAE5",

    "warning": "#F59E0B",        # Orange - Attention, alertes modérées
    "warning_hover": "#D97706",
    "warning_light": "#FEF3C7",

    "danger": "#EF4444",         # Rouge - Erreurs, actions destructives
    "danger_hover": "#DC2626",
    "danger_light": "#FEE2E2",

    "info": "#06B6D4",           # Cyan - Information, aide
    "info_hover": "#0891B2",
    "info_light": "#CFFAFE",

    # Neutres
    "neutral_50": "#F9FAFB",     # Background très clair
    "neutral_100": "#F3F4F6",    # Background clair
    "neutral_200": "#E5E7EB",    # Bordures légères
    "neutral_300": "#D1D5DB",    # Bordures
    "neutral_400": "#9CA3AF",    # Texte désactivé
    "neutral_500": "#6B7280",    # Texte secondaire
    "neutral_600": "#4B5563",    # Texte normal
    "neutral_700": "#374151",    # Texte foncé
    "neutral_800": "#1F2937",    # Titres
    "neutral_900": "#111827",    # Texte très foncé

    # Fond
    "background": "#FFFFFF",
    "background_secondary": "#F9FAFB",
    "surface": "#FFFFFF",
    "surface_elevated": "#FFFFFF",
}

# Mode sombre
COLORS_DARK = {
    "primary": "#60A5FA",
    "primary_hover": "#93C5FD",
    "primary_light": "#1E3A5F",

    "secondary": "#9CA3AF",
    "secondary_hover": "#D1D5DB",
    "secondary_light": "#374151",

    "success": "#34D399",
    "success_light": "#064E3B",

    "warning": "#FBBF24",
    "warning_light": "#78350F",

    "danger": "#F87171",
    "danger_light": "#7F1D1D",

    "info": "#22D3EE",
    "info_light": "#164E63",

    "neutral_50": "#1F2937",
    "neutral_100": "#374151",
    "neutral_200": "#4B5563",
    "neutral_300": "#6B7280",
    "neutral_400": "#9CA3AF",
    "neutral_500": "#D1D5DB",
    "neutral_600": "#E5E7EB",
    "neutral_700": "#F3F4F6",
    "neutral_800": "#F9FAFB",
    "neutral_900": "#FFFFFF",

    "background": "#111827",
    "background_secondary": "#1F2937",
    "surface": "#1F2937",
    "surface_elevated": "#374151",
}


# ═══════════════════════════════════════════════════════════════════════════════
# COULEURS DES ÉTATS (Pages Facebook)
# ═══════════════════════════════════════════════════════════════════════════════

STATE_COLORS = {
    "XXL": {
        "bg": "#7C3AED",      # Violet - Top performer (>=150 ads)
        "text": "#FFFFFF",
        "light": "#EDE9FE",
        "description": "150+ ads actives"
    },
    "XL": {
        "bg": "#2563EB",      # Bleu - Excellent (80-149 ads)
        "text": "#FFFFFF",
        "light": "#DBEAFE",
        "description": "80-149 ads actives"
    },
    "L": {
        "bg": "#0891B2",      # Cyan - Très bien (35-79 ads)
        "text": "#FFFFFF",
        "light": "#CFFAFE",
        "description": "35-79 ads actives"
    },
    "M": {
        "bg": "#059669",      # Vert - Bien (20-34 ads)
        "text": "#FFFFFF",
        "light": "#D1FAE5",
        "description": "20-34 ads actives"
    },
    "S": {
        "bg": "#D97706",      # Orange - Moyen (10-19 ads)
        "text": "#FFFFFF",
        "light": "#FEF3C7",
        "description": "10-19 ads actives"
    },
    "XS": {
        "bg": "#DC2626",      # Rouge - Faible (1-9 ads)
        "text": "#FFFFFF",
        "light": "#FEE2E2",
        "description": "1-9 ads actives"
    },
    "inactif": {
        "bg": "#6B7280",      # Gris - Inactif (0 ads)
        "text": "#FFFFFF",
        "light": "#F3F4F6",
        "description": "0 ads actives"
    },
}

# Ordre des états pour affichage cohérent
STATE_ORDER = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]


# ═══════════════════════════════════════════════════════════════════════════════
# COULEURS DES CMS
# ═══════════════════════════════════════════════════════════════════════════════

CMS_COLORS = {
    "Shopify": {
        "bg": "#96BF48",      # Vert Shopify
        "text": "#FFFFFF",
        "icon": "🛒"
    },
    "WooCommerce": {
        "bg": "#7F54B3",      # Violet WooCommerce
        "text": "#FFFFFF",
        "icon": "🔌"
    },
    "PrestaShop": {
        "bg": "#DF0067",      # Rose PrestaShop
        "text": "#FFFFFF",
        "icon": "🛍️"
    },
    "Magento": {
        "bg": "#F46F25",      # Orange Magento
        "text": "#FFFFFF",
        "icon": "🔶"
    },
    "Wix": {
        "bg": "#0C6EFC",      # Bleu Wix
        "text": "#FFFFFF",
        "icon": "✨"
    },
    "Squarespace": {
        "bg": "#000000",      # Noir Squarespace
        "text": "#FFFFFF",
        "icon": "◼️"
    },
    "BigCommerce": {
        "bg": "#121118",      # Noir BigCommerce
        "text": "#FFFFFF",
        "icon": "🏪"
    },
    "Webflow": {
        "bg": "#4353FF",      # Bleu Webflow
        "text": "#FFFFFF",
        "icon": "🌊"
    },
    "Unknown": {
        "bg": "#9CA3AF",      # Gris
        "text": "#FFFFFF",
        "icon": "❓"
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# COULEURS POUR GRAPHIQUES (Plotly)
# ═══════════════════════════════════════════════════════════════════════════════

CHART_COLORS = {
    # États (pour graphiques)
    "XXL": "#7C3AED",
    "XL": "#2563EB",
    "L": "#0891B2",
    "M": "#059669",
    "S": "#D97706",
    "XS": "#DC2626",
    "inactif": "#9CA3AF",

    # CMS (pour graphiques)
    "Shopify": "#96BF48",
    "WooCommerce": "#7F54B3",
    "PrestaShop": "#DF0067",
    "Magento": "#F46F25",
    "Wix": "#0C6EFC",
    "Squarespace": "#000000",
    "BigCommerce": "#121118",
    "Webflow": "#4353FF",
    "Unknown": "#9CA3AF",

    # Sémantiques
    "primary": "#3B82F6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#06B6D4",
    "neutral": "#6B7280",

    # Palette pour séries de données
    "series": [
        "#3B82F6",  # Bleu
        "#10B981",  # Vert
        "#F59E0B",  # Orange
        "#EF4444",  # Rouge
        "#8B5CF6",  # Violet
        "#EC4899",  # Rose
        "#06B6D4",  # Cyan
        "#84CC16",  # Lime
    ]
}

# Layout Plotly standard
CHART_LAYOUT = {
    "font": {
        "family": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "size": 12,
        "color": "#374151"
    },
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
    "hoverlabel": {
        "bgcolor": "white",
        "font_size": 13,
        "font_family": "Inter, sans-serif",
        "bordercolor": "#E5E7EB"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# ESPACEMENTS
# ═══════════════════════════════════════════════════════════════════════════════

SPACING = {
    "none": "0",
    "xs": "0.25rem",    # 4px
    "sm": "0.5rem",     # 8px
    "md": "1rem",       # 16px
    "lg": "1.5rem",     # 24px
    "xl": "2rem",       # 32px
    "2xl": "3rem",      # 48px
    "3xl": "4rem",      # 64px
}

# Padding pour les containers
CONTAINER_PADDING = {
    "card": "1rem",
    "section": "1.5rem",
    "page": "2rem",
}


# ═══════════════════════════════════════════════════════════════════════════════
# TYPOGRAPHIE
# ═══════════════════════════════════════════════════════════════════════════════

TYPOGRAPHY = {
    "font_family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "font_family_mono": "'SF Mono', 'Fira Code', Consolas, monospace",

    # Tailles
    "text_xs": "0.75rem",     # 12px
    "text_sm": "0.875rem",    # 14px
    "text_base": "1rem",      # 16px
    "text_lg": "1.125rem",    # 18px
    "text_xl": "1.25rem",     # 20px
    "text_2xl": "1.5rem",     # 24px
    "text_3xl": "1.875rem",   # 30px
    "text_4xl": "2.25rem",    # 36px

    # Line heights
    "leading_tight": "1.25",
    "leading_normal": "1.5",
    "leading_relaxed": "1.75",

    # Font weights
    "font_normal": "400",
    "font_medium": "500",
    "font_semibold": "600",
    "font_bold": "700",
}


# ═══════════════════════════════════════════════════════════════════════════════
# BORDURES ET OMBRES
# ═══════════════════════════════════════════════════════════════════════════════

BORDERS = {
    "radius_sm": "0.25rem",   # 4px
    "radius_md": "0.375rem",  # 6px
    "radius_lg": "0.5rem",    # 8px
    "radius_xl": "0.75rem",   # 12px
    "radius_full": "9999px",  # Pills

    "width_thin": "1px",
    "width_medium": "2px",

    "color": "#E5E7EB",
    "color_focus": "#3B82F6",
}

SHADOWS = {
    "sm": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    "md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    "lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
    "xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
}


# ═══════════════════════════════════════════════════════════════════════════════
# ICÔNES (Emojis standardisés)
# ═══════════════════════════════════════════════════════════════════════════════

ICONS = {
    # Navigation
    "home": "🏠",
    "search": "🔍",
    "history": "📜",
    "loading": "⏳",
    "pages": "🏪",
    "watchlist": "📋",
    "alerts": "🔔",
    "favorites": "⭐",
    "collections": "📁",
    "tags": "🏷️",
    "monitoring": "📈",
    "analytics": "📊",
    "winning": "🏆",
    "creative": "🎨",
    "schedule": "🕐",
    "blacklist": "🚫",
    "settings": "⚙️",
    "users": "👥",

    # Actions
    "add": "➕",
    "edit": "✏️",
    "delete": "🗑️",
    "save": "💾",
    "export": "📥",
    "refresh": "🔄",
    "filter": "🎛️",
    "sort": "↕️",
    "expand": "📂",
    "collapse": "📁",
    "link": "🔗",
    "copy": "📋",

    # États
    "success": "✅",
    "warning": "⚠️",
    "error": "❌",
    "info": "ℹ️",
    "question": "❓",
    "loading_spinner": "⏳",

    # Données
    "globe": "🌍",
    "money": "💰",
    "chart": "📊",
    "trend_up": "📈",
    "trend_down": "📉",
    "rocket": "🚀",
    "target": "🎯",
    "fire": "🔥",
    "star": "⭐",
    "crown": "👑",

    # CMS
    "shopify": "🛒",
    "store": "🏪",
    "cart": "🛍️",

    # Divers
    "calendar": "📅",
    "clock": "🕐",
    "lock": "🔒",
    "key": "🔑",
    "database": "🗄️",
    "api": "🔌",
    "moon": "🌙",
    "sun": "☀️",
}


# ═══════════════════════════════════════════════════════════════════════════════
# NOMS DE PAYS (Standardisés)
# ═══════════════════════════════════════════════════════════════════════════════

COUNTRY_NAMES = {
    "FR": {"name": "France", "flag": "🇫🇷", "display": "🇫🇷 France"},
    "DE": {"name": "Allemagne", "flag": "🇩🇪", "display": "🇩🇪 Allemagne"},
    "ES": {"name": "Espagne", "flag": "🇪🇸", "display": "🇪🇸 Espagne"},
    "IT": {"name": "Italie", "flag": "🇮🇹", "display": "🇮🇹 Italie"},
    "GB": {"name": "Royaume-Uni", "flag": "🇬🇧", "display": "🇬🇧 Royaume-Uni"},
    "US": {"name": "États-Unis", "flag": "🇺🇸", "display": "🇺🇸 États-Unis"},
    "BE": {"name": "Belgique", "flag": "🇧🇪", "display": "🇧🇪 Belgique"},
    "CH": {"name": "Suisse", "flag": "🇨🇭", "display": "🇨🇭 Suisse"},
    "NL": {"name": "Pays-Bas", "flag": "🇳🇱", "display": "🇳🇱 Pays-Bas"},
    "PT": {"name": "Portugal", "flag": "🇵🇹", "display": "🇵🇹 Portugal"},
    "AT": {"name": "Autriche", "flag": "🇦🇹", "display": "🇦🇹 Autriche"},
    "CA": {"name": "Canada", "flag": "🇨🇦", "display": "🇨🇦 Canada"},
    "AU": {"name": "Australie", "flag": "🇦🇺", "display": "🇦🇺 Australie"},
    "LU": {"name": "Luxembourg", "flag": "🇱🇺", "display": "🇱🇺 Luxembourg"},
    "PL": {"name": "Pologne", "flag": "🇵🇱", "display": "🇵🇱 Pologne"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def get_color(name: str, dark_mode: bool = False) -> str:
    """Récupère une couleur du thème."""
    palette = COLORS_DARK if dark_mode else COLORS
    return palette.get(name, COLORS.get(name, "#000000"))


def get_state_color(state: str, property: str = "bg") -> str:
    """Récupère la couleur d'un état."""
    state_data = STATE_COLORS.get(state, STATE_COLORS["inactif"])
    return state_data.get(property, state_data["bg"])


def get_cms_color(cms: str, property: str = "bg") -> str:
    """Récupère la couleur d'un CMS."""
    cms_data = CMS_COLORS.get(cms, CMS_COLORS["Unknown"])
    return cms_data.get(property, cms_data["bg"])


def get_country_display(code: str) -> str:
    """Récupère l'affichage d'un pays."""
    country = COUNTRY_NAMES.get(code.upper(), {})
    return country.get("display", code)


def is_dark_mode() -> bool:
    """Vérifie si le mode sombre est activé."""
    return st.session_state.get("dark_mode", False)


# ═══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

def get_base_css(dark_mode: bool = False) -> str:
    """Génère le CSS de base du Design System."""
    colors = COLORS_DARK if dark_mode else COLORS

    return f"""
    <style>
        /* ═══ RESET & BASE ═══ */
        .stApp {{
            font-family: {TYPOGRAPHY["font_family"]};
        }}

        /* ═══ SIDEBAR ═══ */
        section[data-testid="stSidebar"] {{
            background-color: {colors["background_secondary"]};
            border-right: 1px solid {colors["neutral_200"]};
        }}

        section[data-testid="stSidebar"] > div {{
            padding-top: {SPACING["md"]};
        }}

        /* ═══ BOUTONS ═══ */
        .stButton > button {{
            border-radius: {BORDERS["radius_lg"]};
            font-weight: {TYPOGRAPHY["font_medium"]};
            transition: all 0.2s ease;
        }}

        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: {SHADOWS["md"]};
        }}

        .stButton > button[kind="primary"] {{
            background-color: {colors["primary"]};
            border-color: {colors["primary"]};
        }}

        .stButton > button[kind="primary"]:hover {{
            background-color: {colors["primary_hover"]};
        }}

        /* ═══ INPUTS ═══ */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div {{
            border-radius: {BORDERS["radius_md"]};
            border-color: {colors["neutral_300"]};
        }}

        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {{
            border-color: {colors["primary"]};
            box-shadow: 0 0 0 3px {colors["primary_light"]};
        }}

        /* ═══ MÉTRIQUES ═══ */
        div[data-testid="stMetricValue"] {{
            font-size: 1.75rem;
            font-weight: {TYPOGRAPHY["font_bold"]};
            color: {colors["neutral_800"]};
        }}

        div[data-testid="stMetricLabel"] {{
            font-size: {TYPOGRAPHY["text_sm"]};
            color: {colors["neutral_500"]};
            font-weight: {TYPOGRAPHY["font_medium"]};
        }}

        /* ═══ EXPANDERS ═══ */
        .streamlit-expanderHeader {{
            font-weight: {TYPOGRAPHY["font_semibold"]};
            border-radius: {BORDERS["radius_md"]};
        }}

        .streamlit-expanderHeader:hover {{
            background-color: {colors["neutral_100"]};
        }}

        /* ═══ TABS ═══ */
        .stTabs [data-baseweb="tab-list"] {{
            gap: {SPACING["sm"]};
            background-color: transparent;
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: {BORDERS["radius_md"]};
            padding: {SPACING["sm"]} {SPACING["md"]};
            font-weight: {TYPOGRAPHY["font_medium"]};
        }}

        .stTabs [aria-selected="true"] {{
            background-color: {colors["primary"]};
            color: white;
        }}

        /* ═══ DATAFRAMES ═══ */
        .stDataFrame {{
            border-radius: {BORDERS["radius_lg"]};
            overflow: hidden;
        }}

        /* ═══ PROGRESS BAR ═══ */
        .stProgress > div > div {{
            background-color: {colors["primary"]};
            border-radius: {BORDERS["radius_full"]};
        }}

        /* ═══ ALERTS ═══ */
        .stAlert {{
            border-radius: {BORDERS["radius_lg"]};
            border-left-width: 4px;
        }}

        /* ═══ BADGES ═══ */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 10px;
            border-radius: {BORDERS["radius_full"]};
            font-size: {TYPOGRAPHY["text_xs"]};
            font-weight: {TYPOGRAPHY["font_semibold"]};
            line-height: 1.5;
        }}

        .badge-state {{
            padding: 3px 12px;
        }}

        .badge-cms {{
            padding: 2px 10px;
        }}

        /* ═══ CARDS ═══ */
        .card {{
            background-color: {colors["surface"]};
            border: 1px solid {colors["neutral_200"]};
            border-radius: {BORDERS["radius_xl"]};
            padding: {CONTAINER_PADDING["card"]};
            box-shadow: {SHADOWS["sm"]};
        }}

        .card:hover {{
            box-shadow: {SHADOWS["md"]};
            border-color: {colors["neutral_300"]};
        }}

        /* ═══ SECTION HEADERS ═══ */
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: {SPACING["md"]};
            margin-bottom: {SPACING["md"]};
            border-bottom: 1px solid {colors["neutral_200"]};
        }}

        .section-title {{
            font-size: {TYPOGRAPHY["text_xl"]};
            font-weight: {TYPOGRAPHY["font_semibold"]};
            color: {colors["neutral_800"]};
            margin: 0;
        }}

        .section-subtitle {{
            font-size: {TYPOGRAPHY["text_sm"]};
            color: {colors["neutral_500"]};
            margin-top: {SPACING["xs"]};
        }}

        /* ═══ EMPTY STATES ═══ */
        .empty-state {{
            text-align: center;
            padding: {SPACING["2xl"]} {SPACING["xl"]};
            color: {colors["neutral_500"]};
        }}

        .empty-state-icon {{
            font-size: 3rem;
            margin-bottom: {SPACING["md"]};
            opacity: 0.5;
        }}

        .empty-state-title {{
            font-size: {TYPOGRAPHY["text_lg"]};
            font-weight: {TYPOGRAPHY["font_semibold"]};
            color: {colors["neutral_700"]};
            margin-bottom: {SPACING["sm"]};
        }}

        .empty-state-description {{
            font-size: {TYPOGRAPHY["text_sm"]};
            color: {colors["neutral_500"]};
        }}

        /* ═══ NAVIGATION LINKS ═══ */
        .nav-item {{
            display: flex;
            align-items: center;
            padding: {SPACING["sm"]} {SPACING["md"]};
            border-radius: {BORDERS["radius_md"]};
            color: {colors["neutral_600"]};
            text-decoration: none;
            transition: all 0.15s ease;
            cursor: pointer;
        }}

        .nav-item:hover {{
            background-color: {colors["neutral_100"]};
            color: {colors["neutral_800"]};
        }}

        .nav-item.active {{
            background-color: {colors["primary_light"]};
            color: {colors["primary"]};
            font-weight: {TYPOGRAPHY["font_semibold"]};
        }}

        .nav-section-title {{
            font-size: {TYPOGRAPHY["text_xs"]};
            font-weight: {TYPOGRAPHY["font_semibold"]};
            color: {colors["neutral_400"]};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: {SPACING["md"]} {SPACING["md"]} {SPACING["sm"]};
        }}

        /* ═══ TOOLTIPS ═══ */
        .tooltip {{
            position: relative;
            display: inline-block;
        }}

        .tooltip .tooltip-text {{
            visibility: hidden;
            background-color: {colors["neutral_800"]};
            color: white;
            text-align: center;
            padding: {SPACING["sm"]} {SPACING["md"]};
            border-radius: {BORDERS["radius_md"]};
            position: absolute;
            z-index: 1000;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.2s;
            font-size: {TYPOGRAPHY["text_xs"]};
            white-space: nowrap;
            box-shadow: {SHADOWS["lg"]};
        }}

        .tooltip:hover .tooltip-text {{
            visibility: visible;
            opacity: 1;
        }}

        /* ═══ SCROLLBAR ═══ */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: {colors["neutral_100"]};
            border-radius: {BORDERS["radius_full"]};
        }}

        ::-webkit-scrollbar-thumb {{
            background: {colors["neutral_300"]};
            border-radius: {BORDERS["radius_full"]};
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: {colors["neutral_400"]};
        }}
    </style>
    """


def apply_theme():
    """Applique le thème complet (CSS global)."""
    dark_mode = is_dark_mode()
    st.markdown(get_base_css(dark_mode), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Palettes
    "COLORS",
    "COLORS_DARK",
    "STATE_COLORS",
    "STATE_ORDER",
    "CMS_COLORS",
    "CHART_COLORS",
    "CHART_LAYOUT",

    # Design tokens
    "SPACING",
    "CONTAINER_PADDING",
    "TYPOGRAPHY",
    "BORDERS",
    "SHADOWS",
    "ICONS",
    "COUNTRY_NAMES",

    # Fonctions
    "get_color",
    "get_state_color",
    "get_cms_color",
    "get_country_display",
    "is_dark_mode",
    "apply_theme",
    "get_base_css",
]
