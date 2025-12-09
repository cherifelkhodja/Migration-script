"""
Design System - Organismes (Composants complexes).

Ce module contient les organismes du Design System :
- Navigation (sidebar structurée)
- Header global
- Footer
- Formulaires complexes

Usage:
    from src.presentation.streamlit.ui.organisms import (
        render_navigation, render_app_header
    )

Principes:
    - Les organismes combinent plusieurs molécules
    - Ils représentent des sections complètes de l'UI
    - Ils sont la couche la plus haute avant les pages
"""

import streamlit as st
from typing import Literal, Optional, List, Dict, Any, Callable

from .theme import (
    COLORS, ICONS, SPACING, TYPOGRAPHY,
    is_dark_mode, apply_theme
)
from .atoms import (
    primary_button, secondary_button, ghost_button,
    format_number, status_tag
)
from .molecules import alert


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DE LA NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

# Structure de navigation hiérarchique
NAVIGATION_CONFIG = {
    "sections": [
        {
            "id": "main",
            "label": "PRINCIPAL",
            "items": [
                {"id": "Dashboard", "label": "Accueil", "icon": "🏠"},
                {"id": "Search Ads", "label": "Recherche", "icon": "🔍"},
                {"id": "Historique", "label": "Historique", "icon": "📜"},
                {"id": "Background Searches", "label": "En cours", "icon": "⏳", "badge_key": "active_searches"},
            ]
        },
        {
            "id": "explore",
            "label": "EXPLORER",
            "items": [
                {"id": "Pages / Shops", "label": "Pages / Shops", "icon": "🏪"},
                {"id": "Winning Ads", "label": "Winning Ads", "icon": "🏆"},
                {"id": "Analytics", "label": "Analytics", "icon": "📊"},
            ]
        },
        {
            "id": "organize",
            "label": "ORGANISER",
            "items": [
                {"id": "Favoris", "label": "Favoris", "icon": "⭐"},
                {"id": "Collections", "label": "Collections", "icon": "📁"},
                {"id": "Tags", "label": "Tags", "icon": "🏷️"},
            ]
        },
        {
            "id": "monitor",
            "label": "SURVEILLER",
            "items": [
                {"id": "Monitoring", "label": "Monitoring", "icon": "📈"},
                {"id": "Watchlists", "label": "Watchlists", "icon": "📋"},
                {"id": "Alerts", "label": "Alertes", "icon": "🔔"},
                {"id": "Scheduled Scans", "label": "Scans programmés", "icon": "🕐"},
            ]
        },
        {
            "id": "analyze",
            "label": "ANALYSER",
            "items": [
                {"id": "Creative Analysis", "label": "Créatives", "icon": "🎨"},
            ]
        },
        {
            "id": "config",
            "label": "CONFIGURATION",
            "items": [
                {"id": "Settings", "label": "Paramètres", "icon": "⚙️"},
                {"id": "Blacklist", "label": "Blacklist", "icon": "🚫"},
            ]
        },
    ],
    "admin_items": [
        {"id": "Users", "label": "Utilisateurs", "icon": "👥", "admin_only": True},
    ],
    "footer_links": [
        {"label": "API Swagger", "url": "/docs", "icon": "📚"},
        {"label": "API ReDoc", "url": "/redoc", "icon": "📖"},
    ]
}


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR / NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

def render_navigation(
    current_page: str = "Dashboard",
    user: Dict = None,
    db=None,
    on_page_change: Callable = None,
    show_dark_mode: bool = True,
    show_db_status: bool = True,
    collapsed_sections: List[str] = None,
):
    """
    Affiche la navigation sidebar restructurée.

    Args:
        current_page: Page actuellement sélectionnée
        user: Utilisateur connecté {email, role, is_admin}
        db: DatabaseManager pour le statut
        on_page_change: Callback quand une page est sélectionnée
        show_dark_mode: Afficher le toggle dark mode
        show_db_status: Afficher le statut DB
        collapsed_sections: IDs des sections à replier

    Example:
        with st.sidebar:
            render_navigation(
                current_page=st.session_state.current_page,
                user=st.session_state.user,
                db=get_database(),
                on_page_change=lambda page: setattr(st.session_state, 'current_page', page)
            )
    """
    collapsed = collapsed_sections or []

    with st.sidebar:
        # Header avec logo et dark mode
        _render_sidebar_header(show_dark_mode)

        st.markdown("---")

        # Sections de navigation
        for section in NAVIGATION_CONFIG["sections"]:
            _render_nav_section(
                section=section,
                current_page=current_page,
                on_page_change=on_page_change,
                collapsed=section["id"] in collapsed,
            )

        # Items admin
        if user and user.get("is_admin"):
            st.markdown("---")
            st.markdown(f"<p style='font-size: 11px; color: {COLORS['neutral_400']}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 8px 16px 4px;'>ADMIN</p>", unsafe_allow_html=True)

            for item in NAVIGATION_CONFIG["admin_items"]:
                _render_nav_item(
                    item=item,
                    is_active=(current_page == item["id"]),
                    on_click=on_page_change,
                )

        # Footer links
        st.markdown("---")
        for link in NAVIGATION_CONFIG["footer_links"]:
            st.link_button(
                f"{link['icon']} {link['label']}",
                link["url"],
                use_container_width=True,
            )

        # Statut DB
        if show_db_status:
            st.markdown("---")
            _render_db_status(db)


