"""
Page Layout - Structure de l'application (Sidebar + Dashboard).

Ce module definit la structure principale de l'interface :
1. render_sidebar() : Navigation laterale avec toutes les pages
2. render_dashboard() : Page d'accueil avec KPIs et graphiques

Sidebar (Navigation):
---------------------
Organisation en sections :
- **Main** : Dashboard, Search Ads, Historique, Recherches en cours,
  Pages/Shops, Watchlists, Alerts
- **Organisation** : Favoris, Collections, Tags
- **Analyse** : Monitoring, Analytics, Winning Ads, Creative Analysis
- **Automation** : Scans Programmes
- **Config** : Blacklist, Settings

Inclut :
- Toggle dark mode
- Indicateur de recherches en cours (avec compteur)
- Statut de la base de donnees

Dashboard:
----------
Vue d'ensemble avec :
- **KPIs principaux** : Total pages, actives, XXL, Shopify, Winning (7j)
- **Tendances** : Delta vs semaine precedente, pages montantes/descendantes
- **Alertes** : Generes automatiquement par le systeme de monitoring
- **Graphiques** : Repartition par etat et par CMS
- **Top Performers** : Tableau des meilleures pages avec score

Systeme de Score:
-----------------
Calcul du score de performance (0-100) :
- Etat de la page (XXL=50pts, XL=40pts, etc.)
- Nombre d'ads (jusqu'a 30pts bonus)
- Winning ads (jusqu'a 20pts bonus)

Grades : S (>=80), A (>=60), B (>=40), C (>=20), D (<20)

Filtres de classification:
--------------------------
Le dashboard supporte les filtres :
- Thematique (categorie Gemini)
- Sous-categorie
- Pays
"""
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import (
    CHART_COLORS, info_card, chart_header,
    create_horizontal_bar_chart, create_donut_chart, export_to_csv
)
from src.infrastructure.persistence.database import (
    get_suivi_stats, get_suivi_stats_filtered,
    get_winning_ads_stats, get_winning_ads_count_by_page,
    get_dashboard_trends, search_pages
)


def format_state_for_df(etat: str) -> str:
    """Formate l'etat pour l'affichage."""
    state_colors = {
        "XXL": "XXL (150+)",
        "XL": "XL (80-149)",
        "L": "L (35-79)",
        "M": "M (20-34)",
        "S": "S (10-19)",
        "XS": "XS (1-9)",
        "inactif": "Inactif"
    }
    return state_colors.get(etat, etat)


