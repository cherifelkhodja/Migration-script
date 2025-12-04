"""
Dashboard Streamlit pour Meta Ads Analyzer
Design moderne avec navigation latérale
"""
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import (
    AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES,
    MIN_ADS_INITIAL, MIN_ADS_FOR_EXPORT,
    DEFAULT_COUNTRIES, DEFAULT_LANGUAGES,
    DATABASE_URL, MIN_ADS_SUIVI, MIN_ADS_LISTE
)
from app.meta_api import MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
from app.shopify_detector import detect_cms_from_url
from app.web_analyzer import analyze_website_complete
from app.utils import load_blacklist, is_blacklisted
from app.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, search_pages, get_suivi_history
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_session_state():
    """Initialise le state de la session Streamlit"""
    defaults = {
        'search_results': None,
        'pages_final': {},
        'web_results': {},
        'page_ads': {},
        'search_running': False,
        'stats': {},
        'db': None,
        'current_page': 'Dashboard',
        'countries': ['FR'],
        'languages': ['fr']
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_database() -> DatabaseManager:
    """Récupère ou initialise la connexion à la base de données"""
    if st.session_state.db is None:
        try:
            st.session_state.db = DatabaseManager(DATABASE_URL)
            st.session_state.db.create_tables()
        except Exception as e:
            return None
    return st.session_state.db


# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    """Affiche la sidebar avec navigation"""
    with st.sidebar:
        st.markdown("## 📊 Meta Ads Analyzer")
        st.markdown("---")

        # Main Navigation
        st.markdown("### Main")

        if st.button("🏠 Dashboard", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
            st.session_state.current_page = "Dashboard"
            st.rerun()

        if st.button("🔍 Search Ads", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Search Ads" else "secondary"):
            st.session_state.current_page = "Search Ads"
            st.rerun()

        if st.button("🏪 Pages / Shops", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Pages / Shops" else "secondary"):
            st.session_state.current_page = "Pages / Shops"
            st.rerun()

        if st.button("📋 Watchlists", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Watchlists" else "secondary"):
            st.session_state.current_page = "Watchlists"
            st.rerun()

        if st.button("🔔 Alerts", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Alerts" else "secondary"):
            st.session_state.current_page = "Alerts"
            st.rerun()

        st.markdown("---")
        st.markdown("### More")

        if st.button("📈 Monitoring", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Monitoring" else "secondary"):
            st.session_state.current_page = "Monitoring"
            st.rerun()

        if st.button("📊 Analytics", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
            st.session_state.current_page = "Analytics"
            st.rerun()

        if st.button("⚙️ Settings", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Settings" else "secondary"):
            st.session_state.current_page = "Settings"
            st.rerun()

        # Database status
        st.markdown("---")
        db = get_database()
        if db:
            st.success("🟢 Database connected")
        else:
            st.error("🔴 Database offline")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def render_dashboard():
    """Page Dashboard - Vue d'ensemble"""
    st.title("🏠 Dashboard")
    st.markdown("Vue d'ensemble de vos données")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    try:
        stats = get_suivi_stats(db)

        # KPIs principaux
        col1, col2, col3, col4 = st.columns(4)

        total_pages = stats.get("total_pages", 0)
        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})

        actives = sum(v for k, v in etats.items() if k != "inactif")
        shopify_count = cms_stats.get("Shopify", 0)

        col1.metric("📄 Total Pages", total_pages)
        col2.metric("✅ Pages Actives", actives)
        col3.metric("🛒 Shopify", shopify_count)
        col4.metric("❌ Inactives", etats.get("inactif", 0))

        st.markdown("---")

        # Graphiques
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Répartition par État")
            if etats:
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = [(k, etats.get(k, 0)) for k in ordre_etats if etats.get(k, 0) > 0]
                if etats_ordonne:
                    fig = px.bar(
                        x=[e[0] for e in etats_ordonne],
                        y=[e[1] for e in etats_ordonne],
                        color=[e[0] for e in etats_ordonne],
                        color_discrete_map={
                            "XXL": "#1f77b4", "XL": "#2ca02c", "L": "#98df8a",
                            "M": "#ffbb78", "S": "#ff7f0e", "XS": "#d62728", "inactif": "#7f7f7f"
                        }
                    )
                    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Nombre")
                    st.plotly_chart(fig, key="dash_etats", use_container_width=True)
            else:
                st.info("Aucune donnée disponible")

        with col2:
            st.subheader("Répartition par CMS")
            if cms_stats:
                fig = px.pie(
                    values=list(cms_stats.values()),
                    names=list(cms_stats.keys()),
                    hole=0.4
                )
                fig.update_layout(showlegend=True)
                st.plotly_chart(fig, key="dash_cms", use_container_width=True)
            else:
                st.info("Aucune donnée disponible")

        # Dernières pages
        st.markdown("---")
        st.subheader("📋 Dernières Pages Ajoutées")

        recent_pages = search_pages(db, limit=10)
        if recent_pages:
            df = pd.DataFrame(recent_pages)
            cols_to_show = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active"]
            df_display = df[[c for c in cols_to_show if c in df.columns]]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune page en base. Lancez une recherche pour commencer.")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SEARCH ADS
# ═══════════════════════════════════════════════════════════════════════════════

def render_search_ads():
    """Page Search Ads - Recherche d'annonces"""
    st.title("🔍 Search Ads")
    st.markdown("Rechercher et analyser des annonces Meta")

    # Configuration de recherche
    with st.expander("⚙️ Configuration de recherche", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            token = st.text_input(
                "Token Meta API",
                type="password",
                value=os.getenv("META_ACCESS_TOKEN", ""),
                help="Votre token d'accès Meta Ads API"
            )

            keywords_input = st.text_area(
                "Mots-clés (un par ligne)",
                placeholder="dropshipping\necommerce\nboutique",
                height=100
            )
            keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

        with col2:
            countries = st.multiselect(
                "Pays cibles",
                options=list(AVAILABLE_COUNTRIES.keys()),
                default=DEFAULT_COUNTRIES,
                format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}"
            )

            languages = st.multiselect(
                "Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=DEFAULT_LANGUAGES,
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}"
            )

            min_ads = st.slider("Min. ads pour inclusion", 5, 50, MIN_ADS_INITIAL)

    # CMS Filter
    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
    selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=cms_options)

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", use_container_width=True):
        if not token:
            st.error("Token Meta API requis !")
            return
        if not keywords:
            st.error("Au moins un mot-clé requis !")
            return

        run_search_process(token, keywords, countries, languages, min_ads, selected_cms)


def run_search_process(token, keywords, countries, languages, min_ads, selected_cms):
    """Exécute le processus de recherche complet"""
    client = MetaAdsClient(token)

    # Phase 1: Recherche
    st.subheader("🔍 Phase 1: Recherche par mots-clés")
    all_ads = []
    seen_ad_ids = set()
    progress = st.progress(0)

    for i, kw in enumerate(keywords):
        st.text(f"Recherche: '{kw}'...")
        ads = client.search_ads(kw, countries, languages)
        for ad in ads:
            ad_id = ad.get("id")
            if ad_id and ad_id not in seen_ad_ids:
                ad["_keyword"] = kw
                all_ads.append(ad)
                seen_ad_ids.add(ad_id)
        progress.progress((i + 1) / len(keywords))

    st.success(f"✓ {len(all_ads)} annonces trouvées")

    # Phase 2: Regroupement
    st.subheader("📋 Phase 2: Regroupement par page")
    pages = {}
    page_ads = defaultdict(list)
    name_counter = defaultdict(Counter)

    for ad in all_ads:
        pid = ad.get("page_id")
        if not pid:
            continue
        pname = (ad.get("page_name") or "").strip()

        if pid not in pages:
            pages[pid] = {
                "page_id": pid, "page_name": pname, "website": "",
                "_ad_ids": set(), "ads_found_search": 0,
                "ads_active_total": -1, "currency": "",
                "cms": "Unknown", "is_shopify": False
            }

        ad_id = ad.get("id")
        if ad_id:
            pages[pid]["_ad_ids"].add(ad_id)
            page_ads[pid].append(ad)
        if pname:
            name_counter[pid][pname] += 1

    for pid, counter in name_counter.items():
        if counter and pid in pages:
            pages[pid]["page_name"] = counter.most_common(1)[0][0]

    for pid, data in pages.items():
        data["ads_found_search"] = len(data["_ad_ids"])

    pages_filtered = {pid: data for pid, data in pages.items() if data["ads_found_search"] >= min_ads}
    st.success(f"✓ {len(pages_filtered)} pages avec ≥{min_ads} ads")

    if not pages_filtered:
        st.warning("Aucune page trouvée avec assez d'ads")
        return

    # Phase 3: Extraction sites
    st.subheader("🌐 Phase 3: Extraction des sites web")
    progress = st.progress(0)
    for i, (pid, data) in enumerate(pages_filtered.items()):
        data["website"] = extract_website_from_ads(page_ads.get(pid, []))
        progress.progress((i + 1) / len(pages_filtered))

    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    st.success(f"✓ {sites_found} sites extraits")

    # Phase 4: Détection CMS
    st.subheader("🔍 Phase 4: Détection CMS")
    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_with_sites.items()):
        cms_result = detect_cms_from_url(data["website"])
        data["cms"] = cms_result["cms"]
        data["is_shopify"] = cms_result["is_shopify"]
        progress.progress((i + 1) / len(pages_with_sites))
        time.sleep(0.1)

    # Filter by CMS
    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in cms_options[:-1]:
            return True
        return False

    pages_with_cms = {pid: data for pid, data in pages_with_sites.items() if cms_matches(data.get("cms", "Unknown"))}
    st.success(f"✓ {len(pages_with_cms)} pages avec CMS sélectionnés")

    # Phase 5: Comptage
    st.subheader("📊 Phase 5: Comptage des annonces")
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_with_cms.items()):
        ads_complete, count = client.fetch_all_ads_for_page(pid, countries, languages)
        if count > 0:
            page_ads[pid] = ads_complete
            data["ads_active_total"] = count
            data["currency"] = extract_currency_from_ads(ads_complete)
        else:
            data["ads_active_total"] = data["ads_found_search"]
        progress.progress((i + 1) / len(pages_with_cms))
        time.sleep(0.1)

    pages_final = {pid: data for pid, data in pages_with_cms.items() if data["ads_active_total"] >= min_ads}
    st.success(f"✓ {len(pages_final)} pages finales")

    # Phase 6: Analyse web
    st.subheader("🔬 Phase 6: Analyse des sites web")
    web_results = {}
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_final.items()):
        if data["website"]:
            result = analyze_website_complete(data["website"], countries[0])
            web_results[pid] = result
            if not data["currency"] and result.get("currency_from_site"):
                data["currency"] = result["currency_from_site"]
        progress.progress((i + 1) / len(pages_final))
        time.sleep(0.2)

    # Phase 7: Sauvegarde BDD
    st.subheader("💾 Phase 7: Sauvegarde en base de données")
    db = get_database()

    if db:
        try:
            pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages)
            suivi_saved = save_suivi_page(db, pages_final, web_results, MIN_ADS_SUIVI)
            ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, MIN_ADS_LISTE)

            col1, col2, col3 = st.columns(3)
            col1.metric("Pages", pages_saved)
            col2.metric("Suivi", suivi_saved)
            col3.metric("Annonces", ads_saved)
            st.success("✓ Données sauvegardées !")
        except Exception as e:
            st.error(f"Erreur sauvegarde: {e}")

    # Save to session
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.countries = countries
    st.session_state.languages = languages

    st.balloons()
    st.success("🎉 Recherche terminée !")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: PAGES / SHOPS
