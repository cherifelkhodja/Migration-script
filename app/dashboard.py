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
    DATABASE_URL, MIN_ADS_SUIVI, MIN_ADS_LISTE,
    DEFAULT_STATE_THRESHOLDS
)
from app.meta_api import MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
from app.shopify_detector import detect_cms_from_url
from app.web_analyzer import analyze_website_complete
from app.utils import load_blacklist, is_blacklisted
from app.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, search_pages, get_suivi_history,
    get_evolution_stats, get_page_evolution_history, get_etat_from_ads_count,
    add_to_blacklist, remove_from_blacklist, get_blacklist, get_blacklist_ids
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
        'languages': ['fr'],
        'state_thresholds': DEFAULT_STATE_THRESHOLDS.copy()
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

    # Vérifier si on a des résultats en aperçu à afficher
    if st.session_state.get("show_preview_results", False):
        render_preview_results()
        return

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

            min_ads = st.slider("Min. ads pour inclusion", 1, 50, MIN_ADS_INITIAL)

    # CMS Filter
    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
    selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=cms_options)

    # Mode aperçu
    st.markdown("---")
    preview_mode = st.checkbox(
        "📋 Mode aperçu (ne pas enregistrer en BDD)",
        help="Permet de voir les résultats avant de les enregistrer, et de blacklister des pages"
    )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", use_container_width=True):
        if not token:
            st.error("Token Meta API requis !")
            return
        if not keywords:
            st.error("Au moins un mot-clé requis !")
            return

        run_search_process(token, keywords, countries, languages, min_ads, selected_cms, preview_mode)


def render_preview_results():
    """Affiche les résultats en mode aperçu"""
    st.subheader("📋 Aperçu des résultats")
    st.warning("⚠️ Mode aperçu activé - Les données ne sont pas encore enregistrées")

    db = get_database()
    pages_final = st.session_state.get("pages_final", {})
    web_results = st.session_state.get("web_results", {})
    countries = st.session_state.get("countries", ["FR"])

    if not pages_final:
        st.info("Aucun résultat à afficher")
        if st.button("🔙 Nouvelle recherche"):
            st.session_state.show_preview_results = False
            st.rerun()
        return

    st.info(f"📊 {len(pages_final)} pages trouvées")

    # Afficher les pages avec options
    for pid, data in list(pages_final.items()):
        web = web_results.get(pid, {})
        website = data.get('website', '')
        fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            st.write(f"**{data.get('page_name', 'N/A')}** - {data.get('ads_active_total', 0)} ads")
            st.caption(f"CMS: {data.get('cms', 'N/A')} | Produits: {web.get('product_count', 'N/A')}")

        with col2:
            if website:
                st.link_button("🌐 Site", website)
            else:
                st.caption("Pas de site")

        with col3:
            st.link_button("📘 Ads", fb_link)

        with col4:
            if st.button("🚫", key=f"bl_preview_{pid}", help="Blacklister"):
                if db and add_to_blacklist(db, pid, data.get("page_name", ""), "Blacklisté depuis aperçu"):
                    # Retirer de pages_final
                    del st.session_state.pages_final[pid]
                    if pid in st.session_state.web_results:
                        del st.session_state.web_results[pid]
                    st.rerun()

    st.markdown("---")

    # Boutons d'action
    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Sauvegarder en base de données", type="primary", use_container_width=True):
            if db:
                try:
                    thresholds = st.session_state.get("state_thresholds", None)
                    languages = st.session_state.get("languages", ["fr"])
                    pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                    suivi_saved = save_suivi_page(db, pages_final, web_results, MIN_ADS_SUIVI)
                    ads_saved = save_ads_recherche(db, pages_final, st.session_state.get("page_ads", {}), countries, MIN_ADS_LISTE)

                    st.success(f"✓ Sauvegardé : {pages_saved} pages, {suivi_saved} suivi, {ads_saved} ads")
                    st.session_state.show_preview_results = False
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur sauvegarde: {e}")

    with col2:
        if st.button("🔙 Nouvelle recherche", use_container_width=True):
            st.session_state.show_preview_results = False
            st.session_state.pages_final = {}
            st.session_state.web_results = {}
            st.rerun()