def _render_sidebar_header(show_dark_mode: bool):
    """Affiche le header de la sidebar."""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("## 📊 Meta Ads")

    with col2:
        if show_dark_mode:
            dark_mode = st.toggle(
                "🌙",
                value=is_dark_mode(),
                key="dark_mode_toggle",
                help="Mode sombre"
            )
            if dark_mode != is_dark_mode():
                st.session_state.dark_mode = dark_mode
                st.rerun()


def _render_nav_section(
    section: Dict,
    current_page: str,
    on_page_change: Callable,
    collapsed: bool = False,
):
    """Affiche une section de navigation."""
    # Label de section
    st.markdown(
        f"<p style='font-size: 11px; color: {COLORS['neutral_400']}; font-weight: 600; "
        f"text-transform: uppercase; letter-spacing: 0.05em; padding: 12px 16px 4px;'>"
        f"{section['label']}</p>",
        unsafe_allow_html=True
    )

    # Items de la section
    for item in section["items"]:
        _render_nav_item(
            item=item,
            is_active=(current_page == item["id"]),
            on_click=on_page_change,
        )


def _render_nav_item(
    item: Dict,
    is_active: bool,
    on_click: Callable,
):
    """Affiche un item de navigation."""
    label = f"{item['icon']} {item['label']}"

    # Badge dynamique (ex: nombre de recherches en cours)
    if item.get("badge_key"):
        badge_value = _get_badge_value(item["badge_key"])
        if badge_value:
            label = f"{label} ({badge_value})"

    btn_type = "primary" if is_active else "secondary"

    if st.button(
        label,
        key=f"nav_{item['id']}",
        type=btn_type,
        use_container_width=True,
    ):
        if on_click:
            on_click(item["id"])
        else:
            st.session_state.current_page = item["id"]
        st.rerun()


def _get_badge_value(badge_key: str) -> Optional[int]:
    """Récupère la valeur d'un badge dynamique."""
    if badge_key == "active_searches":
        try:
            from src.infrastructure.workers.background_worker import get_worker
            worker = get_worker()
            active = worker.get_active_searches()
            return len(active) if active else None
        except Exception:
            return None
    return None


def _render_db_status(db):
    """Affiche le statut de la base de données."""
    if db:
        st.success("🟢 Base de données connectée", icon="✅")
    else:
        st.error("🔴 Base de données hors ligne", icon="❌")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR SIMPLE (Compatibilité)
# ═══════════════════════════════════════════════════════════════════════════════

