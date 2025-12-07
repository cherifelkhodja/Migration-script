"""
Page Analytics - Analyses avancees.
"""
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import (
    CHART_COLORS, info_card, chart_header,
    create_horizontal_bar_chart, export_to_csv
)
from src.infrastructure.persistence.database import (
    get_suivi_stats, search_pages, get_page_evolution_history
)


def render_csv_download(df: pd.DataFrame, filename: str, label: str = "📥 Exporter CSV"):
    """Bouton de telechargement CSV."""
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv"
    )


def render_analytics():
    """Page Analytics - Analyses avancees"""
    st.title("📊 Analytics")
    st.markdown("Analyses et statistiques avancees")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    try:
        stats = get_suivi_stats(db)

        # Info card
        info_card(
            "Que signifient ces statistiques ?",
            """
            Cette page vous donne une vue d'ensemble de votre base de donnees de pages publicitaires.<br><br>
            • <b>Distribution par Etat</b> : Montre combien de pages sont dans chaque categorie d'activite<br>
            • <b>Distribution par CMS</b> : Les plateformes e-commerce utilisees (Shopify domine le marche)<br>
            • <b>Thematiques</b> : Les niches/secteurs les plus representes dans votre base
            """,
            "📚"
        )

        # Stats generales
        col1, col2, col3, col4 = st.columns(4)

        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})
        total_pages = stats.get("total_pages", 0)
        actives = sum(v for k, v in etats.items() if k != "inactif")

        col1.metric("📄 Total Pages", f"{total_pages:,}")
        col2.metric("✅ Pages Actives", f"{actives:,}")
        col3.metric("🛒 CMS Differents", len(cms_stats))

        # Taux d'activite
        taux_actif = (actives / total_pages * 100) if total_pages > 0 else 0
        col4.metric("📈 Taux d'activite", f"{taux_actif:.1f}%")

        st.markdown("---")

        # Graphiques cote a cote
        col1, col2 = st.columns(2)

        with col1:
            chart_header(
                "📊 Distribution par Etat",
                "Nombre de pages par niveau d'activite",
                "Plus une page a d'ads actives, plus elle est probablement performante"
            )
            if etats:
                # Ordonner les etats
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = [(k, etats.get(k, 0)) for k in ordre_etats if etats.get(k, 0) > 0]

                labels = [e[0] for e in etats_ordonne]
                values = [e[1] for e in etats_ordonne]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    value_suffix=" pages",
                    height=300
                )
                st.plotly_chart(fig, key="analytics_states", width="stretch")
            else:
                st.info("Aucune donnee disponible")

        with col2:
            chart_header(
                "🛒 Distribution par CMS",
                "Plateformes e-commerce utilisees",
                "Shopify est le leader du marche dropshipping"
            )
            if cms_stats:
                # Trier par valeur decroissante
                sorted_cms = sorted(cms_stats.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_cms]
                values = [c[1] for c in sorted_cms]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    value_suffix=" sites",
                    height=300
                )
                st.plotly_chart(fig, key="analytics_cms", width="stretch")
            else:
                st.info("Aucune donnee disponible")

        # Top thematiques
        st.markdown("---")
        chart_header(
            "🏷️ Analyse par thematique",
            "Repartition des pages selon leur niche/secteur",
            "Identifiez les marches les plus competitifs"
        )

        all_pages = search_pages(db, limit=500)
        if all_pages:
            themes = {}
            for p in all_pages:
                theme = p.get("thematique", "Non classe") or "Non classe"
                themes[theme] = themes.get(theme, 0) + 1

            if themes:
                # Trier et prendre top 10
                sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:10]
                labels = [t[0] for t in sorted_themes]
                values = [t[1] for t in sorted_themes]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    colors=[CHART_COLORS["info"]] * len(labels),
                    value_suffix=" pages",
                    height=350
                )
                st.plotly_chart(fig, key="analytics_themes", width="stretch")
        else:
            st.info("Aucune donnee disponible")

        # Graphiques d'evolution
        _render_evolution_charts(db)

        # Evolution d'une page specifique
        _render_page_evolution(db)

    except Exception as e:
        st.error(f"Erreur: {e}")


