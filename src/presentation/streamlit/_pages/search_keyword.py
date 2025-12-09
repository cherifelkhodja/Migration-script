"""
Module de recherche par mots-cles.

Ce module gere la recherche d'annonces Meta via mots-cles.
Il constitue le coeur du pipeline de decouverte d'annonceurs.

Fonctions:
----------
- render_keyword_search: Interface utilisateur de recherche
- run_search_process: Pipeline complet en 8 phases
"""
from datetime import datetime
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os

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
    get_cached_pages_info
)
from src.infrastructure.external_services.meta_api import MetaAdsClient
from src.infrastructure.scrapers.web_analyzer import (
    extract_website_from_ads, extract_currency_from_ads
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
    DEFAULT_COUNTRIES, MIN_ADS_INITIAL,
    WINNING_AD_CRITERIA, MIN_ADS_SUIVI, MIN_ADS_LISTE,
    META_DELAY_BETWEEN_KEYWORDS, META_DELAY_BETWEEN_BATCHES,
)
from src.presentation.streamlit.components.progress import SearchProgressTracker


def render_keyword_search():
    """
    Interface de recherche par mots-cles.

    Affiche le formulaire de recherche avec:
    - Champs essentiels (mots-cles, pays)
    - Options avancees (langues, min ads, CMS)
    - Mode arriere-plan / apercu
    """
    from src.presentation.streamlit.dashboard import add_to_search_history

    # Multi-tenancy: recuperer l'utilisateur courant
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # ═══ CHAMPS ESSENTIELS (toujours visibles) ═══
    section_header("Recherche rapide", icon="🎯")

    col1, col2 = st.columns([2, 1])

    with col1:
        keywords_input = st.text_area(
            "Mots-cles (un par ligne)",
            placeholder="dropshipping\necommerce\nboutique en ligne",
            height=100,
            help="Entrez vos mots-cles de recherche, un par ligne"
        )
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

    with col2:
        countries = st.multiselect(
            "🌍 Pays",
            options=list(AVAILABLE_COUNTRIES.keys()),
            default=DEFAULT_COUNTRIES,
            format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
            key="countries_keyword"
        )

        # Indicateur rapide
        if keywords:
            st.info(f"🔍 {len(keywords)} mot(s)-cle(s)")

    # ═══ OPTIONS AVANCEES (dans expander) ═══
    with st.expander("⚙️ Options avancees", expanded=False):
        adv_col1, adv_col2, adv_col3 = st.columns(3)

        with adv_col1:
            languages = st.multiselect(
                "🗣️ Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=[],
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_keyword"
            )

        with adv_col2:
            min_ads = st.slider("📊 Min. ads pour inclusion", 1, 50, MIN_ADS_INITIAL, key="min_ads_keyword")

        with adv_col3:
            cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
            selected_cms = st.multiselect("🛒 CMS a inclure", options=cms_options, default=["Shopify"], key="cms_keyword")

    # Options de mode
    opt_col1, opt_col2 = st.columns(2)

    with opt_col1:
        background_mode = st.checkbox(
            "⏳ Lancer en arriere-plan",
            help="La recherche continue meme si vous quittez la page. Resultats disponibles dans 'Recherches en cours'.",
            key="background_keyword"
        )

    with opt_col2:
        preview_mode = st.checkbox(
            "📋 Mode apercu",
            help="Voir les resultats avant de les enregistrer en base de donnees",
            key="preview_keyword",
            disabled=background_mode
        )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", use_container_width=True, key="btn_keyword"):
        if not keywords:
            st.error("❌ Au moins un mot-cle requis !")
            return

        if background_mode:
            # Mode arriere-plan: ajouter a la file d'attente
            from src.infrastructure.workers.background_worker import get_worker
            worker = get_worker()

            search_id = worker.submit_search(
                keywords=keywords,
                cms_filter=selected_cms if selected_cms else ["Shopify"],
                ads_min=min_ads,
                countries=",".join(countries) if countries else "FR",
                languages=",".join(languages) if languages else "",
                user_id=user_id
            )

            st.success(f"✅ Recherche #{search_id} ajoutee a la file d'attente!")
            st.info("💡 Vous pouvez quitter cette page, la recherche continuera en arriere-plan. Consultez les resultats dans **Recherches en cours**.")

            if st.button("📋 Voir les recherches en arriere-plan", key="goto_bg"):
                st.session_state.current_page = "Background Searches"
                st.rerun()
        else:
            # Mode direct: execution synchrone
            run_search_process(keywords, countries, languages, min_ads, selected_cms, preview_mode)