def render_simple_sidebar(
    pages: List[Dict[str, str]],
    current_page: str,
    title: str = "📊 Meta Ads",
) -> str:
    """
    Sidebar simplifiée pour compatibilité.

    Args:
        pages: Liste de pages [{id, label, icon}]
        current_page: Page actuelle
        title: Titre de l'app

    Returns:
        ID de la page sélectionnée
    """
    with st.sidebar:
        st.markdown(f"## {title}")
        st.markdown("---")

        selected = current_page

        for page in pages:
            label = f"{page.get('icon', '')} {page['label']}"
            is_active = (current_page == page["id"])

            if st.button(
                label,
                key=f"simple_nav_{page['id']}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                selected = page["id"]

        return selected


# ═══════════════════════════════════════════════════════════════════════════════
# APP HEADER
# ═══════════════════════════════════════════════════════════════════════════════

def render_app_header(
    user: Dict = None,
    show_logout: bool = True,
    logout_callback: Callable = None,
    notifications: List[Dict] = None,
):
    """
    Header global de l'application (haut de page).

    Args:
        user: Utilisateur connecté {email, role}
        show_logout: Afficher le bouton déconnexion
        logout_callback: Callback de déconnexion
        notifications: Liste de notifications [{message, type}]
    """
    col1, col2, col3 = st.columns([1, 4, 1])

    with col1:
        pass  # Espace pour breadcrumb ou retour

    with col2:
        # Notifications
        if notifications:
            for notif in notifications[:3]:  # Max 3 notifications
                alert(
                    message=notif["message"],
                    variant=notif.get("type", "info"),
                )

    with col3:
        if user:
            with st.popover(f"👤 {user.get('email', 'User')[:20]}"):
                st.markdown(f"**{user.get('email', '')}**")
                st.caption(f"Rôle: {user.get('role', 'viewer').capitalize()}")

                if show_logout and logout_callback:
                    if st.button("🚪 Déconnexion", key="header_logout"):
                        logout_callback()


# ═══════════════════════════════════════════════════════════════════════════════
# FORMULAIRES COMPLEXES
# ═══════════════════════════════════════════════════════════════════════════════

def search_form(
    key_prefix: str = "search",
    show_keywords: bool = True,
    show_page_ids: bool = True,
    show_countries: bool = True,
    show_cms: bool = True,
    show_advanced: bool = True,
    on_submit: Callable = None,
    default_countries: List[str] = None,
    default_cms: List[str] = None,
) -> Optional[Dict]:
    """
    Formulaire de recherche complet.

    Args:
        key_prefix: Préfixe des clés
        show_keywords: Afficher le champ mots-clés
        show_page_ids: Afficher le champ Page IDs
        show_countries: Afficher le sélecteur de pays
        show_cms: Afficher le sélecteur CMS
        show_advanced: Afficher les options avancées
        on_submit: Callback à la soumission
        default_countries: Pays par défaut
        default_cms: CMS par défaut

    Returns:
        Dict avec les paramètres de recherche si soumis
    """
    from src.infrastructure.config import AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES

    result = {
        "keywords": [],
        "page_ids": [],
        "countries": default_countries or ["FR"],
        "languages": [],
        "cms": default_cms or ["Shopify"],
        "min_ads": 3,
        "preview_mode": False,
        "background_mode": False,
    }

    # Mode de recherche
    if show_keywords and show_page_ids:
        search_mode = st.radio(
            "Mode de recherche",
            ["🔤 Par mots-clés", "🆔 Par Page IDs"],
            horizontal=True,
            key=f"{key_prefix}_mode"
        )
        is_keyword_mode = (search_mode == "🔤 Par mots-clés")
    else:
        is_keyword_mode = show_keywords

    # Champs principaux
    col1, col2 = st.columns([2, 1])

    with col1:
        if is_keyword_mode:
            keywords_input = st.text_area(
                "Mots-clés (un par ligne)",
                placeholder="dropshipping\necommerce\nboutique en ligne",
                height=100,
                key=f"{key_prefix}_keywords",
                help="Entrez vos mots-clés de recherche, un par ligne"
            )
            result["keywords"] = [k.strip() for k in keywords_input.split("\n") if k.strip()]
        else:
            page_ids_input = st.text_area(
                "Page IDs (un par ligne)",
                placeholder="123456789\n987654321",
                height=100,
                key=f"{key_prefix}_page_ids",
                help="Entrez les Page IDs Facebook, un par ligne"
            )
            result["page_ids"] = [p.strip() for p in page_ids_input.split("\n") if p.strip()]

    with col2:
        if show_countries:
            result["countries"] = st.multiselect(
                "🌍 Pays",
                options=list(AVAILABLE_COUNTRIES.keys()),
                default=result["countries"],
                format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES.get(x, x)}",
                key=f"{key_prefix}_countries"
            )

        # Indicateur
        if is_keyword_mode and result["keywords"]:
            st.info(f"🔍 {len(result['keywords'])} mot(s)-clé(s)")
        elif not is_keyword_mode and result["page_ids"]:
            batch_count = (len(result["page_ids"]) + 9) // 10
            st.info(f"📊 {len(result['page_ids'])} IDs → {batch_count} requêtes")

    # Options avancées
    if show_advanced:
        with st.expander("⚙️ Options avancées", expanded=False):
            adv_col1, adv_col2, adv_col3 = st.columns(3)

            with adv_col1:
                result["languages"] = st.multiselect(
                    "🗣️ Langues",
                    options=list(AVAILABLE_LANGUAGES.keys()),
                    default=[],
                    format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES.get(x, x)}",
                    key=f"{key_prefix}_languages"
                )

            with adv_col2:
                result["min_ads"] = st.slider(
                    "📊 Min. ads",
                    min_value=1,
                    max_value=50,
                    value=3,
                    key=f"{key_prefix}_min_ads"
                )

            with adv_col3:
                if show_cms:
                    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Autre/Inconnu"]
                    result["cms"] = st.multiselect(
                        "🛒 CMS",
                        options=cms_options,
                        default=result["cms"],
                        key=f"{key_prefix}_cms"
                    )

    # Options de mode
    opt_col1, opt_col2 = st.columns(2)

    with opt_col1:
        result["background_mode"] = st.checkbox(
            "⏳ Lancer en arrière-plan",
            key=f"{key_prefix}_background",
            help="La recherche continue même si vous quittez la page"
        )

    with opt_col2:
        result["preview_mode"] = st.checkbox(
            "📋 Mode aperçu",
            key=f"{key_prefix}_preview",
            disabled=result["background_mode"],
            help="Voir les résultats avant de les enregistrer"
        )

    # Bouton de soumission
    if st.button(
        "🚀 Lancer la recherche",
        type="primary",
        use_container_width=True,
        key=f"{key_prefix}_submit"
    ):
        # Validation
        if is_keyword_mode and not result["keywords"]:
            st.error("❌ Au moins un mot-clé requis !")
            return None
        elif not is_keyword_mode and not result["page_ids"]:
            st.error("❌ Au moins un Page ID requis !")
            return None

        if on_submit:
            on_submit(result)

        return result

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TABLES AVANCÉES
# ═══════════════════════════════════════════════════════════════════════════════

