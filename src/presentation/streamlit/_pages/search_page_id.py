"""
Module de recherche par Page IDs.

Ce module gere la recherche d'annonces Meta via Page IDs Facebook.
Il permet une recherche directe sans passer par les mots-cles.

Fonctions:
----------
- render_page_id_search: Interface utilisateur de recherche par IDs
- run_page_id_search: Pipeline de recherche par batch de 10 IDs
"""
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
import json

import streamlit as st

from src.presentation.streamlit.shared import get_database

# Design System imports
from src.presentation.streamlit.ui import (
    section_header,
    loading_spinner,
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext
from src.infrastructure.persistence.database import (
    get_blacklist_ids,
    save_pages_recherche, save_suivi_page, save_ads_recherche, save_winning_ads,
)
from src.infrastructure.external_services.meta_api import MetaAdsClient
from src.infrastructure.scrapers.web_analyzer import (
    detect_cms_from_url, extract_website_from_ads, extract_currency_from_ads
)
# MarketSpy V2 - Optimized analyzers
from src.infrastructure.scrapers.market_spy import (
    analyze_homepage_v2, analyze_sitemap_v2
)
from src.infrastructure.scrapers.gemini_batch_classifier import (
    classify_pages_batch_v2
)
from src.infrastructure.persistence.database import is_winning_ad, get_etat_from_ads_count
from src.infrastructure.config import (
    AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES,
    DEFAULT_COUNTRIES,
    WINNING_AD_CRITERIA, MIN_ADS_SUIVI, MIN_ADS_LISTE,
    META_DELAY_BETWEEN_BATCHES, WEB_DELAY_CMS_CHECK
)


def render_page_id_search():
    """
    Interface de recherche par Page IDs (optimisee par batch de 10).

    Affiche le formulaire de recherche avec:
    - Champ Page IDs (un par ligne)
    - Selection pays
    - Options avancees (langues, CMS)
    - Mode apercu
    """

    # ═══ CHAMPS ESSENTIELS ═══
    section_header("Recherche par Page IDs", icon="🆔")

    col1, col2 = st.columns([2, 1])

    with col1:
        page_ids_input = st.text_area(
            "Page IDs (un par ligne)",
            placeholder="123456789\n987654321\n456789123",
            height=120,
            help="Entrez les Page IDs Facebook, un par ligne"
        )
        page_ids = [pid.strip() for pid in page_ids_input.split("\n") if pid.strip()]

    with col2:
        countries = st.multiselect(
            "🌍 Pays",
            options=list(AVAILABLE_COUNTRIES.keys()),
            default=DEFAULT_COUNTRIES,
            format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
            key="countries_pageid"
        )

        # Indicateur rapide
        if page_ids:
            batch_count = (len(page_ids) + 9) // 10
            st.info(f"📊 {len(page_ids)} IDs → {batch_count} requetes")

    # ═══ OPTIONS AVANCEES ═══
    with st.expander("⚙️ Options avancees", expanded=False):
        adv_col1, adv_col2 = st.columns(2)

        with adv_col1:
            languages = st.multiselect(
                "🗣️ Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=[],
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_pageid"
            )

        with adv_col2:
            cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
            selected_cms = st.multiselect("🛒 CMS a inclure", options=cms_options, default=["Shopify"], key="cms_pageid")

    # Mode apercu
    preview_mode = st.checkbox(
        "📋 Mode apercu",
        help="Voir les resultats avant de les enregistrer",
        key="preview_pageid"
    )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", use_container_width=True, key="btn_pageid"):
        if not page_ids:
            st.error("❌ Au moins un Page ID requis !")
            return

        run_page_id_search(page_ids, countries, languages, selected_cms, preview_mode)


def run_page_id_search(page_ids, countries, languages, selected_cms, preview_mode=False):
    """
    Execute la recherche par Page IDs (optimisee par batch de 10).

    Args:
        page_ids: Liste des Page IDs Facebook
        countries: Liste des codes pays
        languages: Liste des codes langues
        selected_cms: Liste des CMS a inclure
        preview_mode: Si True, affiche un apercu sans sauvegarder

    Phases:
        1. Recuperation des annonces par batch de 10
        2. Detection CMS
        3. Analyse Homepage (MarketSpy V2)
        4. Comptage produits Shopify
        5. Classification Gemini
        6. Detection Winning Ads
        7. Sauvegarde (si pas mode apercu)
    """
    from src.presentation.streamlit.dashboard import add_to_search_history
    from src.infrastructure.external_services.meta_api import init_token_rotator
    from src.infrastructure.persistence.database import (
        get_active_meta_tokens_with_proxies, ensure_tables_exist,
        create_search_log, update_search_log
    )

    db = get_database()
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # Charger les tokens
    tokens_with_proxies = []
    if db:
        with loading_spinner("Chargement des tokens..."):
            try:
                ensure_tables_exist(db)
                tokens_with_proxies = get_active_meta_tokens_with_proxies(db)
            except Exception as e:
                st.warning(f"Impossible de charger les tokens: {e}")

    if not tokens_with_proxies:
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            tokens_with_proxies = [{"id": None, "token": env_token, "proxy": None, "name": "Env Token"}]

    if not tokens_with_proxies:
        st.error("Aucun token Meta API disponible. Configurez vos tokens dans Settings > Tokens Meta API.")
        return

    # Sauvegarder dans l'historique
    add_to_search_history('page_ids', {
        'page_ids': page_ids,
        'countries': countries,
        'languages': languages,
        'cms': selected_cms
    })

    # Initialiser le TokenRotator
    rotator = init_token_rotator(tokens_with_proxies=tokens_with_proxies, db=db)
    if rotator.token_count > 1:
        st.success(f"Rotation automatique activee ({rotator.token_count} tokens)")

    client = MetaAdsClient(rotator.get_current_token())

    # Creer le log de recherche
    log_id = None
    if db:
        try:
            log_id = create_search_log(
                db,
                keywords=page_ids,
                countries=countries,
                languages=languages,
                min_ads=1,
                selected_cms=selected_cms if selected_cms else [],
                user_id=user_id
            )
        except Exception as e:
            st.warning(f"⚠️ Log non cree: {str(e)[:100]}")

    # Recuperer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db, user_id=user_id)
        if blacklist_ids:
            st.info(f"{len(blacklist_ids)} pages en blacklist seront ignorees")

    # Filtrer les page_ids blacklistes
    page_ids_filtered = [pid for pid in page_ids if str(pid) not in blacklist_ids]
    if len(page_ids_filtered) < len(page_ids):
        st.warning(f"{len(page_ids) - len(page_ids_filtered)} Page IDs ignores (blacklist)")

    if not page_ids_filtered:
        st.error("Aucun Page ID valide apres filtrage blacklist")
        return

    # ═══ PHASE 1: Recuperation des annonces par batch ═══
    st.subheader("Phase 1: Recuperation des annonces")
    batch_size = 10
    total_batches = (len(page_ids_filtered) + batch_size - 1) // batch_size
    st.caption(f"{len(page_ids_filtered)} Page IDs → {total_batches} requetes API")

    pages = {}
    page_ads = defaultdict(list)
    progress = st.progress(0)

    processed = 0
    for batch_idx in range(0, len(page_ids_filtered), batch_size):
        batch_pids = page_ids_filtered[batch_idx:batch_idx + batch_size]

        batch_results = client.fetch_ads_for_pages_batch(batch_pids, countries, languages)

        for pid in batch_pids:
            pid_str = str(pid)
            ads_list, count = batch_results.get(pid_str, ([], 0))

            if count > 0:
                page_name = ""
                if ads_list:
                    page_name = ads_list[0].get("page_name", "")

                pages[pid_str] = {
                    "page_id": pid_str,
                    "page_name": page_name,
                    "website": extract_website_from_ads(ads_list),
                    "ads_active_total": count,
                    "currency": extract_currency_from_ads(ads_list),
                    "cms": "Unknown",
                    "is_shopify": False,
                    "_keywords": set()
                }
                page_ads[pid_str] = ads_list

            processed += 1
            progress.progress(processed / len(page_ids_filtered))

        time.sleep(META_DELAY_BETWEEN_BATCHES)

    st.success(f"{len(pages)} pages avec annonces actives trouvees")

    if not pages:
        st.warning("Aucune page trouvee avec des annonces actives")
        return

    # ═══ PHASE 2: Detection CMS ═══
    st.subheader("Phase 2: Detection CMS")
    pages_with_sites = {pid: data for pid, data in pages.items() if data["website"]}
    progress = st.progress(0)

    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow"]

    for i, (pid, data) in enumerate(pages_with_sites.items()):
        cms_name = detect_cms_from_url(data["website"])
        data["cms"] = cms_name if cms_name else "Unknown"
        data["is_shopify"] = (cms_name == "Shopify")
        progress.progress((i + 1) / len(pages_with_sites))
        time.sleep(WEB_DELAY_CMS_CHECK)

    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in cms_options:
            return True
        return False

    pages_final = {pid: data for pid, data in pages.items() if cms_matches(data.get("cms", "Unknown"))}

    # Ajouter etat
    for pid, data in pages_final.items():
        data["etat"] = get_etat_from_ads_count(data.get("ads_active_total", 0))

    st.success(f"{len(pages_final)} pages avec CMS selectionnes")

    if not pages_final:
        st.warning("Aucune page trouvee avec les CMS selectionnes")
        return

    # ═══ PHASE 3: Analyse Homepage (MarketSpy V2) ═══
    st.subheader("Phase 3: Analyse des sites web")
    web_results = {}
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_final.items()):
        if data["website"]:
            result = analyze_homepage_v2(data["website"])
            web_results[pid] = {
                "product_count": None,
                "theme": result.get("theme", "Unknown"),
                "site_title": result.get("site_title", ""),
                "site_description": result.get("site_description", ""),
                "site_h1": result.get("site_h1", ""),
                "currency_from_site": result.get("currency_from_site", ""),
                "_from_cache": False,
                "_skip_classification": False
            }
            if not data["currency"] and result.get("currency_from_site"):
                data["currency"] = result["currency_from_site"]
            if result.get("theme") and result["theme"] != "Unknown":
                data["theme"] = result["theme"]
        progress.progress((i + 1) / len(pages_final))
        time.sleep(0.1)

    st.success(f"{len(web_results)} sites analyses")

    # ═══ PHASE 4: Comptage produits Shopify ═══
    st.subheader("Phase 4: Comptage produits Shopify")
    shopify_pages = [(pid, data) for pid, data in pages_final.items() if data.get("is_shopify") and data.get("website")]

    if shopify_pages:
        st.caption(f"{len(shopify_pages)} boutiques Shopify a analyser")

        def analyze_shopify_worker(pid_data):
            pid, data = pid_data
            try:
                result = analyze_sitemap_v2(data["website"])
                return pid, result
            except Exception as e:
                return pid, {"product_count": None, "error": str(e)[:50]}

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_shopify_worker, item): item[0] for item in shopify_pages}

            for future in as_completed(futures):
                pid, result = future.result()
                if pid in web_results:
                    count = result.get("product_count")
                    web_results[pid]["product_count"] = count if count is not None else None

        st.success(f"{len(shopify_pages)} boutiques analysees")
    else:
        st.info("Aucune boutique Shopify a analyser")

    # ═══ PHASE 5: Classification Gemini ═══
    st.subheader("Phase 5: Classification Gemini")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    pages_to_classify = []
    for pid, web_data in web_results.items():
        url = pages_final.get(pid, {}).get("website", "")
        has_content = url or web_data.get("site_title") or web_data.get("site_description") or web_data.get("site_h1")
        if has_content:
            pages_to_classify.append({
                "page_id": pid,
                "url": url,
                "site_title": web_data.get("site_title", ""),
                "site_description": web_data.get("site_description", ""),
                "site_h1": web_data.get("site_h1", ""),
            })

    if gemini_key and pages_to_classify:
        batch_count = (len(pages_to_classify) + 9) // 10
        st.caption(f"{len(pages_to_classify)} pages a classifier ({batch_count} batches)")

        try:
            classification_results = classify_pages_batch_v2(db, pages_to_classify)

            for pid, classification in classification_results.items():
                if pid in web_results:
                    web_results[pid]["gemini_category"] = classification.get("category", "")
                    web_results[pid]["gemini_subcategory"] = classification.get("subcategory", "")
                    web_results[pid]["gemini_confidence"] = classification.get("confidence", 0.0)

            st.success(f"{len(classification_results)} pages classifiees")
        except Exception as e:
            st.warning(f"Classification Gemini: {str(e)[:100]}")
    elif not gemini_key:
        st.warning("Cle Gemini non configuree - classification ignoree")
    else:
        st.info("Aucune page a classifier")

    # ═══ PHASE 6: Detection des Winning Ads ═══
    st.subheader("Phase 6: Detection des Winning Ads")
    scan_date = datetime.now()
    winning_ads_data = []
    winning_ads_by_page = {}

    progress = st.progress(0)
    for i, (pid, data) in enumerate(pages_final.items()):
        page_winning_count = 0
        for ad in page_ads.get(pid, []):
            is_winning, age_days, reach, matched_criteria = is_winning_ad(ad, scan_date, WINNING_AD_CRITERIA)
            if is_winning:
                winning_ads_data.append({
                    "ad": ad,
                    "page_id": pid,
                    "page_name": data.get("page_name", ""),
                    "age_days": age_days,
                    "reach": reach,
                    "matched_criteria": matched_criteria
                })
                page_winning_count += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

        progress.progress((i + 1) / len(pages_final))

    st.success(f"{len(winning_ads_data)} winning ads detectees sur {len(winning_ads_by_page)} pages")

    # Save to session
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.winning_ads_data = winning_ads_data
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.preview_mode = preview_mode
    st.session_state.search_log_id = log_id

    if preview_mode:
        st.success(f"Recherche terminee ! {len(pages_final)} pages trouvees")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        # ═══ PHASE 7: Sauvegarde en base de donnees ═══
        st.subheader("Phase 7: Sauvegarde en base de donnees")

        if db:
            try:
                thresholds = st.session_state.get("state_thresholds", None)
                pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds, log_id, user_id=user_id)
                det = st.session_state.get("detection_thresholds", {})
                suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI), user_id=user_id)
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, det.get("min_ads_liste", MIN_ADS_LISTE), user_id=user_id)
                winning_saved, winning_new, winning_updated = save_winning_ads(db, winning_ads_data, log_id, user_id=user_id)

                # Mettre a jour le search_log avec les IDs JSON pour l'historique
                if log_id:
                    page_ids_list = [str(pid) for pid in pages_final.keys()]
                    winning_ad_ids_list = [str(data.get("ad", {}).get("id", "")) for data in winning_ads_data if data.get("ad", {}).get("id")]
                    update_search_log(
                        db, log_id,
                        status="completed",
                        page_ids=json.dumps(page_ids_list),
                        winning_ad_ids=json.dumps(winning_ad_ids_list),
                        pages_saved=pages_saved,
                        winning_ads_count=len(winning_ads_data)
                    )

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Pages", pages_saved)
                col2.metric("Suivi", suivi_saved)
                col3.metric("Annonces", ads_saved)
                col4.metric("Winning", winning_saved)
                st.success("Donnees sauvegardees !")
            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")

        st.balloons()
        st.success("Recherche terminee !")