# ═══════════════════════════════════════════════════════════════════════════════

def render_pages_shops():
    """Page Pages/Shops - Liste des pages"""
    st.title("🏪 Pages / Shops")
    st.markdown("Explorer toutes les pages et boutiques")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Filtres
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search_term = st.text_input("🔍 Rechercher", placeholder="Nom ou site...")

    with col2:
        cms_filter = st.selectbox("CMS", ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"])

    with col3:
        etat_filter = st.selectbox("État", ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"])

    with col4:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    # Recherche
    try:
        results = search_pages(
            db,
            cms=cms_filter if cms_filter != "Tous" else None,
            etat=etat_filter if etat_filter != "Tous" else None,
            search_term=search_term if search_term else None,
            limit=limit
        )

        if results:
            st.markdown(f"**{len(results)} résultats**")

            df = pd.DataFrame(results)

            # Colonnes à afficher
            display_cols = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active", "nombre_produits", "thematique"]
            df_display = df[[c for c in display_cols if c in df.columns]]

            # Renommer colonnes
            df_display.columns = ["Nom", "Site", "CMS", "État", "Ads", "Produits", "Thématique"][:len(df_display.columns)]

            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Site": st.column_config.LinkColumn("Site"),
                }
            )
        else:
            st.info("Aucun résultat trouvé")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: WATCHLISTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_watchlists():
    """Page Watchlists - Listes de surveillance"""
    st.title("📋 Watchlists")
    st.markdown("Gérer vos listes de surveillance")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Suivi des pages performantes
    st.subheader("🌟 Top Performers (≥80 ads)")
    try:
        top_pages = search_pages(db, etat="XXL", limit=20)
        top_pages.extend(search_pages(db, etat="XL", limit=20))

        if top_pages:
            df = pd.DataFrame(top_pages)
            cols = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active"]
            df_display = df[[c for c in cols if c in df.columns]].head(20)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune page XXL/XL trouvée")
    except Exception as e:
        st.error(f"Erreur: {e}")

    st.markdown("---")

    # Shopify uniquement
    st.subheader("🛒 Shopify Stores")
    try:
        shopify_pages = search_pages(db, cms="Shopify", limit=30)
        if shopify_pages:
            df = pd.DataFrame(shopify_pages)
            cols = ["page_name", "lien_site", "etat", "nombre_ads_active", "nombre_produits"]
            df_display = df[[c for c in cols if c in df.columns]]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune boutique Shopify trouvée")
    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_alerts():
    """Page Alerts - Alertes et notifications"""
    st.title("🔔 Alerts")
    st.markdown("Alertes et changements détectés")

    st.info("🚧 Fonctionnalité en cours de développement")
    st.markdown("""
    **Fonctionnalités à venir:**
    - Alertes sur nouveaux concurrents
    - Notification quand une page passe en XXL
    - Détection de pages devenues inactives
    - Alertes personnalisées par watchlist
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

def render_monitoring():
    """Page Monitoring - Suivi historique"""
    st.title("📈 Monitoring")
    st.markdown("Suivi de l'évolution des pages")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Recherche par page_id
    page_id = st.text_input("🔍 Entrer un Page ID pour voir l'historique")

    if page_id:
        try:
            history = get_suivi_history(db, page_id=page_id, limit=50)

            if history and len(history) > 0:
                st.subheader(f"Historique de {history[0].get('nom_site', page_id)}")

                # Graphique d'évolution
                if len(history) > 1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[h["date_scan"] for h in history],
                        y=[h["nombre_ads_active"] for h in history],
                        mode='lines+markers',
                        name='Ads actives',
                        line=dict(color='#1f77b4', width=2)
                    ))
                    fig.add_trace(go.Scatter(
                        x=[h["date_scan"] for h in history],
                        y=[h["nombre_produits"] for h in history],
                        mode='lines+markers',
                        name='Produits',
                        line=dict(color='#2ca02c', width=2)
                    ))
                    fig.update_layout(
                        title="Évolution dans le temps",
                        xaxis_title="Date",
                        yaxis_title="Nombre",
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, key="monitoring_chart", use_container_width=True)

                # Tableau historique
                df = pd.DataFrame(history)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun historique trouvé pour cette page")
        except Exception as e:
            st.error(f"Erreur: {e}")
    else:
        # Derniers scans
        st.subheader("📊 Derniers scans enregistrés")
        try:
            recent = get_suivi_history(db, limit=30)
            if recent:
                df = pd.DataFrame(recent)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun historique disponible")
        except Exception as e:
            st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def render_analytics():
    """Page Analytics - Analyses avancées"""
    st.title("📊 Analytics")
    st.markdown("Analyses et statistiques avancées")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    try:
        stats = get_suivi_stats(db)

        # Stats générales
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pages", stats.get("total_pages", 0))

        etats = stats.get("etats", {})
        actives = sum(v for k, v in etats.items() if k != "inactif")
        col2.metric("Pages Actives", actives)

        cms_stats = stats.get("cms", {})
        col3.metric("CMS Différents", len(cms_stats))

        st.markdown("---")

        # Graphiques côte à côte
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Distribution par État")
            if etats:
                fig = px.funnel(
                    x=list(etats.values()),
                    y=list(etats.keys()),
                    color=list(etats.keys())
                )
                st.plotly_chart(fig, key="analytics_funnel", use_container_width=True)

        with col2:
            st.subheader("Distribution par CMS")
            if cms_stats:
                fig = px.bar(
                    x=list(cms_stats.keys()),
                    y=list(cms_stats.values()),
                    color=list(cms_stats.keys())
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, key="analytics_cms", use_container_width=True)

        # Top thématiques
        st.markdown("---")
        st.subheader("🏷️ Analyse par thématique")

        all_pages = search_pages(db, limit=500)
        if all_pages:
            themes = {}
            for p in all_pages:
                theme = p.get("thematique", "Non classé") or "Non classé"
                themes[theme] = themes.get(theme, 0) + 1

            if themes:
                fig = px.treemap(
                    names=list(themes.keys()),
                    values=list(themes.values()),
                    parents=[""] * len(themes)
                )
                st.plotly_chart(fig, key="analytics_themes", use_container_width=True)

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

def render_settings():
    """Page Settings - Paramètres"""
    st.title("⚙️ Settings")
    st.markdown("Configuration de l'application")

    # API Settings
    st.subheader("🔑 API Configuration")

    token = st.text_input(
        "Meta API Token",
        type="password",
        value=os.getenv("META_ACCESS_TOKEN", ""),
        help="Token d'accès Meta Ads API"
    )

    if token:
        st.success("✓ Token configuré")
    else:
        st.warning("⚠️ Token non configuré")

    st.markdown("---")

    # Database info
    st.subheader("🗄️ Base de données")

    db = get_database()
    if db:
        st.success("✓ Connecté à PostgreSQL")
        st.code(DATABASE_URL.replace(DATABASE_URL.split("@")[0].split(":")[-1], "****"))

        try:
            stats = get_suivi_stats(db)
            col1, col2, col3 = st.columns(3)
            col1.metric("Pages en base", stats.get("total_pages", 0))
            col2.metric("États différents", len(stats.get("etats", {})))
            col3.metric("CMS différents", len(stats.get("cms", {})))
        except:
            pass
    else:
        st.error("✗ Non connecté")

    st.markdown("---")

    # Seuils
    st.subheader("📊 Seuils de détection")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"Min. ads pour suivi: **{MIN_ADS_SUIVI}**")
    with col2:
        st.info(f"Min. ads pour liste: **{MIN_ADS_LISTE}**")

    st.markdown("""
    **États basés sur le nombre d'ads:**
    - **XXL**: ≥150 ads
    - **XL**: 80-149 ads
    - **L**: 35-79 ads
    - **M**: 20-34 ads
    - **S**: 10-19 ads
    - **XS**: 1-9 ads
    - **Inactif**: 0 ads
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal"""
    st.set_page_config(
        page_title="Meta Ads Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_session_state()
    render_sidebar()

    # Router
    page = st.session_state.current_page

    if page == "Dashboard":
        render_dashboard()
    elif page == "Search Ads":
        render_search_ads()
    elif page == "Pages / Shops":
        render_pages_shops()
    elif page == "Watchlists":
        render_watchlists()
    elif page == "Alerts":
        render_alerts()
    elif page == "Monitoring":
        render_monitoring()
    elif page == "Analytics":
        render_analytics()
    elif page == "Settings":
        render_settings()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