def paginated_table(
    data: Any,
    page_size: int = 20,
    columns_config: Dict = None,
    key_prefix: str = "table",
) -> None:
    """
    Tableau paginé.

    Args:
        data: DataFrame ou liste de dicts
        page_size: Nombre de lignes par page
        columns_config: Configuration des colonnes
        key_prefix: Préfixe des clés
    """
    import pandas as pd

    if isinstance(data, list):
        df = pd.DataFrame(data) if data else pd.DataFrame()
    else:
        df = data if data is not None else pd.DataFrame()

    if len(df) == 0:
        st.info("Aucune donnée à afficher")
        return

    total_rows = len(df)
    total_pages = (total_rows + page_size - 1) // page_size

    # Sélecteur de page
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        current_page = st.number_input(
            f"Page (1-{total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1,
            key=f"{key_prefix}_page",
            label_visibility="collapsed"
        )

    # Calculer les indices
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    # Afficher le tableau
    st.caption(f"Affichage {start_idx + 1}-{end_idx} sur {total_rows}")

    st.dataframe(
        df.iloc[start_idx:end_idx],
        column_config=columns_config,
        hide_index=True,
        use_container_width=True,
    )


def sortable_table(
    data: Any,
    default_sort_column: str = None,
    default_sort_ascending: bool = False,
    columns_config: Dict = None,
    key_prefix: str = "sortable",
):
    """
    Tableau avec tri personnalisé.

    Args:
        data: DataFrame ou liste
        default_sort_column: Colonne de tri par défaut
        default_sort_ascending: Ordre ascendant par défaut
        columns_config: Configuration des colonnes
        key_prefix: Préfixe des clés
    """
    import pandas as pd

    if isinstance(data, list):
        df = pd.DataFrame(data) if data else pd.DataFrame()
    else:
        df = data if data is not None else pd.DataFrame()

    if len(df) == 0:
        st.info("Aucune donnée à afficher")
        return

    # Options de tri
    col1, col2 = st.columns([2, 1])

    with col1:
        sort_column = st.selectbox(
            "Trier par",
            options=list(df.columns),
            index=list(df.columns).index(default_sort_column) if default_sort_column in df.columns else 0,
            key=f"{key_prefix}_sort_col"
        )

    with col2:
        sort_order = st.radio(
            "Ordre",
            ["↓ Décroissant", "↑ Croissant"],
            horizontal=True,
            index=0 if not default_sort_ascending else 1,
            key=f"{key_prefix}_sort_order",
            label_visibility="collapsed"
        )

    # Appliquer le tri
    ascending = (sort_order == "↑ Croissant")
    df_sorted = df.sort_values(by=sort_column, ascending=ascending)

    st.dataframe(
        df_sorted,
        column_config=columns_config,
        hide_index=True,
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Navigation
    "NAVIGATION_CONFIG",
    "render_navigation",
    "render_simple_sidebar",

    # Header
    "render_app_header",

    # Forms
    "search_form",

    # Tables
    "paginated_table",
    "sortable_table",
]
