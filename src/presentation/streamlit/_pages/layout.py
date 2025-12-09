"""
Page Layout - Structure de l'application (Sidebar + Dashboard).

Ce module définit la structure principale de l'interface utilisant
le nouveau Design System :
1. render_sidebar() : Navigation latérale hiérarchisée
2. render_dashboard() : Page d'accueil avec KPIs et graphiques

Architecture:
    Utilise le Design System (src.presentation.streamlit.ui) pour
    garantir la cohérence visuelle dans toute l'application.

Sidebar (Navigation):
---------------------
Organisation en sections hiérarchiques :
- **PRINCIPAL** : Accueil, Recherche, Historique, En cours
- **EXPLORER** : Pages/Shops, Winning Ads, Analytics
- **ORGANISER** : Favoris, Collections, Tags
- **SURVEILLER** : Monitoring, Watchlists, Alertes, Scans
- **ANALYSER** : Créatives
- **CONFIGURATION** : Paramètres, Blacklist

Dashboard:
----------
Vue d'ensemble avec :
- **KPIs principaux** : Total pages, actives, XXL, Shopify, Winning (7j)
- **Tendances** : Delta vs semaine précédente
- **Alertes** : Générées automatiquement
- **Graphiques** : Répartition par état et par CMS
- **Top Performers** : Tableau des meilleures pages avec score
"""

import streamlit as st
import pandas as pd

# Design System imports
from src.presentation.streamlit.ui import (
    # Theme
    apply_theme, COLORS, STATE_COLORS, ICONS,

    # Atoms
    state_indicator, format_number,

    # Molecules
    info_card, section_header, filter_bar, active_filters_display,
    stats_row, empty_state, export_button, alert,

    # Layouts
    page_header, kpi_row, two_column_layout,

    # Organisms
    render_navigation,
)

