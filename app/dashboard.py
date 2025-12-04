"""
Dashboard Streamlit pour Meta Ads Shopify Analyzer
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
    MIN_ADS_INITIAL, MIN_ADS_FOR_EXPORT, MIN_ADS_FOR_ADS_CSV,
    DEFAULT_COUNTRIES, DEFAULT_LANGUAGES,
    DATABASE_URL, MIN_ADS_SUIVI, MIN_ADS_LISTE
)
from app.meta_api import MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
from app.shopify_detector import detect_cms_from_url
from app.web_analyzer import analyze_website_complete
from app.utils import (
    load_blacklist, is_blacklisted, create_dataframe_pages,
    export_pages_csv, export_ads_csv
)
from app.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, search_pages, get_suivi_history
)


def init_session_state():
    """Initialise le state de la session Streamlit"""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'pages_final' not in st.session_state:
        st.session_state.pages_final = {}
    if 'web_results' not in st.session_state:
        st.session_state.web_results = {}
    if 'page_ads' not in st.session_state:
        st.session_state.page_ads = {}
    if 'search_running' not in st.session_state:
        st.session_state.search_running = False
    if 'stats' not in st.session_state:
        st.session_state.stats = {}
    if 'db' not in st.session_state:
        st.session_state.db = None


def get_database() -> DatabaseManager:
    """Récupère ou initialise la connexion à la base de données"""
    if st.session_state.db is None:
        try:
            st.session_state.db = DatabaseManager(DATABASE_URL)
            st.session_state.db.create_tables()
        except Exception as e:
            st.warning(f"Base de données non disponible: {e}")
            return None
    return st.session_state.db


def render_header():
    """Affiche l'en-tête de l'application"""
    st.set_page_config(
        page_title="Meta Ads Shopify Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 Meta Ads Shopify Analyzer")
    st.markdown("""
    Recherche et analyse des annonces Meta pour sites **Shopify**.
    Détection automatique, comptage des produits et export CSV.
    """)
    st.divider()


def render_sidebar():
    """Affiche la sidebar avec la configuration"""
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Token API
        token = st.text_input(
            "Token Meta API",
            type="password",
            value=os.getenv("META_ACCESS_TOKEN", ""),
            help="Votre token d'accès Meta Ads API"
        )

        st.divider()

        # Mots-clés
        keywords_input = st.text_area(
            "Mots-clés (un par ligne)",
            placeholder="dropshipping\necommerce\nboutique",
            height=100
        )
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

        st.divider()

        # Pays
        countries = st.multiselect(
            "Pays cibles",
            options=list(AVAILABLE_COUNTRIES.keys()),
            default=DEFAULT_COUNTRIES,
            format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}"
        )

        # Langues
        languages = st.multiselect(
            "Langues",
            options=list(AVAILABLE_LANGUAGES.keys()),
            default=DEFAULT_LANGUAGES,
            format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}"
        )

        st.divider()

        # Seuils
        st.subheader("Seuils de filtrage")
        min_ads_initial = st.number_input(
            "Min. ads (recherche)",
            min_value=1, max_value=50, value=MIN_ADS_INITIAL,
            help="Nombre minimum d'ads pour garder une page"
        )
        min_ads_export = st.number_input(
            "Min. ads (export)",
            min_value=1, max_value=100, value=MIN_ADS_FOR_EXPORT,
            help="Nombre minimum d'ads pour l'export CSV"
        )

        st.divider()

        # Sélection des CMS
        st.subheader("CMS à inclure")
        cms_options = [
            "Shopify", "WooCommerce", "PrestaShop", "Magento",
            "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"
        ]
        selected_cms = st.multiselect(
            "CMS à comptabiliser",
            options=cms_options,
            default=cms_options,  # Tous par défaut
            help="Sélectionnez les CMS à inclure dans les résultats"
        )

        st.divider()

        # Blacklist
        blacklist_file = st.file_uploader(
            "Fichier blacklist (CSV)",
            type=['csv'],
            help="Fichier CSV avec colonnes page_id et/ou page_name"
        )

        return {
            'token': token,
            'keywords': keywords,
            'countries': countries,
            'languages': languages,
            'min_ads_initial': min_ads_initial,
            'min_ads_export': min_ads_export,
            'blacklist_file': blacklist_file,
            'selected_cms': selected_cms
        }


def run_search(config: dict):
    """Exécute la recherche complète"""
    token = config['token']
    keywords = config['keywords']
    countries = config['countries']
    languages = config['languages']
    min_ads_initial = config['min_ads_initial']
    min_ads_export = config['min_ads_export']
    selected_cms = config.get('selected_cms', [])

    if not token:
        st.error("Token Meta API requis !")
        return

    if not keywords:
        st.error("Au moins un mot-clé requis !")
        return

    # Charger blacklist
    blacklist_ids, blacklist_names = set(), set()
    if config['blacklist_file']:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            tmp.write(config['blacklist_file'].getvalue())
            blacklist_ids, blacklist_names = load_blacklist(tmp.name)
            os.unlink(tmp.name)

    client = MetaAdsClient(token)

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: RECHERCHE PAR MOTS-CLÉS
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("🔍 Phase 1: Recherche par mots-clés")

    all_ads = []
    seen_ad_ids = set()

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, kw in enumerate(keywords):
        status_text.text(f"Recherche: '{kw}'...")
        ads = client.search_ads(kw, countries, languages)

        unique_ads = []
        for ad in ads:
            ad_id = ad.get("id")
            if ad_id and ad_id not in seen_ad_ids:
                ad["_keyword"] = kw
                unique_ads.append(ad)
                seen_ad_ids.add(ad_id)
            elif not ad_id:
                ad["_keyword"] = kw
                unique_ads.append(ad)

        all_ads.extend(unique_ads)
        progress_bar.progress((i + 1) / len(keywords))
        st.info(f"'{kw}': {len(ads)} trouvées, {len(unique_ads)} uniques")

    status_text.text(f"Total: {len(all_ads)} annonces uniques")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: REGROUPEMENT PAR PAGE
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📋 Phase 2: Regroupement par page")

    pages = {}
    name_counter = defaultdict(Counter)
    page_ads = defaultdict(list)

    for ad in all_ads:
        pid = ad.get("page_id")
        if not pid:
            continue

        pname = (ad.get("page_name") or "").strip()

        if is_blacklisted(pid, pname, blacklist_ids, blacklist_names):
            continue

        if pid not in pages:
            pages[pid] = {
                "page_id": pid,
                "page_name": pname,
                "website": "",
                "_ad_ids": set(),
                "keywords_matched": set(),
                "ads_found_search": 0,
                "ads_active_total": -1,
                "currency": "",
                "cms": "Unknown",
                "is_shopify": False,
                "cms_confidence": 0
            }

        ad_id = ad.get("id")
        if ad_id:
            pages[pid]["_ad_ids"].add(ad_id)
            page_ads[pid].append(ad)

        if pname:
            name_counter[pid][pname] += 1

        kw = ad.get("_keyword", "")
        if kw:
            pages[pid]["keywords_matched"].add(kw)

    for pid, counter in name_counter.items():
        if counter and pid in pages:
            pages[pid]["page_name"] = counter.most_common(1)[0][0]

    for pid, data in pages.items():
        data["ads_found_search"] = len(data["_ad_ids"])

    # Filtre préliminaire
    pages_filtered = {
        pid: data for pid, data in pages.items()
        if data["ads_found_search"] >= min_ads_initial
    }

    col1, col2 = st.columns(2)
    col1.metric("Pages uniques", len(pages))
    col2.metric(f"Pages ≥{min_ads_initial} ads", len(pages_filtered))

    if not pages_filtered:
        st.warning(f"Aucune page avec ≥{min_ads_initial} ads trouvée.")
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: EXTRACTION WEBSITES
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("🌐 Phase 3: Extraction des sites web")

    progress_bar = st.progress(0)
    for i, (pid, data) in enumerate(pages_filtered.items()):
        ads = page_ads.get(pid, [])
        website = extract_website_from_ads(ads)
        data["website"] = website
        progress_bar.progress((i + 1) / len(pages_filtered))

    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    st.success(f"Sites trouvés: {sites_found}/{len(pages_filtered)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 4: DÉTECTION CMS
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("🔍 Phase 4: Détection CMS")

    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}
    progress_bar = st.progress(0)
    status_text = st.empty()

    cms_counts = defaultdict(int)
    for i, (pid, data) in enumerate(pages_with_sites.items()):
        status_text.text(f"Détection CMS: {data['page_name'][:40]}...")

        cms_result = detect_cms_from_url(data["website"])
        data["cms"] = cms_result["cms"]
        data["is_shopify"] = cms_result["is_shopify"]
        data["cms_confidence"] = cms_result["confidence"]

        cms_counts[cms_result["cms"]] += 1

        progress_bar.progress((i + 1) / len(pages_with_sites))
        time.sleep(0.15)

    status_text.empty()

    # Afficher les stats CMS
    col1, col2, col3 = st.columns(3)
    col1.metric("Shopify", cms_counts.get("Shopify", 0))
    col2.metric("WooCommerce", cms_counts.get("WooCommerce", 0))
    col3.metric("Autres CMS", sum(v for k, v in cms_counts.items() if k not in ["Shopify", "WooCommerce", "Unknown"]))

    # Résumé des CMS détectés
    cms_summary = ", ".join([f"{k}: {v}" for k, v in sorted(cms_counts.items(), key=lambda x: -x[1]) if v > 0])
    st.info(f"CMS détectés: {cms_summary}")

    # Filtrer par CMS sélectionnés
    def cms_matches_selection(cms_name: str) -> bool:
        """Vérifie si le CMS correspond à la sélection"""
        if not selected_cms:
            return True  # Aucune sélection = tout garder
        if cms_name in selected_cms:
            return True
        # "Autre/Inconnu" pour les CMS non reconnus
        if "Autre/Inconnu" in selected_cms and cms_name not in [
            "Shopify", "WooCommerce", "PrestaShop", "Magento",
            "Wix", "Squarespace", "BigCommerce", "Webflow"
        ]:
            return True
        return False

    pages_with_cms = {
        pid: data for pid, data in pages_with_sites.items()
        if cms_matches_selection(data.get("cms", "Unknown"))
    }

    st.success(f"Pages avec CMS sélectionnés: {len(pages_with_cms)}/{len(pages_with_sites)}")

    if not pages_with_cms:
        st.warning("Aucun site trouvé.")
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 5: COMPTAGE COMPLET
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📊 Phase 5: Comptage des annonces")

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (pid, data) in enumerate(pages_with_cms.items()):
        status_text.text(f"Comptage: {data['page_name'][:40]}...")

        ads_complete, count = client.fetch_all_ads_for_page(pid, countries, languages)

        if count > 0:
            page_ads[pid] = ads_complete
            data["ads_active_total"] = count
            currency = extract_currency_from_ads(ads_complete)
            data["currency"] = currency
        else:
            data["ads_active_total"] = data["ads_found_search"]

        progress_bar.progress((i + 1) / len(pages_with_cms))
        time.sleep(0.15)

    status_text.empty()

    # Filtre final
    pages_final = {
        pid: data for pid, data in pages_with_cms.items()
        if data["ads_active_total"] >= min_ads_export
    }

    st.success(f"Pages ≥{min_ads_export} ads: {len(pages_final)}")

    if not pages_final:
        st.warning(f"Aucune page avec ≥{min_ads_export} ads.")
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 6: ANALYSE WEB
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("🔬 Phase 6: Analyse des sites web")

    web_results = {}
    progress_bar = st.progress(0)
    status_text = st.empty()

    sites_to_analyze = [(pid, data) for pid, data in pages_final.items() if data["website"]]

    for i, (pid, data) in enumerate(sites_to_analyze):
        status_text.text(f"Analyse: {data['website'][:50]}...")

        result = analyze_website_complete(data["website"], countries[0])
        web_results[pid] = result

        # Si devise pas trouvée dans ads, prendre celle du site
        if not pages_final[pid]["currency"] and result.get("currency_from_site"):
            pages_final[pid]["currency"] = result["currency_from_site"]

        progress_bar.progress((i + 1) / len(sites_to_analyze))
        time.sleep(0.3)

    status_text.empty()

    # Compter les CMS dans les résultats finaux
    final_cms_counts = defaultdict(int)
    for data in pages_final.values():
        final_cms_counts[data.get("cms", "Unknown")] += 1

    # Sauvegarder dans session state
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.stats = {
        'total_ads': len(all_ads),
        'total_pages': len(pages),
        'pages_filtered': len(pages_filtered),
        'pages_with_cms': len(pages_with_cms),
        'pages_final': len(pages_final),
        'total_products': sum(r.get("product_count", 0) for r in web_results.values()),
        'cms_counts': dict(final_cms_counts)
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 7: SAUVEGARDE EN BASE DE DONNÉES
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("💾 Phase 7: Sauvegarde en base de données")

    db = get_database()
    if db:
        try:
            with st.spinner("Sauvegarde des pages..."):
                pages_saved = save_pages_recherche(
                    db, pages_final, web_results, countries, languages
                )

            with st.spinner("Sauvegarde du suivi..."):
                suivi_saved = save_suivi_page(
                    db, pages_final, web_results, MIN_ADS_SUIVI
                )

            with st.spinner("Sauvegarde des annonces..."):
                ads_saved = save_ads_recherche(
                    db, pages_final, dict(page_ads), countries, MIN_ADS_LISTE
                )

            col1, col2, col3 = st.columns(3)
            col1.metric("Pages sauvées", pages_saved)
            col2.metric("Entrées suivi", suivi_saved)
            col3.metric("Annonces sauvées", ads_saved)

            st.success("Données sauvegardées en base !")
        except Exception as e:
            st.error(f"Erreur lors de la sauvegarde: {e}")
    else:
        st.warning("Base de données non disponible - données non sauvegardées")

    st.success("Analyse terminée !")


def render_results():
    """Affiche les résultats de la recherche"""
    if not st.session_state.pages_final:
        st.info("Lancez une recherche pour voir les résultats.")
        return

    pages_final = st.session_state.pages_final
    web_results = st.session_state.web_results
    stats = st.session_state.stats
    countries = st.session_state.get('countries', ['FR'])
    languages = st.session_state.get('languages', ['fr'])

    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTIQUES
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📈 Statistiques")

    cms_counts = stats.get('cms_counts', {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Annonces", stats.get('total_ads', 0))
    col2.metric("Pages Analysées", stats.get('pages_final', 0))
    col3.metric("Total Produits", stats.get('total_products', 0))
    col4.metric("Shopify", cms_counts.get('Shopify', 0))

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # TABLEAU DES RÉSULTATS
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📋 Résultats détaillés")

    df = create_dataframe_pages(pages_final, web_results, countries)

    # Graphiques
    col1, col2, col3 = st.columns(3)

    with col1:
        if not df.empty and 'CMS' in df.columns:
            cms_data = df['CMS'].value_counts()
            if not cms_data.empty:
                fig = px.pie(
                    values=cms_data.values,
                    names=cms_data.index,
                    title="Répartition par CMS"
                )
                st.plotly_chart(fig, width="stretch")

    with col2:
        if not df.empty and 'Thématique' in df.columns:
            theme_counts = df['Thématique'].value_counts()
            if not theme_counts.empty and theme_counts.iloc[0] > 0:
                fig = px.pie(
                    values=theme_counts.values,
                    names=theme_counts.index,
                    title="Répartition par thématique"
                )
                st.plotly_chart(fig, width="stretch")

    with col3:
        if not df.empty and 'Ads Actives' in df.columns:
            fig = px.histogram(
                df,
                x='Ads Actives',
                nbins=20,
                title="Distribution du nombre d'ads"
            )
            st.plotly_chart(fig, width="stretch")

    # Tableau
    st.dataframe(
        df,
        width="stretch",
        height=400,
        column_config={
            "Site Web": st.column_config.LinkColumn("Site Web"),
            "Ads Actives": st.column_config.NumberColumn("Ads"),
            "Produits": st.column_config.NumberColumn("Produits"),
        }
    )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORT CSV
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("💾 Export CSV")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Pages**: {len(pages_final)} pages à exporter")
        if st.button("📥 Exporter Pages", width="stretch"):
            path = export_pages_csv(
                pages_final, web_results,
                countries, languages
            )
            st.success(f"Exporté: {path}")

    with col2:
        pages_for_ads = {
            pid: data for pid, data in pages_final.items()
            if data.get("ads_active_total", 0) >= MIN_ADS_FOR_ADS_CSV
        }
        page_ads = st.session_state.page_ads
        total_ads = sum(len(page_ads.get(pid, [])) for pid in pages_for_ads.keys())
        st.write(f"**Annonces**: {len(pages_for_ads)} pages, ~{total_ads} annonces")
        if st.button("📥 Exporter Annonces", width="stretch"):
            path, count = export_ads_csv(
                pages_for_ads, page_ads,
                countries
            )
            st.success(f"Exporté: {path} ({count} annonces)")

    # Téléchargement direct
    st.divider()
    st.subheader("Téléchargement direct")

    csv_data = df.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        label="📥 Télécharger le tableau (CSV)",
        data=csv_data,
        file_name=f"meta_ads_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        width="stretch"
    )


def render_history():
    """Affiche l'historique des données en base"""
    db = get_database()

    if not db:
        st.warning("Base de données non disponible")
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTIQUES GLOBALES
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📈 Statistiques globales")

    try:
        stats = get_suivi_stats(db)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pages en base", stats.get("total_pages", 0))

        # Répartition par état
        etats = stats.get("etats", {})
        actives = sum(v for k, v in etats.items() if k != "inactif")
        col2.metric("Pages actives", actives)
        col3.metric("Pages inactives", etats.get("inactif", 0))

        # Graphiques
        col1, col2 = st.columns(2)

        with col1:
            if etats:
                # Ordre des états
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = {k: etats.get(k, 0) for k in ordre_etats if etats.get(k, 0) > 0}
                if etats_ordonne:
                    fig = px.bar(
                        x=list(etats_ordonne.keys()),
                        y=list(etats_ordonne.values()),
                        title="Répartition par état",
                        labels={"x": "État", "y": "Nombre de pages"}
                    )
                    st.plotly_chart(fig, use_container_width=True)

        with col2:
            cms_stats = stats.get("cms", {})
            if cms_stats:
                fig = px.pie(
                    values=list(cms_stats.values()),
                    names=list(cms_stats.keys()),
                    title="Répartition par CMS"
                )
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erreur lors de la récupération des stats: {e}")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # RECHERCHE ET FILTRES
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("🔍 Recherche dans la base")

    col1, col2, col3 = st.columns(3)

    with col1:
        search_term = st.text_input("Rechercher (nom ou site)", "")

    with col2:
        cms_filter = st.selectbox(
            "Filtrer par CMS",
            ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"]
        )

    with col3:
        etat_filter = st.selectbox(
            "Filtrer par état",
            ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"]
        )

    if st.button("🔍 Rechercher", width="stretch"):
        try:
            results = search_pages(
                db,
                cms=cms_filter if cms_filter != "Tous" else None,
                etat=etat_filter if etat_filter != "Tous" else None,
                search_term=search_term if search_term else None,
                limit=200
            )

            if results:
                df = pd.DataFrame(results)
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=400,
                    column_config={
                        "lien_site": st.column_config.LinkColumn("Site"),
                        "lien_fb_ad_library": st.column_config.LinkColumn("FB Ads"),
                    }
                )
                st.info(f"{len(results)} résultats trouvés")
            else:
                st.info("Aucun résultat trouvé")
        except Exception as e:
            st.error(f"Erreur lors de la recherche: {e}")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORIQUE DE SUIVI
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("📊 Historique de suivi")

    page_id_filter = st.text_input("Page ID (optionnel)", "")

    if st.button("📊 Voir l'historique", width="stretch"):
        try:
            history = get_suivi_history(
                db,
                page_id=page_id_filter if page_id_filter else None,
                limit=100
            )

            if history:
                df = pd.DataFrame(history)

                # Si on filtre par page_id, afficher un graphique d'évolution
                if page_id_filter and len(history) > 1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[h["date_scan"] for h in history],
                        y=[h["nombre_ads_active"] for h in history],
                        mode='lines+markers',
                        name='Ads actives'
                    ))
                    fig.add_trace(go.Scatter(
                        x=[h["date_scan"] for h in history],
                        y=[h["nombre_produits"] for h in history],
                        mode='lines+markers',
                        name='Produits'
                    ))
                    fig.update_layout(
                        title=f"Évolution de la page {page_id_filter}",
                        xaxis_title="Date",
                        yaxis_title="Nombre"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                st.dataframe(df, use_container_width=True, height=300)
                st.info(f"{len(history)} entrées d'historique")
            else:
                st.info("Aucun historique trouvé")
        except Exception as e:
            st.error(f"Erreur lors de la récupération de l'historique: {e}")


def main():
    """Point d'entrée principal du dashboard"""
    init_session_state()
    render_header()
    config = render_sidebar()

    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["🔍 Recherche", "📊 Résultats", "📚 Historique"])

    with tab1:
        st.header("Lancer une recherche")

        if config['keywords']:
            st.info(f"Mots-clés: {', '.join(config['keywords'])}")
            st.info(f"Pays: {', '.join(config['countries'])} | Langues: {', '.join(config['languages'])}")

        if st.button("🚀 Lancer la recherche", type="primary", width="stretch"):
            run_search(config)

    with tab2:
        render_results()

    with tab3:
        render_history()


if __name__ == "__main__":
    main()