def _render_evolution_charts(db):
    """Affiche les graphiques d'evolution temporelle."""
    st.markdown("---")
    chart_header(
        "📈 Evolution temporelle",
        "Historique des scans et tendances",
        "Suivez l'evolution de votre base de donnees au fil du temps"
    )

    # Recuperer les donnees de suivi pour les graphiques
    from src.infrastructure.persistence.database import SuiviPage
    from sqlalchemy import func

    with db.get_session() as session:
        # Donnees agregees par jour
        daily_stats = session.query(
            func.date(SuiviPage.date_scan).label('date'),
            func.count(func.distinct(SuiviPage.page_id)).label('pages_scanned'),
            func.avg(SuiviPage.nombre_ads_active).label('avg_ads'),
            func.sum(SuiviPage.nombre_ads_active).label('total_ads')
        ).group_by(
            func.date(SuiviPage.date_scan)
        ).order_by(
            func.date(SuiviPage.date_scan)
        ).limit(60).all()

    if daily_stats:
        df_evolution = pd.DataFrame([
            {
                "Date": row.date,
                "Pages scannees": row.pages_scanned,
                "Ads moyennes": round(row.avg_ads or 0, 1),
                "Total ads": row.total_ads or 0
            }
            for row in daily_stats
        ])

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 📊 Pages scannees par jour")
            fig1 = px.area(
                df_evolution,
                x="Date",
                y="Pages scannees",
                color_discrete_sequence=[CHART_COLORS["primary"]]
            )
            fig1.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
            )
            st.plotly_chart(fig1, key="evolution_pages", use_container_width=True)

        with col2:
            st.markdown("##### 📈 Moyenne d'ads actives")
            fig2 = px.line(
                df_evolution,
                x="Date",
                y="Ads moyennes",
                color_discrete_sequence=[CHART_COLORS["success"]]
            )
            fig2.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
            )
            fig2.update_traces(line=dict(width=3))
            st.plotly_chart(fig2, key="evolution_ads", use_container_width=True)

        # Export CSV
        render_csv_download(df_evolution, f"evolution_stats_{datetime.now().strftime('%Y%m%d')}.csv", "📥 Export donnees evolution")
    else:
        st.info("Pas assez de donnees pour afficher l'evolution")


def _render_page_evolution(db):
    """Affiche l'evolution d'une page specifique."""
    st.markdown("---")
    st.markdown("##### 🔍 Evolution d'une page specifique")

    page_id_input = st.text_input("Entrez un Page ID", placeholder="Ex: 123456789", key="evolution_page_id")

    if page_id_input:
        page_history = get_page_evolution_history(db, page_id_input, limit=30)

        if page_history:
            df_page = pd.DataFrame(page_history)
            df_page["Date"] = pd.to_datetime(df_page["date_scan"]).dt.strftime("%d/%m")

            col1, col2 = st.columns(2)

            with col1:
                fig_ads = px.bar(
                    df_page,
                    x="Date",
                    y="nombre_ads_active",
                    title="📊 Evolution des Ads actives",
                    color_discrete_sequence=[CHART_COLORS["primary"]]
                )
                fig_ads.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_ads, key="page_ads_evolution", use_container_width=True)

            with col2:
                fig_prod = px.bar(
                    df_page,
                    x="Date",
                    y="nombre_produits",
                    title="📦 Evolution des Produits",
                    color_discrete_sequence=[CHART_COLORS["success"]]
                )
                fig_prod.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_prod, key="page_prod_evolution", use_container_width=True)

            # Tableau des deltas
            st.dataframe(
                df_page[["Date", "nombre_ads_active", "delta_ads", "nombre_produits", "delta_produits"]].rename(columns={
                    "nombre_ads_active": "Ads",
                    "delta_ads": "Δ Ads",
                    "nombre_produits": "Produits",
                    "delta_produits": "Δ Produits"
                }),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning(f"Aucun historique trouve pour la page {page_id_input}")