def run_search_process(token, keywords, countries, languages, min_ads, selected_cms, preview_mode=False):
    """Exécute le processus de recherche complet"""
    client = MetaAdsClient(token)
    db = get_database()

    # Récupérer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db)
        if blacklist_ids:
            st.info(f"🚫 {len(blacklist_ids)} pages en blacklist seront ignorées")

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

        # Ignorer les pages blacklistées
        if str(pid) in blacklist_ids:
            continue

        pname = (ad.get("page_name") or "").strip()

        if pid not in pages:
            pages[pid] = {
                "page_id": pid, "page_name": pname, "website": "",
                "_ad_ids": set(), "_keywords": set(), "ads_found_search": 0,
                "ads_active_total": -1, "currency": "",
                "cms": "Unknown", "is_shopify": False
            }

        # Track which keyword found this page
        if ad.get("_keyword"):
            pages[pid]["_keywords"].add(ad["_keyword"])

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

    # Save to session first (needed for preview mode)
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.preview_mode = preview_mode

    if preview_mode:
        # Mode aperçu - rediriger vers la page d'aperçu
        st.success(f"✓ Recherche terminée ! {len(pages_final)} pages trouvées")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        # Mode normal - sauvegarder directement
        st.subheader("💾 Phase 7: Sauvegarde en base de données")

        if db:
            try:
                thresholds = st.session_state.get("state_thresholds", None)
                pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                suivi_saved = save_suivi_page(db, pages_final, web_results, MIN_ADS_SUIVI)
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, MIN_ADS_LISTE)

                col1, col2, col3 = st.columns(3)
                col1.metric("Pages", pages_saved)
                col2.metric("Suivi", suivi_saved)
                col3.metric("Annonces", ads_saved)
                st.success("✓ Données sauvegardées !")
            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")

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

    # Mode d'affichage
    view_mode = st.radio("Mode d'affichage", ["Tableau", "Détaillé"], horizontal=True)

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

            if view_mode == "Tableau":
                df = pd.DataFrame(results)

                # Colonnes à afficher
                display_cols = ["page_name", "lien_site", "keywords", "cms", "etat", "nombre_ads_active", "nombre_produits"]
                df_display = df[[c for c in display_cols if c in df.columns]]

                # Renommer colonnes
                df_display.columns = ["Nom", "Site", "Keywords", "CMS", "État", "Ads", "Produits"][:len(df_display.columns)]

                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Site": st.column_config.LinkColumn("Site"),
                    }
                )
            else:
                # Vue détaillée avec boutons blacklist
                for page in results:
                    with st.expander(f"**{page.get('page_name', 'N/A')}** - {page.get('etat', 'N/A')} ({page.get('nombre_ads_active', 0)} ads)"):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                            st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")
                            if page.get('keywords'):
                                st.write(f"**Keywords:** {page.get('keywords', '')}")
                            if page.get('thematique'):
                                st.write(f"**Thématique:** {page.get('thematique', '')}")

                        with col2:
                            pid = page.get('page_id')
                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                            if st.button("🚫 Blacklist", key=f"bl_page_{pid}"):
                                if add_to_blacklist(db, pid, page.get('page_name', ''), "Blacklisté depuis Pages/Shops"):
                                    st.success(f"✓ Blacklisté")
                                    st.rerun()
                                else:
                                    st.warning("Déjà blacklisté")
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
    """Page Monitoring - Suivi historique et évolution"""
    st.title("📈 Monitoring")
    st.markdown("Suivi de l'évolution des pages depuis le dernier scan")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Sélecteur de période
    col1, col2 = st.columns([1, 3])
    with col1:
        period = st.selectbox(
            "📅 Période",
            options=[7, 14, 30],
            format_func=lambda x: f"1 semaine" if x == 7 else f"2 semaines" if x == 14 else "1 mois",
            index=0
        )

    # Section évolution
    st.subheader("📊 Évolution depuis le dernier scan")

    try:
        evolution = get_evolution_stats(db, period_days=period)

        if evolution:
            st.info(f"📈 {len(evolution)} pages avec évolution sur les {period} derniers jours")

            # Métriques globales
            total_up = sum(1 for e in evolution if e["delta_ads"] > 0)
            total_down = sum(1 for e in evolution if e["delta_ads"] < 0)
            total_stable = sum(1 for e in evolution if e["delta_ads"] == 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("📈 En hausse", total_up)
            col2.metric("📉 En baisse", total_down)
            col3.metric("➡️ Stable", total_stable)

            # Tableau d'évolution
            st.markdown("---")

            for evo in evolution[:20]:  # Top 20
                delta_color = "green" if evo["delta_ads"] > 0 else "red" if evo["delta_ads"] < 0 else "gray"
                delta_icon = "📈" if evo["delta_ads"] > 0 else "📉" if evo["delta_ads"] < 0 else "➡️"

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
                        st.metric("Durée entre scans", f"{evo['duree_jours']:.1f} jours")

                    # Dates des scans
                    st.caption(f"🕐 Scan actuel: {evo['date_actuel'].strftime('%Y-%m-%d %H:%M') if evo['date_actuel'] else 'N/A'}")
                    st.caption(f"🕐 Scan précédent: {evo['date_precedent'].strftime('%Y-%m-%d %H:%M') if evo['date_precedent'] else 'N/A'}")

                    # Bouton pour voir l'historique complet
                    if st.button(f"Voir historique complet", key=f"hist_{evo['page_id']}"):
                        st.session_state.monitoring_page_id = evo["page_id"]
                        st.rerun()
        else:
            st.info("Aucune évolution détectée. Effectuez plusieurs scans pour voir les changements.")
    except Exception as e:
        st.error(f"Erreur: {e}")

    st.markdown("---")

    # Section historique d'une page spécifique
    st.subheader("🔍 Historique d'une page")

    # Récupérer page_id depuis session ou input
    default_page_id = st.session_state.get("monitoring_page_id", "")
    page_id = st.text_input("Entrer un Page ID", value=default_page_id)

    if page_id:
        try:
            history = get_page_evolution_history(db, page_id=page_id, limit=50)

            if history and len(history) > 0:
                st.success(f"📊 {len(history)} scans trouvés")

                # Graphique d'évolution
                if len(history) > 1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[h["date_scan"] for h in history],
                        y=[h["nombre_ads_active"] for h in history],
                        mode='lines+markers',
                        name='Ads actives',
                        line=dict(color='#1f77b4', width=2),
                        hovertemplate="Ads: %{y}<br>Delta: %{customdata}<extra></extra>",
                        customdata=[h["delta_ads"] for h in history]
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
                    st.plotly_chart(fig, key="monitoring_page_chart", use_container_width=True)

                # Tableau avec deltas
                df_data = []
                for h in history:
                    delta_ads_str = f"{h['delta_ads']:+d}" if h["delta_ads"] != 0 else "-"
                    delta_prod_str = f"{h['delta_produits']:+d}" if h["delta_produits"] != 0 else "-"
                    df_data.append({
                        "Date": h["date_scan"].strftime("%Y-%m-%d %H:%M") if h["date_scan"] else "",
                        "Ads": h["nombre_ads_active"],
                        "Δ Ads": delta_ads_str,
                        "Produits": h["nombre_produits"],
                        "Δ Produits": delta_prod_str
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun historique trouvé pour cette page")
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

    # Seuils de base
    st.subheader("📊 Seuils de détection")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"Min. ads pour suivi: **{MIN_ADS_SUIVI}**")
    with col2:
        st.info(f"Min. ads pour liste: **{MIN_ADS_LISTE}**")

    st.markdown("---")

    # Configuration des états
    st.subheader("🏷️ Configuration des états")
    st.markdown("Définissez les seuils minimums d'ads actives pour chaque état:")

    # Récupérer les seuils actuels
    thresholds = st.session_state.state_thresholds

    col1, col2, col3 = st.columns(3)

    with col1:
        new_xs = st.number_input(
            "XS (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XS", 1),
            help="Seuil minimum pour l'état XS"
        )
        new_m = st.number_input(
            "M (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("M", 20),
            help="Seuil minimum pour l'état M"
        )

    with col2:
        new_s = st.number_input(
            "S (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("S", 10),
            help="Seuil minimum pour l'état S"
        )
        new_l = st.number_input(
            "L (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("L", 35),
            help="Seuil minimum pour l'état L"
        )

    with col3:
        new_xl = st.number_input(
            "XL (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XL", 80),
            help="Seuil minimum pour l'état XL"
        )
        new_xxl = st.number_input(
            "XXL (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XXL", 150),
            help="Seuil minimum pour l'état XXL"
        )

    # Bouton pour sauvegarder
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 Sauvegarder", type="primary"):
            # Vérifier la cohérence des seuils
            new_thresholds = {
                "XS": new_xs,
                "S": new_s,
                "M": new_m,
                "L": new_l,
                "XL": new_xl,
                "XXL": new_xxl
            }

            # Vérifier que les seuils sont croissants
            if new_xs < new_s < new_m < new_l < new_xl < new_xxl:
                st.session_state.state_thresholds = new_thresholds
                st.success("✓ Seuils sauvegardés !")
            else:
                st.error("Les seuils doivent être strictement croissants (XS < S < M < L < XL < XXL)")

    with col2:
        if st.button("🔄 Réinitialiser"):
            st.session_state.state_thresholds = DEFAULT_STATE_THRESHOLDS.copy()
            st.rerun()

    # Afficher un aperçu des états
    st.markdown("---")
    st.markdown("**Aperçu des états actuels:**")

    current = st.session_state.state_thresholds
    preview_data = [
        {"État": "Inactif", "Plage": "0 ads"},
        {"État": "XS", "Plage": f"{current['XS']}-{current['S']-1} ads"},
        {"État": "S", "Plage": f"{current['S']}-{current['M']-1} ads"},
        {"État": "M", "Plage": f"{current['M']}-{current['L']-1} ads"},
        {"État": "L", "Plage": f"{current['L']}-{current['XL']-1} ads"},
        {"État": "XL", "Plage": f"{current['XL']}-{current['XXL']-1} ads"},
        {"État": "XXL", "Plage": f"≥{current['XXL']} ads"},
    ]
    st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

    # ─────────────────────────────────────────────────────────────────────────────
    # Gestion de la blacklist
    st.markdown("---")
    st.subheader("🚫 Gestion de la Blacklist")

    # Ajouter manuellement une page à la blacklist
    with st.expander("➕ Ajouter une page à la blacklist"):
        col1, col2 = st.columns(2)
        with col1:
            new_bl_page_id = st.text_input("Page ID", key="new_bl_page_id")
        with col2:
            new_bl_page_name = st.text_input("Nom de la page (optionnel)", key="new_bl_page_name")

        new_bl_raison = st.text_input("Raison (optionnel)", key="new_bl_raison")

        if st.button("➕ Ajouter à la blacklist"):
            if new_bl_page_id:
                if add_to_blacklist(db, new_bl_page_id, new_bl_page_name, new_bl_raison):
                    st.success(f"✓ Page {new_bl_page_id} ajoutée à la blacklist")
                    st.rerun()
                else:
                    st.warning("Cette page est déjà dans la blacklist")
            else:
                st.error("Page ID requis")

    # Afficher la blacklist
    st.markdown("**Pages en blacklist:**")
    try:
        blacklist = get_blacklist(db)

        if blacklist:
            st.info(f"🚫 {len(blacklist)} pages en blacklist")

            for entry in blacklist:
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.write(f"**{entry.get('page_name') or entry['page_id']}**")
                    st.caption(f"ID: {entry['page_id']}")

                with col2:
                    if entry.get('raison'):
                        st.caption(f"Raison: {entry['raison']}")
                    if entry.get('added_at'):
                        st.caption(f"Ajouté: {entry['added_at'].strftime('%Y-%m-%d %H:%M')}")

                with col3:
                    if st.button("🗑️ Retirer", key=f"rm_bl_{entry['page_id']}"):
                        if remove_from_blacklist(db, entry['page_id']):
                            st.success("✓ Retiré")
                            st.rerun()
        else:
            st.info("Aucune page en blacklist")

    except Exception as e:
        st.error(f"Erreur: {e}")


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