def run_search_process(
    keywords: list,
    countries: list,
    languages: list,
    min_ads: int,
    selected_cms: list,
    preview_mode: bool = False
):
    """
    Execute le pipeline complet de recherche d'annonceurs Meta.

    Ce processus orchestre 8 phases de traitement pour identifier les pages
    Facebook avec une activite publicitaire significative, analyser leurs
    sites web, et detecter les winning ads performantes.

    Args:
        keywords: Liste des mots-cles de recherche
        countries: Liste des codes pays (ex: ["FR", "BE"])
        languages: Liste des codes langues (ex: ["fr", "en"])
        min_ads: Seuil minimum d'ads actives pour retenir une page
        selected_cms: Liste des CMS a inclure (ex: ["Shopify"])
        preview_mode: Si True, affiche un apercu sans sauvegarder

    Phases d'execution:
        1. Recherche API par keyword avec deduplication
        2. Regroupement ads par page et filtrage blacklist
        3. Extraction des URLs de sites web + CMS
        4. Filtrage par CMS selectionnes
        5. Comptage exact ads par batch API de 10
        6. Analyse web + classification Gemini
        7. Detection winning ads (criteres reach/age)
        8. Sauvegarde DB ou apercu interactif
    """
    from src.presentation.streamlit.dashboard import add_to_search_history
    from src.infrastructure.monitoring.api_tracker import APITracker, set_current_tracker
    from src.infrastructure.external_services.meta_api import init_token_rotator
    from src.infrastructure.persistence.database import (
        get_active_meta_tokens_with_proxies, ensure_tables_exist, create_search_log
    )

    db = get_database()
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # Charger les tokens depuis la base de donnees
    tokens_with_proxies = []
    if db:
        with loading_spinner("Chargement des tokens..."):
            try:
                ensure_tables_exist(db)
                tokens_with_proxies = get_active_meta_tokens_with_proxies(db)
            except Exception as e:
                st.warning(f"⚠️ Impossible de charger les tokens depuis la DB: {e}")

    # Fallback sur variable d'environnement
    if not tokens_with_proxies:
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            tokens_with_proxies = [{"id": None, "token": env_token, "proxy": None, "name": "Env Token"}]
            st.info("📝 Utilisation du token depuis META_ACCESS_TOKEN")

    if not tokens_with_proxies:
        st.error("❌ Aucun token Meta API disponible. Configurez vos tokens dans **Settings > Tokens Meta API**.")
        return

    # Sauvegarder dans l'historique
    add_to_search_history('keywords', {
        'keywords': keywords,
        'countries': countries,
        'languages': languages,
        'min_ads': min_ads,
        'cms': selected_cms
    })

    st.info(f"🔄 {len(tokens_with_proxies)} token(s) actif(s)")

    # Initialiser le TokenRotator
    rotator = init_token_rotator(tokens_with_proxies=tokens_with_proxies, db=db)

    if rotator.token_count > 1:
        st.success(f"🔄 Rotation automatique activee ({rotator.token_count} tokens)")

    client = MetaAdsClient(rotator.get_current_token())

    # Creer le log de recherche
    log_id = None
    if db:
        try:
            log_id = create_search_log(
                db,
                keywords=keywords,
                countries=countries,
                languages=languages,
                min_ads=min_ads,
                selected_cms=selected_cms if selected_cms else [],
                user_id=user_id
            )
        except Exception as e:
            st.warning(f"⚠️ Log non cree: {str(e)[:100]}")

    # Creer l'API tracker
    api_tracker = APITracker(search_log_id=log_id, db=db)
    set_current_tracker(api_tracker)

    # Creer le tracker de progression
    progress_container = st.container()
    tracker = SearchProgressTracker(progress_container, db=db, log_id=log_id, api_tracker=api_tracker)

    # Recuperer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db, user_id=user_id)
        if blacklist_ids:
            st.info(f"🚫 {len(blacklist_ids)} pages en blacklist seront ignorees")

    # PHASE 1: Recherche par mots-cles
    tracker.start_phase(1, "Recherche par mots-cles", total_phases=8)
    all_ads = []
    seen_ad_ids = set()

    for i, kw in enumerate(keywords):
        tracker.update_step("Recherche", i + 1, len(keywords), f"Mot-cle: {kw}")

        if i > 0:
            time.sleep(META_DELAY_BETWEEN_KEYWORDS)

        try:
            ads = client.search_ads(kw, countries, languages)
            new_ads_count = 0
            for ad in ads:
                ad_id = ad.get("id")
                if ad_id and ad_id not in seen_ad_ids:
                    ad["_keyword"] = kw
                    all_ads.append(ad)
                    seen_ad_ids.add(ad_id)
                    new_ads_count += 1

            tracker.log_detail("🔑", f"'{kw}'", count=new_ads_count, total_so_far=len(all_ads))

        except RuntimeError as e:
            tracker.log_detail("❌", f"'{kw}' - Erreur: {str(e)[:50]}")

    tracker.clear_detail_logs()

    phase1_stats = {
        "Mots-cles recherches": len(keywords),
        "Annonces trouvees": len(all_ads),
        "Annonces uniques": len(seen_ad_ids),
    }
    tracker.complete_phase(f"{len(all_ads)} annonces trouvees", details={
        "keywords_searched": len(keywords),
        "ads_found": len(all_ads)
    }, stats=phase1_stats)
    tracker.update_metric("total_ads_found", len(all_ads))

    # PHASE 2: Regroupement par page
    tracker.start_phase(2, "Regroupement par page", total_phases=8)
    pages = {}
    page_ads = defaultdict(list)
    name_counter = defaultdict(Counter)
    blacklisted_ads_count = 0
    blacklisted_pages_found = set()

    for i, ad in enumerate(all_ads):
        if i % 100 == 0:
            tracker.update_step("Regroupement", i + 1, len(all_ads))

        pid = ad.get("page_id")
        if not pid:
            continue

        if str(pid) in blacklist_ids:
            blacklisted_ads_count += 1
            blacklisted_pages_found.add(str(pid))
            continue

        pname = (ad.get("page_name") or "").strip()

        if pid not in pages:
            pages[pid] = {
                "page_id": pid, "page_name": pname, "website": "",
                "_ad_ids": set(), "_keywords": set(), "ads_found_search": 0,
                "ads_active_total": -1, "currency": "",
                "cms": "Unknown", "is_shopify": False
            }

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

    tracker.clear_detail_logs()

    phase2_stats = {
        "Pages trouvees": len(pages),
        f"Pages >={min_ads} ads": len(pages_filtered),
        "Pages filtrees": len(pages) - len(pages_filtered),
        "Pages blacklistees": len(blacklisted_pages_found),
    }

    phase2_details = f"{len(pages_filtered)} pages avec >={min_ads} ads"
    if blacklisted_ads_count > 0:
        phase2_details += f" ({blacklisted_ads_count} ads blacklistees ignorees)"
    tracker.complete_phase(phase2_details, stats=phase2_stats)
    tracker.update_metric("total_pages_found", len(pages))
    tracker.update_metric("pages_after_filter", len(pages_filtered))

    if not pages_filtered:
        if blacklisted_ads_count > 0 and len(pages) == 0:
            st.warning(f"Toutes les {blacklisted_ads_count} ads trouvees appartiennent a des pages blacklistees")
        elif len(all_ads) == 0:
            st.warning("Aucune annonce trouvee pour ces mots-cles.")
        else:
            st.warning(f"{len(pages)} pages trouvees mais aucune avec >={min_ads} ads")
        tracker.finalize_log(status="no_results")
        return

    # PHASE 3+4 FUSIONNEES: Extraction URL + CMS + Metadata (MarketSpy V2)
    tracker.start_phase(3, "Analyse Homepage (CMS + Metadata)", total_phases=8)

    cached_pages = {}
    if db:
        cached_pages = get_cached_pages_info(db, list(pages_filtered.keys()), cache_days=1, user_id=user_id)
        valid_cache = sum(1 for c in cached_pages.values() if not c.get("needs_rescan"))
        if valid_cache > 0:
            st.info(f"📦 {valid_cache} pages en cache BDD (scan < 1 jour)")

    # Etape 1: Extraire URLs depuis les ads (rapide, pas de HTTP)
    for i, (pid, data) in enumerate(pages_filtered.items()):
        cached = cached_pages.get(str(pid), {})
        if cached.get("lien_site"):
            data["website"] = cached["lien_site"]
            data["_from_cache"] = True
        else:
            data["website"] = extract_website_from_ads(page_ads.get(pid, []))
            data["_from_cache"] = False

    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}
    sites_from_cache = sum(1 for d in pages_with_sites.values() if d.get("_from_cache"))

    # Etape 2: Identifier les pages necessitant une analyse
    pages_need_analysis = []
    cms_cached_count = 0

    for pid, data in pages_with_sites.items():
        cached = cached_pages.get(str(pid), {})
        # Utiliser cache si CMS connu
        if cached.get("cms") and cached["cms"] not in ("Unknown", "Inconnu", ""):
            data["cms"] = cached["cms"]
            data["is_shopify"] = cached["cms"] == "Shopify"
            data["theme"] = cached.get("template", "Unknown")
            data["_cms_cached"] = True
            # Copier aussi les metadata du cache
            if cached.get("site_title"):
                data["_site_title"] = cached.get("site_title", "")
                data["_site_description"] = cached.get("site_description", "")
                data["_site_h1"] = cached.get("site_h1", "")
            cms_cached_count += 1
        else:
            pages_need_analysis.append((pid, data))
            data["_cms_cached"] = False

    st.info(f"🔍 {len(pages_need_analysis)} sites a analyser ({cms_cached_count} CMS en cache)")

    # Etape 3: Analyse MarketSpy V2 en parallele (1 requete = CMS + Theme + Metadata)
    if pages_need_analysis:
        completed = 0

        def analyze_homepage_worker(pid_data):
            pid, data = pid_data
            try:
                result = analyze_homepage_v2(data["website"])
                return pid, result
            except Exception as e:
                return pid, {"cms": "Unknown", "error": str(e)[:50]}

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_homepage_worker, item): item[0] for item in pages_need_analysis}

            for future in as_completed(futures):
                pid, result = future.result()
                data = pages_with_sites[pid]

                # Mettre a jour avec les resultats MarketSpy
                data["cms"] = result.get("cms", "Unknown")
                data["is_shopify"] = result.get("is_shopify", False)
                data["theme"] = result.get("theme", "Unknown")
                data["_site_title"] = result.get("site_title", "")
                data["_site_description"] = result.get("site_description", "")
                data["_site_h1"] = result.get("site_h1", "")
                if result.get("currency_from_site") and not data.get("currency"):
                    data["currency"] = result["currency_from_site"]
                if result.get("final_url"):
                    data["website"] = result["final_url"]

                completed += 1
                if completed % 5 == 0:
                    tracker.update_step("Analyse Homepage", completed, len(pages_need_analysis))

    tracker.clear_detail_logs()

    # Etape 4: Filtrage par CMS selectionnes
    known_cms_list = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow"]

    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in known_cms_list:
            return True
        return False

    pages_with_cms = {pid: data for pid, data in pages_with_sites.items() if cms_matches(data.get("cms", "Unknown"))}

    # Statistiques Phase 3+4
    phase34_stats = {
        "Sites avec URL": len(pages_with_sites),
        "URLs en cache": sites_from_cache,
        "CMS en cache": cms_cached_count,
        "Sites analyses": len(pages_need_analysis),
        "Pages CMS match": len(pages_with_cms),
    }
    tracker.complete_phase(f"{len(pages_with_cms)} pages {selected_cms}", stats=phase34_stats)

    # Phase 4 devient un simple log (deja fait dans Phase 3)
    tracker.start_phase(4, "Filtrage CMS", total_phases=8)
    cms_distribution = {}
    for data in pages_with_sites.values():
        cms = data.get("cms", "Unknown")
        cms_distribution[cms] = cms_distribution.get(cms, 0) + 1

    phase4_stats = {
        "Total pages": len(pages_with_sites),
        "Retenues": len(pages_with_cms),
        "Exclues": len(pages_with_sites) - len(pages_with_cms),
    }
    # Ajouter distribution CMS
    for cms, count in sorted(cms_distribution.items(), key=lambda x: -x[1])[:5]:
        phase4_stats[f"  {cms}"] = count

    tracker.complete_phase(f"{len(pages_with_cms)} pages retenues apres filtre CMS", stats=phase4_stats)

    # PHASE 5: Comptage des annonces
    tracker.start_phase(5, "Comptage des annonces (batch)", total_phases=8)

    page_ids_list = list(pages_with_cms.keys())
    batch_size = 10
    total_batches = (len(page_ids_list) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(page_ids_list), batch_size):
        batch_pids = page_ids_list[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        tracker.update_step("Batch API", batch_num, total_batches)

        batch_results = client.fetch_ads_for_pages_batch(batch_pids, countries, languages)

        for pid in batch_pids:
            data = pages_with_cms[pid]
            ads_complete, count = batch_results.get(str(pid), ([], 0))

            if count > 0:
                page_ads[pid] = ads_complete
                data["ads_active_total"] = count
                data["currency"] = extract_currency_from_ads(ads_complete)
            else:
                data["ads_active_total"] = data["ads_found_search"]

        time.sleep(META_DELAY_BETWEEN_BATCHES)

    pages_final = {pid: data for pid, data in pages_with_cms.items() if data["ads_active_total"] >= min_ads}

    # Ajouter etat
    for pid, data in pages_final.items():
        data["etat"] = get_etat_from_ads_count(data.get("ads_active_total", 0))

    total_ads_counted = sum(d.get("ads_active_total", 0) for d in pages_final.values())

    phase5_stats = {
        "Pages comptees": len(pages_with_cms),
        "Pages finales": len(pages_final),
        "Total ads actives": total_ads_counted,
    }
    tracker.complete_phase(f"{len(pages_final)} pages finales", stats=phase5_stats)

    if not pages_final:
        st.warning("Aucune page finale trouvee")
        return

    # PHASE 6: Analyse Sitemap (Shopify only) + Classification Gemini V2
    tracker.start_phase(6, "Sitemap + Classification Gemini", total_phases=8)
    web_results = {}

    # Etape 1: Verifier le cache pour le comptage produits
    pages_need_sitemap = []
    pages_cached = 0

    for pid, data in pages_final.items():
        cached = cached_pages.get(str(pid), {})

        is_recent = not cached.get("needs_rescan")
        has_analysis = cached.get("nombre_produits") is not None
        has_thematique = bool(cached.get("thematique"))

        if is_recent and has_analysis and has_thematique:
            # Utiliser les donnees du cache
            web_results[pid] = {
                "product_count": cached.get("nombre_produits", 0),
                "theme": data.get("theme", cached.get("template", "")),
                "category": cached.get("thematique", ""),
                "currency_from_site": cached.get("devise", ""),
                "site_title": data.get("_site_title", ""),
                "site_description": data.get("_site_description", ""),
                "site_h1": data.get("_site_h1", ""),
                "_from_cache": True,
                "_skip_classification": True
            }
            if cached.get("devise") and not data.get("currency"):
                data["currency"] = cached["devise"]
            pages_cached += 1
        else:
            # Preparer les donnees avec les metadata deja extraites en Phase 3
            web_results[pid] = {
                "product_count": None,
                "theme": data.get("theme", "Unknown"),
                "site_title": data.get("_site_title", ""),
                "site_description": data.get("_site_description", ""),
                "site_h1": data.get("_site_h1", ""),
                "currency_from_site": data.get("currency", ""),
                "_from_cache": False,
                "_skip_classification": False
            }
            # Sitemap seulement pour Shopify
            if data.get("is_shopify") and data.get("website"):
                pages_need_sitemap.append((pid, data))

    st.info(f"📊 {len(pages_need_sitemap)} sitemaps Shopify a analyser ({pages_cached} en cache)")

    # Etape 2: Analyse Sitemap MarketSpy V2 (Shopify uniquement)
    if pages_need_sitemap:
        completed = 0

        def analyze_sitemap_worker(pid_data):
            pid, data = pid_data
            try:
                result = analyze_sitemap_v2(data["website"], countries[0] if countries else "FR")
                return pid, result
            except Exception as e:
                return pid, {"product_count": None, "error": str(e)[:50]}

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_sitemap_worker, item): item[0] for item in pages_need_sitemap}

            for future in as_completed(futures):
                pid, result = future.result()
                if pid in web_results:
                    count = result.get("product_count")
                    web_results[pid]["product_count"] = count if count is not None else None

                completed += 1
                if completed % 5 == 0:
                    tracker.update_step("Analyse Sitemap", completed, len(pages_need_sitemap))

    # Etape 3: Classification Gemini V2 (batch de 10 sites)
    classified_count = 0
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    pages_to_classify_data = []
    for pid, web_data in web_results.items():
        if web_data.get("_skip_classification"):
            continue
        url = pages_final.get(pid, {}).get("website", "")
        has_content = url or web_data.get("site_title") or web_data.get("site_description") or web_data.get("site_h1")
        if has_content:
            pages_to_classify_data.append({
                "page_id": pid,
                "url": url,
                "site_title": web_data.get("site_title", ""),
                "site_description": web_data.get("site_description", ""),
                "site_h1": web_data.get("site_h1", ""),
            })

    if gemini_key and pages_to_classify_data:
        tracker.update_step("Classification Gemini", 0, 1)
        batch_count = (len(pages_to_classify_data) + 9) // 10
        st.info(f"🤖 Classification de {len(pages_to_classify_data)} pages ({batch_count} batches Gemini)")

        try:
            classification_results = classify_pages_batch_v2(db, pages_to_classify_data)

            for pid, classification in classification_results.items():
                if pid in web_results:
                    web_results[pid]["gemini_category"] = classification.get("category", "")
                    web_results[pid]["gemini_subcategory"] = classification.get("subcategory", "")
                    web_results[pid]["gemini_confidence"] = classification.get("confidence", 0.0)

            classified_count = len(classification_results)
            st.success(f"✅ {classified_count} pages classifiees")

        except Exception as e:
            st.warning(f"⚠️ Classification Gemini: {str(e)[:100]}")
    elif not gemini_key and pages_to_classify_data:
        st.warning("⚠️ Cle Gemini non configuree - classification ignoree")

    phase6_stats = {
        "Sites totaux": len(web_results),
        "En cache": pages_cached,
        "Sitemaps analyses": len(pages_need_sitemap),
        "Sites classifies": classified_count,
    }
    tracker.complete_phase(f"{len(web_results)} sites, {classified_count} classifiees", stats=phase6_stats)

    # PHASE 7: Detection des Winning Ads
    tracker.start_phase(7, "Detection des Winning Ads", total_phases=8)
    scan_date = datetime.now()
    winning_ads_data = []
    winning_ads_by_page = {}
    total_ads_checked = 0

    for i, (pid, data) in enumerate(pages_final.items()):
        tracker.update_step("Analyse winning", i + 1, len(pages_final))

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
            total_ads_checked += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

    phase7_stats = {
        "Ads analysees": total_ads_checked,
        "Winning ads": len(winning_ads_data),
        "Pages avec winning": len(winning_ads_by_page),
    }
    tracker.complete_phase(f"{len(winning_ads_data)} winning ads sur {len(winning_ads_by_page)} pages", stats=phase7_stats)
    tracker.update_metric("winning_ads_count", len(winning_ads_data))

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
        tracker.show_summary()
        tracker.finalize_log(status="preview")
        st.success(f"Recherche terminee ! {len(pages_final)} pages trouvees")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        # PHASE 8: Sauvegarde en base de donnees
        tracker.start_phase(8, "Sauvegarde en base de donnees", total_phases=8)

        pages_saved = 0
        suivi_saved = 0
        ads_saved = 0

        if db:
            try:
                tracker.update_step("Sauvegarde pages", 1, 4)
                thresholds = st.session_state.get("state_thresholds", None)
                pages_result = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds, log_id, user_id=user_id)
                if isinstance(pages_result, tuple):
                    pages_saved, pages_new, pages_existing = pages_result
                else:
                    pages_saved = pages_result
                    pages_new = pages_saved
                    pages_existing = 0

                tracker.update_step("Sauvegarde suivi", 2, 4)
                det = st.session_state.get("detection_thresholds", {})
                suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI), user_id=user_id)

                tracker.update_step("Sauvegarde annonces", 3, 4)
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, det.get("min_ads_liste", MIN_ADS_LISTE), user_id=user_id)

                tracker.update_step("Sauvegarde winning ads", 4, 4)
                winning_saved, winning_new, winning_updated = save_winning_ads(db, winning_ads_data, log_id, user_id=user_id)

                # Mettre a jour le search_log avec les IDs JSON pour l'historique
                if log_id:
                    import json
                    from src.infrastructure.persistence.database import update_search_log
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

                msg = f"{pages_saved} pages, {ads_saved} ads, {winning_saved} winning ({winning_new} 🆕)"

                phase8_stats = {
                    "Pages sauvees": pages_saved,
                    "Nouvelles pages": pages_new,
                    "Suivi pages": suivi_saved,
                    "Annonces sauvees": ads_saved,
                    "Winning ads sauvees": winning_saved,
                }
                tracker.complete_phase(msg, stats=phase8_stats)
                tracker.update_metric("pages_saved", pages_saved)
                tracker.update_metric("ads_saved", ads_saved)

            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")
                tracker.finalize_log(status="failed", error_message=str(e))

        tracker.show_summary()
        tracker.finalize_log(status="completed")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Pages", pages_saved)
        col2.metric("Suivi", suivi_saved)
        col3.metric("Annonces", ads_saved)
        col4.metric("Winning", winning_saved)
        col5.metric("Classifiees", classified_count)

        st.balloons()
        st.success("Recherche terminee !")