# Composants graphiques existants (à migrer progressivement)
from src.presentation.streamlit.components import (
    CHART_COLORS, chart_header,
    create_horizontal_bar_chart, create_donut_chart, export_to_csv
)

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.database import (
    get_suivi_stats, get_suivi_stats_filtered,
    get_winning_ads_stats, get_winning_ads_count_by_page,
    get_dashboard_trends, search_pages
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def format_state_for_df(etat: str) -> str:
    """Formate l'état pour l'affichage avec indicateur."""
    return state_indicator(etat)


def calculate_page_score(page: dict, winning_count: int = 0) -> int:
    """
    Calcule un score de performance pour une page (0-100).

    Critères:
    - État de la page : XXL=50pts, XL=40pts, L=30pts, M=20pts, S=10pts, XS=5pts
    - Nombre d'ads : jusqu'à 30pts bonus (1pt par 10 ads)
    - Winning ads : jusqu'à 20pts bonus (5pts par winning)
    """
    score = 0
    ads = page.get("nombre_ads_active", 0) or 0
    etat = page.get("etat", "")

    etat_scores = {"XXL": 50, "XL": 40, "L": 30, "M": 20, "S": 10, "XS": 5}
    score += etat_scores.get(etat, 0)
    score += min(ads // 10, 30)
    score += min(winning_count * 5, 20)

    return min(score, 100)


def get_score_color(score: int) -> str:
    """Retourne le grade selon le score (S/A/B/C/D)."""
    if score >= 80:
        return "S"
    elif score >= 60:
        return "A"
    elif score >= 40:
        return "B"
    elif score >= 20:
        return "C"
    return "D"


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    """
    Affiche la sidebar avec navigation hiérarchisée.

    Utilise le nouveau Design System pour une navigation structurée
    et cohérente.
    """
    db = get_database()
    user = st.session_state.get("user")
    current_page = st.session_state.get("current_page", "Dashboard")

    def on_page_change(page_id: str):
        st.session_state.current_page = page_id

    render_navigation(
        current_page=current_page,
        user=user,
        db=db,
        on_page_change=on_page_change,
        show_dark_mode=True,
        show_db_status=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def render_dashboard():
    """
    Page Dashboard - Vue d'ensemble avec KPIs et graphiques.

    Affiche:
    - KPIs principaux avec tendances
    - Alertes automatiques
    - Graphiques de répartition
    - Top performers avec score
    """
    from src.presentation.streamlit._pages.monitoring import detect_trends, generate_alerts

    # Appliquer le thème
    apply_theme()

    # Header
    page_header(
        title="Dashboard",
        subtitle="Vue d'ensemble de vos données",
        icon=ICONS["home"],
        show_divider=True
    )

    db = get_database()
    if not db:
        alert("Base de données non connectée", variant="warning")
        return

    # Multi-tenancy
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # Section Filtres
    section_header("Filtres", icon="🔍")
    filters = filter_bar(
        db=db,
        key_prefix="dashboard",
        show_thematique=True,
        show_subcategory=True,
        show_pays=True,
        columns=3,
        user_id=user_id
    )
    active_filters_display(filters)

    st.markdown("---")

    try:
        # Récupérer les statistiques
        if any(filters.values()):
            stats = get_suivi_stats_filtered(
                db,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays"),
                user_id=user_id
            )
        else:
            stats = get_suivi_stats(db, user_id=user_id)

        winning_stats = get_winning_ads_stats(db, days=7, user_id=user_id)
        winning_by_page = get_winning_ads_count_by_page(db, days=30, user_id=user_id)
        trends = get_dashboard_trends(db, days=7, user_id=user_id)

        # Extraire les données
        total_pages = stats.get("total_pages", 0)
        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})
        actives = sum(v for k, v in etats.items() if k != "inactif")
        shopify_count = cms_stats.get("Shopify", 0)
        xxl_count = etats.get("XXL", 0)
        winning_total = winning_stats.get("total", 0)

        # Deltas
        pages_delta = trends.get("pages", {}).get("delta", 0)
        winning_delta = trends.get("winning_ads", {}).get("delta", 0)
        rising = trends.get("evolution", {}).get("rising", 0)
        falling = trends.get("evolution", {}).get("falling", 0)

        # KPIs principaux
        kpis = [
            {
                "label": "Total Pages",
                "value": format_number(total_pages),
                "delta": f"+{pages_delta} (7j)" if pages_delta > 0 else (f"{pages_delta} (7j)" if pages_delta < 0 else None),
                "icon": "📄"
            },
            {
                "label": "Actives",
                "value": format_number(actives),
                "delta": f"📈 {rising} montantes" if rising > 0 else None,
                "icon": "✅"
            },
            {
                "label": "XXL (>=150)",
                "value": format_number(xxl_count),
                "icon": "🚀"
            },
            {
                "label": "Shopify",
                "value": format_number(shopify_count),
                "icon": "🛒"
            },
            {
                "label": "Winning (7j)",
                "value": format_number(winning_total),
                "delta": f"+{winning_delta} vs sem." if winning_delta > 0 else (f"{winning_delta} vs sem." if winning_delta < 0 else None),
                "icon": "🏆"
            },
        ]
        kpi_row(kpis, columns=5)

        # Section Tendances (collapsible)
        if rising > 0 or falling > 0 or pages_delta != 0 or winning_delta != 0:
            with st.expander("📈 Tendances (7 derniers jours)", expanded=False):
                trend_stats = [
                    {
                        "label": "Nouvelles pages",
                        "value": trends.get("pages", {}).get("current", 0),
                        "delta": f"+{pages_delta}" if pages_delta > 0 else (str(pages_delta) if pages_delta < 0 else "stable")
                    },
                    {
                        "label": "Winning ads",
                        "value": trends.get("winning_ads", {}).get("current", 0),
                        "delta": f"+{winning_delta}" if winning_delta > 0 else (str(winning_delta) if winning_delta < 0 else "stable")
                    },
                    {
                        "label": "Recherches",
                        "value": trends.get("searches", {}).get("current", 0),
                        "delta": None
                    },
                    {
                        "label": "Balance évolution",
                        "value": f"📈 {rising} / 📉 {falling}",
                        "delta": f"+{rising - falling} net" if rising != falling else "équilibré"
                    },
                ]
                stats_row(trend_stats, columns=4)

        # Alertes
        alerts = generate_alerts(db, user_id=user_id)
        if alerts:
            st.markdown("---")
            section_header("Alertes", icon="🔔")
            alert_cols = st.columns(min(len(alerts), 4))
            for i, alert_data in enumerate(alerts[:4]):
                with alert_cols[i]:
                    variant = alert_data.get("type", "info")
                    if variant == "success":
                        st.success(f"{alert_data['icon']} **{alert_data['title']}**\n\n{alert_data['message']}")
                    elif variant == "warning":
                        st.warning(f"{alert_data['icon']} **{alert_data['title']}**\n\n{alert_data['message']}")
                    else:
                        st.info(f"{alert_data['icon']} **{alert_data['title']}**\n\n{alert_data['message']}")

        st.markdown("---")

        # Info card pour débutants
        info_card(
            title="Comment lire ces graphiques ?",
            content="""
            <b>États des pages</b> : Classement basé sur le nombre d'annonces actives.<br>
            • <b>XXL</b> (>=150 ads) = Pages très actives, probablement rentables<br>
            • <b>XL</b> (80-149) = Pages performantes<br>
            • <b>L</b> (35-79) = Bonne activité<br>
            • <b>M/S/XS</b> = Activité modérée à faible<br><br>
            <b>CMS</b> : La technologie utilisée par le site (Shopify est le plus courant en e-commerce).
            """,
            icon="📚",
            expanded=False
        )

        # Graphiques
        col1, col2 = two_column_layout(left_width=1, right_width=1)

        with col1:
            chart_header(
                "📊 Répartition par État",
                "Classement des pages selon leur nombre d'annonces actives",
                "XXL = >=150 ads, XL = 80-149, L = 35-79, M = 20-34, S = 10-19, XS = 1-9"
            )
            if etats:
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = [(k, etats.get(k, 0)) for k in ordre_etats if etats.get(k, 0) > 0]
                if etats_ordonne:
                    labels = [e[0] for e in etats_ordonne]
                    values = [e[1] for e in etats_ordonne]
                    fig = create_horizontal_bar_chart(
                        labels=labels,
                        values=values,
                        value_suffix=" pages",
                        height=280
                    )
                    st.plotly_chart(fig, key="dash_etats", use_container_width=True)
            else:
                empty_state("Aucune donnée disponible", icon="📊")

        with col2:
            chart_header(
                "🛒 Répartition par CMS",
                "Technologie e-commerce utilisée par les sites",
                "Shopify est la plateforme la plus populaire pour le dropshipping"
            )
            if cms_stats:
                sorted_cms = sorted(cms_stats.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_cms]
                values = [c[1] for c in sorted_cms]
                fig = create_donut_chart(
                    labels=labels,
                    values=values,
                    height=280
                )
                st.plotly_chart(fig, key="dash_cms", use_container_width=True)
            else:
                empty_state("Aucune donnée disponible", icon="🛒")

        # Top performers
        st.markdown("---")
        section_header(
            title="Top Performers",
            subtitle="Pages avec les meilleurs scores de performance",
            icon="🌟"
        )

        top_pages = search_pages(db, limit=15, user_id=user_id)
        if top_pages:
            # Calculer les scores
            for page in top_pages:
                winning_count = winning_by_page.get(page["page_id"], 0)
                page["score"] = calculate_page_score(page, winning_count)
                page["winning_count"] = winning_count
                page["score_display"] = f"{get_score_color(page['score'])} {page['score']}"

            # Trier par score
            top_pages = sorted(top_pages, key=lambda x: x["score"], reverse=True)[:10]

            # Formater états avec indicateurs
            for p in top_pages:
                p["etat_display"] = format_state_for_df(p.get("etat", ""))

            df = pd.DataFrame(top_pages)
            cols_to_show = ["page_name", "cms", "etat_display", "nombre_ads_active", "winning_count", "score_display"]
            col_names = ["Nom", "CMS", "État", "Ads", "🏆 Winning", "Score"]
            df_display = df[[c for c in cols_to_show if c in df.columns]]
            df_display.columns = col_names[:len(df_display.columns)]

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Export
            export_button(
                data=top_pages,
                filename="top_performers.csv",
                label="Exporter en CSV",
                icon="📥",
                key="export_top"
            )
        else:
            empty_state(
                title="Aucune page en base",
                description="Lancez une recherche pour commencer à collecter des données.",
                icon="🔍",
            )

        # Tendances détaillées
        st.markdown("---")
        col1, col2 = two_column_layout()

        with col1:
            section_header("En forte croissance (7j)", icon="📈")
            trend_data = detect_trends(db, days=7, user_id=user_id)
            if trend_data["rising"]:
                for t in trend_data["rising"][:5]:
                    st.write(f"🚀 **{t['nom_site']}** +{t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune tendance détectée")

        with col2:
            section_header("En déclin", icon="📉")
            if trend_data.get("falling"):
                for t in trend_data["falling"][:5]:
                    st.write(f"⚠️ **{t['nom_site']}** {t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune page en déclin")

    except Exception as e:
        st.error(f"Erreur lors du chargement du dashboard: {e}")