def calculate_page_score(page: dict, winning_count: int = 0) -> int:
    """Calcule un score pour une page."""
    score = 0
    ads = page.get("nombre_ads_active", 0) or 0
    etat = page.get("etat", "")

    etat_scores = {"XXL": 50, "XL": 40, "L": 30, "M": 20, "S": 10, "XS": 5}
    score += etat_scores.get(etat, 0)
    score += min(ads // 10, 30)
    score += min(winning_count * 5, 20)

    return score


def get_score_color(score: int) -> str:
    """Retourne un emoji couleur selon le score."""
    if score >= 80:
        return "S"
    elif score >= 60:
        return "A"
    elif score >= 40:
        return "B"
    elif score >= 20:
        return "C"
    return "D"


def render_sidebar():
    """Affiche la sidebar avec navigation"""
    with st.sidebar:
        # Header avec dark mode toggle
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("## Meta Ads")
        with col2:
            dark_mode = st.toggle("🌙", value=st.session_state.get('dark_mode', False), key="dark_toggle", help="Mode sombre")
            if dark_mode != st.session_state.get('dark_mode', False):
                st.session_state.dark_mode = dark_mode
                st.rerun()

        st.markdown("---")

        # Main Navigation
        st.markdown("### Main")

        if st.button("Dashboard", width="stretch",
                     type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
            st.session_state.current_page = "Dashboard"
            st.rerun()

        if st.button("Search Ads", width="stretch",
                     type="primary" if st.session_state.current_page == "Search Ads" else "secondary"):
            st.session_state.current_page = "Search Ads"
            st.rerun()

        if st.button("Historique", width="stretch",
                     type="primary" if st.session_state.current_page == "Historique" else "secondary"):
            st.session_state.current_page = "Historique"
            st.rerun()

        # Indicateur de recherches en arriere-plan
        try:
            from src.infrastructure.workers.background_worker import get_worker
            worker = get_worker()
            active = worker.get_active_searches()
            count = len(active) if active else 0
            btn_label = f"Recherches en cours ({count})"
            btn_type = "primary" if st.session_state.current_page == "Background Searches" else "secondary"

            if st.button(btn_label, width="stretch", type=btn_type):
                st.session_state.current_page = "Background Searches"
                st.rerun()
        except Exception:
            pass

        if st.button("Pages / Shops", width="stretch",
                     type="primary" if st.session_state.current_page == "Pages / Shops" else "secondary"):
            st.session_state.current_page = "Pages / Shops"
            st.rerun()

        if st.button("Watchlists", width="stretch",
                     type="primary" if st.session_state.current_page == "Watchlists" else "secondary"):
            st.session_state.current_page = "Watchlists"
            st.rerun()

        if st.button("Alerts", width="stretch",
                     type="primary" if st.session_state.current_page == "Alerts" else "secondary"):
            st.session_state.current_page = "Alerts"
            st.rerun()

        st.markdown("---")
        st.markdown("### Organisation")

        if st.button("Favoris", width="stretch",
                     type="primary" if st.session_state.current_page == "Favoris" else "secondary"):
            st.session_state.current_page = "Favoris"
            st.rerun()

        if st.button("Collections", width="stretch",
                     type="primary" if st.session_state.current_page == "Collections" else "secondary"):
            st.session_state.current_page = "Collections"
            st.rerun()

        if st.button("Tags", width="stretch",
                     type="primary" if st.session_state.current_page == "Tags" else "secondary"):
            st.session_state.current_page = "Tags"
            st.rerun()

        st.markdown("---")
        st.markdown("### Analyse")

        if st.button("Monitoring", width="stretch",
                     type="primary" if st.session_state.current_page == "Monitoring" else "secondary"):
            st.session_state.current_page = "Monitoring"
            st.rerun()

        if st.button("Analytics", width="stretch",
                     type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
            st.session_state.current_page = "Analytics"
            st.rerun()

        if st.button("Winning Ads", width="stretch",
                     type="primary" if st.session_state.current_page == "Winning Ads" else "secondary"):
            st.session_state.current_page = "Winning Ads"
            st.rerun()

        if st.button("Creative Analysis", width="stretch",
                     type="primary" if st.session_state.current_page == "Creative Analysis" else "secondary"):
            st.session_state.current_page = "Creative Analysis"
            st.rerun()

        st.markdown("---")
        st.markdown("### Automation")

        if st.button("Scans Programmes", width="stretch",
                     type="primary" if st.session_state.current_page == "Scheduled Scans" else "secondary"):
            st.session_state.current_page = "Scheduled Scans"
            st.rerun()

        st.markdown("---")
        st.markdown("### Config")

        if st.button("Blacklist", width="stretch",
                     type="primary" if st.session_state.current_page == "Blacklist" else "secondary"):
            st.session_state.current_page = "Blacklist"
            st.rerun()

        if st.button("Settings", width="stretch",
                     type="primary" if st.session_state.current_page == "Settings" else "secondary"):
            st.session_state.current_page = "Settings"
            st.rerun()

        # Liens vers la documentation
        st.markdown("---")
        st.markdown("### Documentation")
        st.link_button("📚 API Swagger", "/docs", use_container_width=True)
        st.link_button("📖 API ReDoc", "/redoc", use_container_width=True)

        # Page Users (admin only)
        user = st.session_state.get("user")
        if user and user.get("is_admin"):
            if st.button("👥 Users", width="stretch",
                         type="primary" if st.session_state.current_page == "Users" else "secondary"):
                st.session_state.current_page = "Users"
                st.rerun()

        # Database status
        st.markdown("---")
        db = get_database()
        if db:
            st.success("DB OK")
        else:
            st.error("DB offline")


def render_dashboard():
    """Page Dashboard - Vue d'ensemble"""
    from src.presentation.streamlit.dashboard import render_classification_filters
    from src.presentation.streamlit._pages.monitoring import detect_trends, generate_alerts

    st.title("🏠 Dashboard")
    st.markdown("Vue d'ensemble de vos données")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Filtres de classification
    st.markdown("#### 🔍 Filtres")
    filters = render_classification_filters(db, key_prefix="dashboard", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"🏷️ {filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"📂 {filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"🌍 {filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' - '.join(active_filters)}")

    st.markdown("---")

    try:
        # Utiliser les stats filtrees si des filtres sont actifs
        if any(filters.values()):
            stats = get_suivi_stats_filtered(
                db,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays")
            )
        else:
            stats = get_suivi_stats(db)

        winning_stats = get_winning_ads_stats(db, days=7)
        winning_by_page = get_winning_ads_count_by_page(db, days=30)

        # Recuperer les tendances (7 jours vs 7 jours precedents)
        trends = get_dashboard_trends(db, days=7)

        # KPIs principaux avec trends
        col1, col2, col3, col4, col5 = st.columns(5)

        total_pages = stats.get("total_pages", 0)
        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})

        actives = sum(v for k, v in etats.items() if k != "inactif")
        shopify_count = cms_stats.get("Shopify", 0)
        xxl_count = etats.get("XXL", 0)
        winning_total = winning_stats.get("total", 0)

        # Formater les deltas pour affichage
        pages_delta = trends.get("pages", {}).get("delta", 0)
        winning_delta = trends.get("winning_ads", {}).get("delta", 0)
        rising = trends.get("evolution", {}).get("rising", 0)
        falling = trends.get("evolution", {}).get("falling", 0)

        col1.metric(
            "📄 Total Pages",
            total_pages,
            delta=f"+{pages_delta} (7j)" if pages_delta > 0 else f"{pages_delta} (7j)" if pages_delta < 0 else None,
            delta_color="normal"
        )
        col2.metric(
            "✅ Actives",
            actives,
            delta=f"📈 {rising} montantes" if rising > 0 else None,
            delta_color="normal"
        )
        col3.metric("🚀 XXL (>=150)", xxl_count)
        col4.metric("🛒 Shopify", shopify_count)
        col5.metric(
            "🏆 Winning (7j)",
            winning_total,
            delta=f"+{winning_delta} vs sem. préc." if winning_delta > 0 else f"{winning_delta} vs sem. préc." if winning_delta < 0 else None,
            delta_color="normal" if winning_delta >= 0 else "inverse"
        )

        # Encart Tendances (7 jours)
        if rising > 0 or falling > 0 or pages_delta != 0 or winning_delta != 0:
            with st.expander("📈 Tendances (7 derniers jours)", expanded=False):
                trend_cols = st.columns(4)
                with trend_cols[0]:
                    st.metric(
                        "Nouvelles pages",
                        trends.get("pages", {}).get("current", 0),
                        delta=f"+{pages_delta}" if pages_delta > 0 else str(pages_delta) if pages_delta < 0 else "stable"
                    )
                with trend_cols[1]:
                    st.metric(
                        "Winning ads",
                        trends.get("winning_ads", {}).get("current", 0),
                        delta=f"+{winning_delta}" if winning_delta > 0 else str(winning_delta) if winning_delta < 0 else "stable"
                    )
                with trend_cols[2]:
                    searches_delta = trends.get("searches", {}).get("delta", 0)
                    st.metric(
                        "Recherches",
                        trends.get("searches", {}).get("current", 0),
                        delta=f"+{searches_delta}" if searches_delta > 0 else str(searches_delta) if searches_delta < 0 else "stable"
                    )
                with trend_cols[3]:
                    net_evolution = rising - falling
                    st.metric(
                        "Balance evolution",
                        f"{rising} / {falling}",
                        delta=f"+{net_evolution} net" if net_evolution > 0 else f"{net_evolution} net" if net_evolution < 0 else "equilibre",
                        delta_color="normal" if net_evolution >= 0 else "inverse"
                    )

        # Quick Alerts
        alerts = generate_alerts(db)
        if alerts:
            st.markdown("---")
            st.subheader("🔔 Alertes")
            alert_cols = st.columns(min(len(alerts), 4))
            for i, alert in enumerate(alerts[:4]):
                with alert_cols[i]:
                    if alert["type"] == "success":
                        st.success(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")
                    elif alert["type"] == "warning":
                        st.warning(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")
                    else:
                        st.info(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")

        st.markdown("---")

        # Info card pour debutants
        info_card(
            "Comment lire ces graphiques ?",
            """
            <b>Etats des pages</b> : Classement base sur le nombre d'annonces actives.<br>
            - <b>XXL</b> (>=150 ads) = Pages tres actives, probablement rentables<br>
            - <b>XL</b> (80-149) = Pages performantes<br>
            - <b>L</b> (35-79) = Bonne activite<br>
            - <b>M/S/XS</b> = Activite moderee a faible<br><br>
            <b>CMS</b> : La technologie utilisee par le site (Shopify est le plus courant en e-commerce).
            """,
            "info"
        )

        # Graphiques ameliores
        col1, col2 = st.columns(2)

        with col1:
            chart_header(
                "Repartition par Etat",
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
                    st.plotly_chart(fig, key="dash_etats", width="stretch")
            else:
                st.info("Aucune donnee disponible")

        with col2:
            chart_header(
                "Repartition par CMS",
                "Technologie e-commerce utilisee par les sites",
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
                st.plotly_chart(fig, key="dash_cms", width="stretch")
            else:
                st.info("Aucune donnee disponible")

        # Top performers avec score
        st.markdown("---")
        st.subheader("Top Performers (avec Score)")

        top_pages = search_pages(db, limit=15)
        if top_pages:
            # Calculer les scores
            for page in top_pages:
                winning_count = winning_by_page.get(page["page_id"], 0)
                page["score"] = calculate_page_score(page, winning_count)
                page["winning_count"] = winning_count
                page["score_display"] = f"{get_score_color(page['score'])} {page['score']}"

            # Trier par score
            top_pages = sorted(top_pages, key=lambda x: x["score"], reverse=True)[:10]

            # Formater etats avec badges
            for p in top_pages:
                p["etat_display"] = format_state_for_df(p.get("etat", ""))

            df = pd.DataFrame(top_pages)
            cols_to_show = ["page_name", "cms", "etat_display", "nombre_ads_active", "winning_count", "score_display"]
            col_names = ["Nom", "CMS", "Etat", "Ads", "Winning", "Score"]
            df_display = df[[c for c in cols_to_show if c in df.columns]]
            df_display.columns = col_names[:len(df_display.columns)]
            st.dataframe(df_display, width="stretch", hide_index=True)

            # Export button
            csv_data = export_to_csv(top_pages)
            st.download_button(
                "Exporter en CSV",
                csv_data,
                "top_performers.csv",
                "text/csv",
                key="export_top"
            )
        else:
            st.info("Aucune page en base. Lancez une recherche pour commencer.")

        # Tendances
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("En forte croissance (7j)")
            trend_data = detect_trends(db, days=7)
            if trend_data["rising"]:
                for t in trend_data["rising"][:5]:
                    st.write(f"**{t['nom_site']}** +{t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune tendance detectee")

        with col2:
            st.subheader("En declin")
            if trend_data.get("falling"):
                for t in trend_data["falling"][:5]:
                    st.write(f"**{t['nom_site']}** {t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune page en declin")

    except Exception as e:
        st.error(f"Erreur: {e}")
