"""
Page Monitoring - Surveillance et alertes des pages publicitaires.

Ce module fournit les outils de monitoring pour suivre l'evolution des
annonceurs dans le temps et detecter les opportunites/risques.

Fonctionnalites principales:
----------------------------
1. Watchlists (render_watchlists):
   - Top performers: Pages XXL/XL avec le plus d'ads actives
   - Top winning ads: Ads avec le meilleur ratio reach/age
   - Pages avec winning: Classement par nombre de winning ads

2. Alertes (render_alerts + generate_alerts):
   - Nouvelles pages XXL detectees
   - Pages en forte croissance (+50% en 7 jours)
   - Pages en declin (-30% ou plus)
   - Winning ads du jour
   - Changements d'etat (promotions/regressions)

3. Monitoring (render_monitoring):
   - Evolution temporelle des pages
   - Comparaison multi-pages
   - Graphiques de tendance

4. Detection de tendances (detect_trends):
   - Identification des pages en croissance rapide
   - Detection des pages en chute

Seuils de detection:
--------------------
- Croissance forte: +50% d'ads en 7 jours
- Declin: -30% d'ads ou plus en 7 jours
- Page XXL: >= 150 ads actives
- Page XL: >= 80 ads actives

Ces seuils sont calibres pour detecter les changements significatifs
sans generer trop de faux positifs.
"""
from datetime import datetime, timedelta
from collections import Counter
from itertools import groupby

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import (
    CHART_COLORS, chart_header, create_trend_chart
)
from src.infrastructure.persistence.database import (
    search_pages, get_winning_ads, get_winning_ads_by_page,
    get_evolution_stats, get_page_evolution_history,
    get_winning_ads_stats, get_winning_ads_stats_filtered,
    DatabaseManager, get_etat_from_ads_count
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


def render_watchlists():
    """Page Watchlists - Listes de surveillance"""
    from src.presentation.streamlit.dashboard import (
        render_classification_filters, render_date_filter
    )

    st.title("Watchlists")
    st.markdown("Gerer vos listes de surveillance")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Filtres de classification + date
    st.markdown("#### Filtres")
    filter_col1, filter_col2 = st.columns([3, 1])

    with filter_col1:
        filters = render_classification_filters(db, key_prefix="watchlists", columns=3)

    with filter_col2:
        days_filter = render_date_filter(key_prefix="watchlists")

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"{filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"{filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"{filters['pays']}")
    if days_filter > 0:
        active_filters.append(f"{days_filter}j")

    if active_filters:
        st.caption(f"Filtres actifs: {' - '.join(active_filters)}")

    st.markdown("---")

    # Creer 3 onglets pour les differentes vues
    tab1, tab2, tab3 = st.tabs(["Top Performers", "Top Winning Ads", "Pages avec le + de Winning Ads"])

    # TAB 1: Top Performers
    with tab1:
        st.subheader("Top Performers (>=80 ads)")
        try:
            top_pages = search_pages(
                db, etat="XXL", limit=20,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays"),
                days=days_filter if days_filter > 0 else None
            )
            top_pages.extend(search_pages(
                db, etat="XL", limit=20,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays"),
                days=days_filter if days_filter > 0 else None
            ))

            if top_pages:
                # Trier par nombre d'ads decroissant
                top_pages_sorted = sorted(top_pages, key=lambda x: x.get("nombre_ads_active", 0), reverse=True)[:20]
                df = pd.DataFrame(top_pages_sorted)

                # Formater la date
                if "dernier_scan" in df.columns:
                    df["dernier_scan"] = pd.to_datetime(df["dernier_scan"]).dt.strftime("%d/%m/%Y %H:%M")

                cols = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active", "dernier_scan", "subcategory", "pays"]
                df_display = df[[c for c in cols if c in df.columns]]
                df_display.columns = ["Page", "Site", "CMS", "Etat", "Ads Actives", "Dernier Scan", "Categorie", "Pays"][:len(df_display.columns)]

                col_table, col_export = st.columns([4, 1])
                with col_table:
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                with col_export:
                    render_csv_download(df_display, f"top_performers_{datetime.now().strftime('%Y%m%d')}.csv", "CSV")
            else:
                st.info("Aucune page XXL/XL trouvee")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # TAB 2: Top Winning Ads
    with tab2:
        st.subheader("Top Winning Ads (Best Performers)")
        st.caption("Ads avec le plus grand reach et duree de diffusion")

        try:
            # Recuperer les meilleures winning ads (utilise le filtre de jours)
            winning_ads = get_winning_ads(db, limit=50, days=days_filter if days_filter > 0 else 30)

            if winning_ads:
                # Creer un DataFrame pour l'affichage
                ads_data = []
                for ad in winning_ads[:20]:
                    # Formater le reach
                    reach = ad.get("eu_total_reach", 0) or 0
                    if reach >= 1000000:
                        reach_str = f"{reach/1000000:.1f}M"
                    elif reach >= 1000:
                        reach_str = f"{reach/1000:.0f}K"
                    else:
                        reach_str = str(reach)

                    # Extraire le texte de l'ad
                    bodies = ad.get("ad_creative_bodies", "")
                    if isinstance(bodies, str):
                        try:
                            import json
                            bodies = json.loads(bodies) if bodies.startswith("[") else [bodies]
                        except:
                            bodies = [bodies] if bodies else []
                    ad_text = bodies[0][:80] + "..." if bodies and len(bodies[0]) > 80 else (bodies[0] if bodies else "N/A")

                    # Formater la date
                    date_scan = ad.get("date_scan")
                    date_str = date_scan.strftime("%d/%m/%Y %H:%M") if date_scan else "-"

                    ads_data.append({
                        "Page": ad.get("page_name", "N/A"),
                        "Texte Ad": ad_text,
                        "Reach EU": reach_str,
                        "Age (jours)": ad.get("ad_age_days", 0),
                        "Date Scan": date_str,
                        "Criteres": ad.get("matched_criteria", ""),
                        "Lien": ad.get("ad_snapshot_url", "")
                    })

                df = pd.DataFrame(ads_data)

                col_table, col_export = st.columns([4, 1])
                with col_table:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                with col_export:
                    render_csv_download(df, f"top_winning_ads_{datetime.now().strftime('%Y%m%d')}.csv", "CSV")

                # Bouton pour voir les details
                with st.expander("Details des Winning Ads"):
                    for i, ad in enumerate(winning_ads[:10]):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{ad.get('page_name', 'N/A')}**")
                            bodies = ad.get("ad_creative_bodies", "")
                            if isinstance(bodies, str):
                                try:
                                    import json
                                    bodies = json.loads(bodies) if bodies.startswith("[") else [bodies]
                                except:
                                    bodies = [bodies] if bodies else []
                            if bodies:
                                st.caption(bodies[0][:200])
                        with col2:
                            if ad.get("ad_snapshot_url"):
                                st.link_button("Voir", ad["ad_snapshot_url"], use_container_width=True)
                        st.divider()
            else:
                st.info("Aucune winning ad trouvee")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # TAB 3: Pages avec le plus de Winning Ads
    with tab3:
        st.subheader("Pages avec le plus de Winning Ads")
        st.caption("Classement des pages par nombre de winning ads")

        try:
            # Recuperer le nombre de winning ads par page (utilise le filtre de jours)
            winning_by_page = get_winning_ads_by_page(db, days=days_filter if days_filter > 0 else 30)

            if winning_by_page:
                # Trier par nombre decroissant
                sorted_pages = sorted(winning_by_page.items(), key=lambda x: x[1], reverse=True)[:30]

                # Recuperer les infos des pages
                pages_data = []
                for page_id, count in sorted_pages:
                    # Chercher les infos de la page
                    page_info = search_pages(db, page_id=page_id, limit=1)
                    if page_info:
                        p = page_info[0]
                        # Formater la date
                        dernier_scan = p.get("dernier_scan")
                        date_str = dernier_scan.strftime("%d/%m/%Y") if dernier_scan else "-"

                        pages_data.append({
                            "Page": p.get("page_name", "N/A"),
                            "Site": p.get("lien_site", ""),
                            "Winning Ads": count,
                            "Ads Actives": p.get("nombre_ads_active", 0),
                            "Dernier Scan": date_str,
                            "CMS": p.get("cms", "N/A"),
                            "Etat": p.get("etat", "N/A"),
                            "Categorie": p.get("subcategory", ""),
                            "page_id": page_id
                        })
                    else:
                        # Si page pas trouvee, recuperer le nom depuis les winning ads
                        winning = get_winning_ads(db, page_id=page_id, limit=1)
                        page_name = winning[0].get("page_name", page_id) if winning else page_id
                        pages_data.append({
                            "Page": page_name,
                            "Site": "",
                            "Winning Ads": count,
                            "Ads Actives": 0,
                            "Dernier Scan": "-",
                            "CMS": "N/A",
                            "Etat": "N/A",
                            "Categorie": "",
                            "page_id": page_id
                        })

                if pages_data:
                    df = pd.DataFrame(pages_data)
                    # Afficher sans le page_id
                    display_cols = ["Page", "Site", "Winning Ads", "Ads Actives", "Dernier Scan", "CMS", "Etat", "Categorie"]

                    col_table, col_export = st.columns([4, 1])
                    with col_table:
                        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                    with col_export:
                        render_csv_download(df[display_cols], f"pages_winning_ranking_{datetime.now().strftime('%Y%m%d')}.csv", "CSV")

                    # Top 3 en metrique
                    st.markdown("##### Podium")
                    col1, col2, col3 = st.columns(3)
                    if len(pages_data) >= 1:
                        with col1:
                            st.metric("1er", pages_data[0]["Page"][:20], f"{pages_data[0]['Winning Ads']} winning ads")
                    if len(pages_data) >= 2:
                        with col2:
                            st.metric("2eme", pages_data[1]["Page"][:20], f"{pages_data[1]['Winning Ads']} winning ads")
                    if len(pages_data) >= 3:
                        with col3:
                            st.metric("3eme", pages_data[2]["Page"][:20], f"{pages_data[2]['Winning Ads']} winning ads")
            else:
                st.info("Aucune winning ad enregistree")
        except Exception as e:
            st.error(f"Erreur: {e}")


def render_alerts():
    """Page Alerts - Alertes et notifications"""
    from src.presentation.streamlit.dashboard import (
        render_classification_filters, detect_trends, generate_alerts
    )

    st.title("Alerts")
    st.markdown("Alertes et changements detectes automatiquement")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Filtres de classification
    st.markdown("#### Filtres")
    filters = render_classification_filters(db, key_prefix="alerts", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"{filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"{filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"{filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' - '.join(active_filters)}")

    st.markdown("---")

    try:
        alerts = generate_alerts(
            db,
            thematique=filters.get("thematique"),
            subcategory=filters.get("subcategory"),
            pays=filters.get("pays")
        )

        if alerts:
            st.success(f"{len(alerts)} alerte(s) active(s)")

            for alert in alerts:
                if alert["type"] == "success":
                    with st.expander(f"{alert['icon']} {alert['title']}", expanded=True):
                        st.success(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    change = item.get("change", "")
                                    if change:
                                        st.write(f"  - {name} ({change})")
                                    else:
                                        st.write(f"  - {name}")

                elif alert["type"] == "warning":
                    with st.expander(f"{alert['icon']} {alert['title']}", expanded=True):
                        st.warning(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    delta = item.get("pct_ads", 0)
                                    change = item.get("change", "")
                                    if change:
                                        st.write(f"  - {name} ({change})")
                                    else:
                                        st.write(f"  - {name} ({delta:+.0f}%)")

                else:
                    with st.expander(f"{alert['icon']} {alert['title']}", expanded=True):
                        st.info(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    delta = item.get("pct_ads", 0)
                                    ads = item.get("ads_actuel", 0)
                                    if delta:
                                        st.write(f"  - {name} ({delta:+.0f}%, {ads} ads)")
                                    else:
                                        st.write(f"  - {name}")

                st.markdown("")
        else:
            st.info("Aucune alerte pour le moment")
            st.caption("Les alertes sont generees automatiquement lors des scans")

        # Section detection manuelle
        st.markdown("---")
        st.subheader("Detection manuelle")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Rechercher pages en croissance", width="stretch"):
                trends = detect_trends(db, days=7)
                if trends["rising"]:
                    st.success(f"{len(trends['rising'])} page(s) en forte croissance")
                    for t in trends["rising"]:
                        st.write(f"**{t['nom_site']}** +{t['pct_ads']:.0f}%")
                else:
                    st.info("Aucune page en forte croissance")

        with col2:
            if st.button("Rechercher pages en declin", width="stretch"):
                trends = detect_trends(db, days=7)
                if trends["falling"]:
                    st.warning(f"{len(trends['falling'])} page(s) en declin")
                    for t in trends["falling"]:
                        st.write(f"**{t['nom_site']}** {t['pct_ads']:.0f}%")
                else:
                    st.info("Aucune page en declin detectee")

    except Exception as e:
        st.error(f"Erreur: {e}")


def render_monitoring():
    """Page Monitoring - Suivi historique et evolution"""
    st.title("Monitoring")
    st.markdown("Suivi de l'evolution des pages depuis le dernier scan")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Selecteur de periode
    col1, col2 = st.columns([1, 3])
    with col1:
        period = st.selectbox(
            "Periode",
            options=[7, 14, 30],
            format_func=lambda x: f"1 semaine" if x == 7 else f"2 semaines" if x == 14 else "1 mois",
            index=0
        )

    # Section evolution
    st.subheader("Evolution depuis le dernier scan")

    try:
        evolution = get_evolution_stats(db, period_days=period)

        if evolution:
            st.info(f"{len(evolution)} pages avec evolution sur les {period} derniers jours")

            # Metriques globales
            total_up = sum(1 for e in evolution if e["delta_ads"] > 0)
            total_down = sum(1 for e in evolution if e["delta_ads"] < 0)
            total_stable = sum(1 for e in evolution if e["delta_ads"] == 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("En hausse", total_up)
            col2.metric("En baisse", total_down)
            col3.metric("Stable", total_stable)

            # Tableau d'evolution
            st.markdown("---")

            for evo in evolution[:20]:  # Top 20
                delta_color = "green" if evo["delta_ads"] > 0 else "red" if evo["delta_ads"] < 0 else "gray"
                delta_icon = "+" if evo["delta_ads"] > 0 else "-" if evo["delta_ads"] < 0 else "="

                with st.expander(f"{delta_icon} **{evo['nom_site']}** - {evo['delta_ads']:+d} ads ({evo['pct_ads']:+.1f}%)"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric(
                            "Ads actives",
                            evo["ads_actuel"],
                            delta=f"{evo['delta_ads']:+d}",
                            delta_color="normal" if evo["delta_ads"] >= 0 else "inverse"
                        )

                    with col2:
                        st.metric(
                            "Produits",
                            evo["produits_actuel"],
                            delta=f"{evo['delta_produits']:+d}" if evo["delta_produits"] != 0 else None
                        )

                    with col3:
                        st.metric("Duree entre scans", f"{evo['duree_jours']:.1f} jours")

                    # Dates des scans
                    st.caption(f"Scan actuel: {evo['date_actuel'].strftime('%Y-%m-%d %H:%M') if evo['date_actuel'] else 'N/A'}")
                    st.caption(f"Scan precedent: {evo['date_precedent'].strftime('%Y-%m-%d %H:%M') if evo['date_precedent'] else 'N/A'}")

                    # Bouton pour voir l'historique complet
                    if st.button(f"Voir historique complet", key=f"hist_{evo['page_id']}"):
                        st.session_state.monitoring_page_id = evo["page_id"]
                        st.rerun()
        else:
            st.info("Aucune evolution detectee. Effectuez plusieurs scans pour voir les changements.")
    except Exception as e:
        st.error(f"Erreur: {e}")

    st.markdown("---")

    # Section historique d'une page specifique
    st.subheader("Historique d'une page")

    # Recuperer page_id depuis session ou input
    default_page_id = st.session_state.get("monitoring_page_id", "")
    page_id = st.text_input("Entrer un Page ID", value=default_page_id)

    if page_id:
        try:
            history = get_page_evolution_history(db, page_id=page_id, limit=50)

            if history and len(history) > 0:
                st.success(f"{len(history)} scans trouves")

                # Graphique d'evolution ameliore
                if len(history) > 1:
                    chart_header(
                        "Evolution dans le temps",
                        "Suivi du nombre d'annonces et de produits",
                        "La ligne pointillee indique la tendance generale"
                    )

                    dates = [h["date_scan"] for h in history]
                    ads_values = [h["nombre_ads_active"] for h in history]
                    products_values = [h["nombre_produits"] for h in history]

                    fig = create_trend_chart(
                        dates=dates,
                        values=ads_values,
                        value_name="Ads actives",
                        color=CHART_COLORS["primary"],
                        secondary_values=products_values,
                        secondary_name="Produits",
                        show_trend=True,
                        height=350
                    )
                    st.plotly_chart(fig, key="monitoring_page_chart", width="stretch")

                # Tableau avec deltas
                df_data = []
                for h in history:
                    delta_ads_str = f"{h['delta_ads']:+d}" if h["delta_ads"] != 0 else "-"
                    delta_prod_str = f"{h['delta_produits']:+d}" if h["delta_produits"] != 0 else "-"
                    df_data.append({
                        "Date": h["date_scan"].strftime("%Y-%m-%d %H:%M") if h["date_scan"] else "",
                        "Ads": h["nombre_ads_active"],
                        "Delta Ads": delta_ads_str,
                        "Produits": h["nombre_produits"],
                        "Delta Produits": delta_prod_str
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info("Aucun historique trouve pour cette page")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # COMPARAISON DE PAGES
    st.markdown("---")
    st.subheader("Comparer des pages")
    st.caption("Comparez jusqu'a 3 pages cote a cote")

    col1, col2, col3 = st.columns(3)

    with col1:
        page1_id = st.text_input("Page 1", placeholder="Page ID", key="compare_page1")
    with col2:
        page2_id = st.text_input("Page 2", placeholder="Page ID", key="compare_page2")
    with col3:
        page3_id = st.text_input("Page 3 (optionnel)", placeholder="Page ID", key="compare_page3")

    if st.button("Comparer", type="primary", key="compare_btn"):
        pages_to_compare = [p for p in [page1_id, page2_id, page3_id] if p]

        if len(pages_to_compare) >= 2:
            comparison_data = []

            for pid in pages_to_compare:
                page_results = search_pages(db, search_term=pid, limit=1)
                if page_results:
                    page = page_results[0]
                    # Recuperer l'historique
                    history = get_page_evolution_history(db, page_id=pid, limit=10)
                    avg_ads = sum(h["nombre_ads_active"] for h in history) / len(history) if history else 0
                    trend = "+" if history and len(history) > 1 and history[0]["delta_ads"] > 0 else "-" if history and len(history) > 1 and history[0]["delta_ads"] < 0 else "="

                    # Winning ads count
                    winning = get_winning_ads(db, page_id=pid, limit=100)
                    winning_count = len(winning) if winning else 0

                    comparison_data.append({
                        "Page ID": pid,
                        "Nom": page.get("page_name", "N/A")[:25],
                        "CMS": page.get("cms", "N/A"),
                        "Etat": page.get("etat", "N/A"),
                        "Ads actives": page.get("nombre_ads_active", 0),
                        "Produits": page.get("nombre_produits", 0),
                        "Winning Ads": winning_count,
                        "Moy. Ads": f"{avg_ads:.0f}",
                        "Tendance": trend
                    })
                else:
                    comparison_data.append({
                        "Page ID": pid,
                        "Nom": "Non trouvee",
                        "CMS": "-",
                        "Etat": "-",
                        "Ads actives": 0,
                        "Produits": 0,
                        "Winning Ads": 0,
                        "Moy. Ads": "-",
                        "Tendance": "-"
                    })

            # Afficher la comparaison
            st.markdown("##### Resultat de la comparaison")
            df_compare = pd.DataFrame(comparison_data)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)

            # Graphique de comparaison
            if any(d["Ads actives"] > 0 for d in comparison_data):
                fig = go.Figure(data=[
                    go.Bar(name='Ads actives', x=[d["Nom"] for d in comparison_data], y=[d["Ads actives"] for d in comparison_data], marker_color=CHART_COLORS["primary"]),
                    go.Bar(name='Winning Ads', x=[d["Nom"] for d in comparison_data], y=[d["Winning Ads"] for d in comparison_data], marker_color=CHART_COLORS["success"])
                ])
                fig.update_layout(
                    barmode='group',
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True, key="compare_chart")
        else:
            st.warning("Entrez au moins 2 Page IDs pour comparer")


def detect_trends(db: DatabaseManager, days: int = 7) -> dict:
    """
    Detecte les tendances (pages en forte croissance/decroissance)

    Returns:
        Dict avec 'rising' et 'falling' lists
    """
    evolution = get_evolution_stats(db, period_days=days)

    rising = []
    falling = []

    for evo in evolution:
        delta_pct = evo.get("pct_ads", 0)

        if delta_pct >= 50:  # +50% ou plus
            rising.append({
                "page_id": evo["page_id"],
                "nom_site": evo["nom_site"],
                "delta_ads": evo["delta_ads"],
                "pct_ads": delta_pct,
                "ads_actuel": evo["ads_actuel"]
            })
        elif delta_pct <= -30:  # -30% ou moins
            falling.append({
                "page_id": evo["page_id"],
                "nom_site": evo["nom_site"],
                "delta_ads": evo["delta_ads"],
                "pct_ads": delta_pct,
                "ads_actuel": evo["ads_actuel"]
            })

    return {
        "rising": sorted(rising, key=lambda x: x["pct_ads"], reverse=True)[:10],
        "falling": sorted(falling, key=lambda x: x["pct_ads"])[:10]
    }


def generate_alerts(
    db: DatabaseManager,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None
) -> list:
    """
    Genere des alertes basees sur les donnees

    Args:
        db: DatabaseManager
        thematique: Filtre par categorie
        subcategory: Filtre par sous-categorie
        pays: Filtre par pays

    Returns:
        Liste d'alertes avec type, message, data
    """
    from src.infrastructure.persistence.database import SuiviPage
    from sqlalchemy import func, desc

    alerts = []

    try:
        # Alerte: Nouvelles pages XXL
        xxl_pages = search_pages(
            db, etat="XXL", limit=50,
            thematique=thematique, subcategory=subcategory, pays=pays
        )
        recent_xxl = [p for p in xxl_pages if p.get("dernier_scan") and
                      (datetime.utcnow() - p["dernier_scan"]).days <= 1]
        if recent_xxl:
            alerts.append({
                "type": "success",
                "icon": "rocket",
                "title": f"{len(recent_xxl)} nouvelle(s) page(s) XXL",
                "message": f"Pages detectees avec >=150 ads actives",
                "data": recent_xxl[:5]
            })

        # Alerte: Tendances a la hausse
        trends = detect_trends(db, days=7)
        # Filter trends if classification filters are active
        if thematique or subcategory or pays:
            filtered_pages = search_pages(
                db, limit=1000,
                thematique=thematique, subcategory=subcategory, pays=pays
            )
            filtered_ids = {p["page_id"] for p in filtered_pages}

            trends["rising"] = [t for t in trends.get("rising", []) if t.get("page_id") in filtered_ids]
            trends["falling"] = [t for t in trends.get("falling", []) if t.get("page_id") in filtered_ids]

        if trends["rising"]:
            alerts.append({
                "type": "info",
                "icon": "trending_up",
                "title": f"{len(trends['rising'])} page(s) en forte croissance",
                "message": "Pages avec +50% d'ads en 7 jours",
                "data": trends["rising"][:5]
            })

        # Alerte: Pages en chute
        if trends["falling"]:
            alerts.append({
                "type": "warning",
                "icon": "trending_down",
                "title": f"{len(trends['falling'])} page(s) en declin",
                "message": "Pages avec -30% d'ads ou plus",
                "data": trends["falling"][:5]
            })

        # Alerte: Winning ads recentes (avec filtres si actifs)
        if thematique or subcategory or pays:
            winning_stats = get_winning_ads_stats_filtered(
                db, days=1,
                thematique=thematique, subcategory=subcategory, pays=pays
            )
        else:
            winning_stats = get_winning_ads_stats(db, days=1)

        if winning_stats.get("total", 0) > 0:
            alerts.append({
                "type": "success",
                "icon": "trophy",
                "title": f"{winning_stats['total']} winning ad(s) aujourd'hui",
                "message": f"Reach moyen: {winning_stats.get('avg_reach', 0):,}",
                "data": winning_stats.get("by_page", [])[:5]
            })

        # Alerte: Changements d'etat
        state_changes = []
        state_order = {"inactif": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6}

        with db.get_session() as session:
            recent_scans = session.query(
                SuiviPage.page_id,
                SuiviPage.nom_site,
                SuiviPage.nombre_ads_active,
                SuiviPage.date_scan
            ).filter(
                SuiviPage.date_scan >= datetime.utcnow() - timedelta(days=7)
            ).order_by(
                SuiviPage.page_id,
                desc(SuiviPage.date_scan)
            ).all()

            for page_id, scans in groupby(recent_scans, key=lambda x: x.page_id):
                scans_list = list(scans)
                if len(scans_list) >= 2:
                    latest = scans_list[0]
                    previous = scans_list[1]

                    current_state = get_etat_from_ads_count(latest.nombre_ads_active)
                    prev_state = get_etat_from_ads_count(previous.nombre_ads_active)

                    if current_state != prev_state:
                        current_rank = state_order.get(current_state, 0)
                        prev_rank = state_order.get(prev_state, 0)

                        if current_rank > prev_rank:
                            state_changes.append({
                                "page_id": page_id,
                                "page_name": latest.nom_site,
                                "from_state": prev_state,
                                "to_state": current_state,
                                "direction": "up",
                                "ads": latest.nombre_ads_active
                            })
                        else:
                            state_changes.append({
                                "page_id": page_id,
                                "page_name": latest.nom_site,
                                "from_state": prev_state,
                                "to_state": current_state,
                                "direction": "down",
                                "ads": latest.nombre_ads_active
                            })

        promotions = [s for s in state_changes if s["direction"] == "up"]
        degradations = [s for s in state_changes if s["direction"] == "down"]

        if promotions:
            alerts.append({
                "type": "success",
                "icon": "arrow_up",
                "title": f"{len(promotions)} page(s) en progression",
                "message": "Pages ayant change d'etat vers le haut",
                "data": [{"page_name": p["page_name"], "pct_ads": 0, "change": f"{p['from_state']} -> {p['to_state']}"} for p in promotions[:5]]
            })

        if degradations:
            alerts.append({
                "type": "warning",
                "icon": "arrow_down",
                "title": f"{len(degradations)} page(s) en regression",
                "message": "Pages ayant change d'etat vers le bas",
                "data": [{"page_name": p["page_name"], "pct_ads": 0, "change": f"{p['from_state']} -> {p['to_state']}"} for p in degradations[:5]]
            })

    except Exception:
        pass

    return alerts
