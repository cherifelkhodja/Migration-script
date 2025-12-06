"""
Composants de badges et styles pour le dashboard Streamlit.

Ce module contient les fonctions de création de badges,
couleurs et styles CSS pour le dashboard.
"""

import streamlit as st


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE COULEURS
# ═══════════════════════════════════════════════════════════════════════════════

# Couleurs pour les états
STATE_COLORS = {
    "XXL": {"bg": "#7c3aed", "text": "#fff"},  # Violet - Top performer
    "XL": {"bg": "#2563eb", "text": "#fff"},   # Bleu - Excellent
    "L": {"bg": "#0891b2", "text": "#fff"},    # Cyan - Très bien
    "M": {"bg": "#059669", "text": "#fff"},    # Vert - Bien
    "S": {"bg": "#d97706", "text": "#fff"},    # Orange - Moyen
    "XS": {"bg": "#dc2626", "text": "#fff"},   # Rouge - Faible
    "inactif": {"bg": "#6b7280", "text": "#fff"},  # Gris - Inactif
}

# Couleurs pour les CMS
CMS_COLORS = {
    "Shopify": {"bg": "#96bf48", "text": "#fff"},
    "WooCommerce": {"bg": "#7f54b3", "text": "#fff"},
    "PrestaShop": {"bg": "#df0067", "text": "#fff"},
    "Magento": {"bg": "#f46f25", "text": "#fff"},
    "Wix": {"bg": "#0c6efc", "text": "#fff"},
    "Squarespace": {"bg": "#000", "text": "#fff"},
    "BigCommerce": {"bg": "#121118", "text": "#fff"},
    "Webflow": {"bg": "#4353ff", "text": "#fff"},
    "Unknown": {"bg": "#9ca3af", "text": "#fff"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS DE BADGES
# ═══════════════════════════════════════════════════════════════════════════════

def get_state_badge(etat: str) -> str:
    """Retourne un badge HTML coloré pour l'état"""
    colors = STATE_COLORS.get(etat, {"bg": "#6b7280", "text": "#fff"})
    return f'<span style="background-color:{colors["bg"]};color:{colors["text"]};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">{etat}</span>'


def get_cms_badge(cms: str) -> str:
    """Retourne un badge HTML coloré pour le CMS"""
    colors = CMS_COLORS.get(cms, {"bg": "#9ca3af", "text": "#fff"})
    return f'<span style="background-color:{colors["bg"]};color:{colors["text"]};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;">{cms}</span>'


def format_state_for_df(etat: str) -> str:
    """Formate l'état avec un emoji indicateur pour les DataFrames"""
    indicators = {
        "XXL": "🟣 XXL",
        "XL": "🔵 XL",
        "L": "🔷 L",
        "M": "🟢 M",
        "S": "🟠 S",
        "XS": "🔴 XS",
        "inactif": "⚫ inactif"
    }
    return indicators.get(etat, etat)


# ═══════════════════════════════════════════════════════════════════════════════
# CSS PERSONNALISÉ
# ═══════════════════════════════════════════════════════════════════════════════

def apply_custom_css():
    """Applique les styles CSS personnalisés"""
    st.markdown("""
    <style>
        /* Badges dans les tableaux */
        .state-badge {
            padding: 2px 10px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 12px;
            display: inline-block;
        }

        /* Amélioration des cartes métriques */
        div[data-testid="stMetricValue"] {
            font-size: 1.8rem;
        }

        /* Hover effect sur les expandeurs */
        .streamlit-expanderHeader:hover {
            background-color: rgba(151, 166, 195, 0.1);
        }

        /* Style pour les boutons d'action rapide */
        .quick-action-btn {
            padding: 5px 15px;
            border-radius: 20px;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }

        /* Amélioration de la sidebar */
        section[data-testid="stSidebar"] > div {
            padding-top: 1rem;
        }

        /* Progress bar améliorée */
        .stProgress > div > div {
            background-color: #10b981;
        }

        /* Tooltips personnalisés */
        .tooltip {
            position: relative;
            display: inline-block;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            background-color: #1f2937;
            color: #fff;
            text-align: center;
            padding: 8px 12px;
            border-radius: 6px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
            white-space: nowrap;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
    </style>
    """, unsafe_allow_html=True)
