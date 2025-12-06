"""
Module d'exécution de recherche en arrière-plan.
Version headless (sans Streamlit) de la logique de recherche.
"""
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import (
    META_DELAY_BETWEEN_KEYWORDS,
    META_DELAY_BETWEEN_BATCHES,
    WINNING_AD_CRITERIA,
    MIN_ADS_SUIVI,
    MIN_ADS_LISTE
)


class BackgroundProgressTracker:
    """
    Tracker de progression pour les recherches en arrière-plan.
    Met à jour la base de données au lieu de l'UI Streamlit.
    """

    def __init__(self, db, search_id: int):
        """
        Args:
            db: DatabaseManager instance
            search_id: ID de la recherche dans SearchQueue
        """
        self.db = db
        self.search_id = search_id
        self.current_phase = 0
        self.total_phases = 9
        self.phases_data = []
        self.phase_start_time = None
        self.metrics = {}

    def start_phase(self, phase_num: int, phase_name: str, total_phases: int = 9):
        """Démarre une nouvelle phase"""
        self.current_phase = phase_num
        self.total_phases = total_phases
        self.phase_start_time = time.time()

        # Calculer le pourcentage global
        progress_percent = int((phase_num - 1) / total_phases * 100)

        self._update_db(
            phase=phase_num,
            phase_name=phase_name,
            percent=progress_percent,
            message=f"Phase {phase_num}/{total_phases}: {phase_name}"
        )

        print(f"[Search #{self.search_id}] Phase {phase_num}: {phase_name}")

    def update_step(self, step_name: str, current: int, total: int, detail: str = ""):
        """Met à jour la progression au sein d'une phase"""
        step_percent = int(current / total * 100) if total > 0 else 0
        global_percent = int(((self.current_phase - 1) + (current / total)) / self.total_phases * 100)

        message = f"{step_name}: {current}/{total}"
        if detail:
            message += f" - {detail}"

        self._update_db(
            phase=self.current_phase,
            percent=global_percent,
            message=message
        )

    def complete_phase(self, result_summary: str, details: dict = None, stats: dict = None):
        """Marque une phase comme terminée"""
        duration = time.time() - self.phase_start_time if self.phase_start_time else 0

        phase_data = {
            "num": self.current_phase,
            "name": self._get_phase_name(self.current_phase),
            "result": result_summary,
            "duration": duration,
            "time_formatted": self._format_duration(duration),
            "details": details or {},
            "stats": stats or {}
        }
        self.phases_data.append(phase_data)

        # Mettre à jour la DB avec les phases complètes
        self._update_db(
            phase=self.current_phase,
            percent=int(self.current_phase / self.total_phases * 100),
            message=f"Phase {self.current_phase} terminée: {result_summary}",
            phases_data=self.phases_data
        )

        print(f"[Search #{self.search_id}] Phase {self.current_phase} terminée: {result_summary} ({self._format_duration(duration)})")

    def update_metric(self, key: str, value: Any):
        """Met à jour une métrique"""
        self.metrics[key] = value

    def _update_db(self, phase: int, percent: int, message: str,
                   phase_name: str = None, phases_data: list = None):
        """Met à jour la base de données"""
        from app.database import update_search_queue_progress

        update_search_queue_progress(
            self.db,
            self.search_id,
            phase=phase,
            phase_name=phase_name or self._get_phase_name(phase),
            percent=percent,
            message=message,
            phases_data=phases_data
        )

    def _get_phase_name(self, phase_num: int) -> str:
        """Retourne le nom d'une phase"""
        names = {
            1: "Recherche par mots-clés",
            2: "Regroupement par page",
            3: "Extraction sites web",
            4: "Détection CMS",
            5: "Comptage des annonces",
            6: "Analyse sites web",
            7: "Détection Winning Ads",
            8: "Sauvegarde"
        }
        return names.get(phase_num, f"Phase {phase_num}")

    def _format_duration(self, seconds: float) -> str:
        """Formate une durée en format lisible"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    def get_phases_data(self) -> list:
        """Retourne les données des phases"""
        return self.phases_data

    def get_metrics(self) -> dict:
        """Retourne les métriques"""
        return self.metrics


def execute_background_search(
    db,
    search_id: int,
    keywords: List[str],
    cms_filter: List[str],
    ads_min: int = 3,
    countries: str = "FR",
    languages: str = "fr"
) -> Dict[str, Any]:
    """
    Exécute une recherche complète en arrière-plan.

    Args:
        db: DatabaseManager instance
        search_id: ID de la recherche dans SearchQueue
        keywords: Liste des mots-clés
        cms_filter: Liste des CMS à inclure
        ads_min: Nombre minimum d'ads
        countries: Pays (code)
        languages: Langues (code)

    Returns:
        Dict avec les résultats et search_log_id
    """
    from app.meta_api import MetaAdsClient, init_token_rotator, get_token_rotator, extract_currency_from_ads
    from app.shopify_detector import detect_cms_from_url
    from app.web_analyzer import analyze_website_complete
    from app.database import (
        get_active_meta_tokens_with_proxies, get_blacklist_ids, get_cached_pages_info,
        create_search_log, update_search_log, save_pages_recherche,
        save_suivi_page, save_ads_recherche, save_winning_ads,
        ensure_tables_exist, is_winning_ad,
        record_pages_search_history_batch, record_winning_ads_search_history_batch
    )
    from app.api_tracker import APITracker, set_current_tracker

    # Liste des CMS disponibles
    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "BigCommerce",
                   "Wix", "Squarespace", "Custom", "Autre/Inconnu"]

    # Créer le tracker de progression
    tracker = BackgroundProgressTracker(db, search_id)

    # Convertir countries et languages en listes si ce sont des strings
    # (SearchQueue stocke des strings comme "FR" ou "FR,BE")
    if isinstance(countries, str):
        countries_list = [c.strip() for c in countries.split(",") if c.strip()]
    else:
        countries_list = countries if countries else ["FR"]

    if isinstance(languages, str):
        languages_list = [l.strip() for l in languages.split(",") if l.strip()]
    else:
        languages_list = languages if languages else []  # Vide si pas de langues

    # S'assurer que les tables existent
    ensure_tables_exist(db)

    # Charger les tokens avec leurs proxies
    tokens_data = get_active_meta_tokens_with_proxies(db)
    if not tokens_data:
        # Fallback sur variable d'environnement
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            tokens_data = [{"token": env_token, "proxy": None, "name": "ENV Token"}]

    if not tokens_data:
        raise ValueError("Aucun token Meta API disponible")

    # Initialiser le client Meta avec rotation par proxy
    rotator = init_token_rotator(tokens_with_proxies=tokens_data, db=db)
    client = MetaAdsClient(rotator.get_current_token())

    # Créer le log de recherche
    log_id = create_search_log(
        db,
        keywords=keywords,
        countries=countries,
        languages=languages,
        min_ads=ads_min,
        selected_cms=cms_filter
    )

    # Créer l'API tracker
    api_tracker = APITracker(search_log_id=log_id, db=db)
    set_current_tracker(api_tracker)

    # Récupérer la blacklist
    blacklist_ids = get_blacklist_ids(db)
    print(f"[Search #{search_id}] {len(blacklist_ids)} pages en blacklist")

    # ═══ PHASE 1: Recherche par mots-clés (parallèle si proxies) ═══
    tracker.start_phase(1, "Recherche par mots-clés", total_phases=8)

    # Utiliser la recherche parallèle intelligente
    from app.meta_api import search_keywords_parallel

    def phase1_progress(kw, current, total):
        """Callback pour la progression de la recherche"""
        tracker.update_step("Recherche", current, total, f"Mot-clé: {kw}")

    # Lancer la recherche (parallèle ou séquentielle selon les proxies)
    all_ads, ads_by_keyword = search_keywords_parallel(
        keywords=keywords,
        countries=countries_list,
        languages=languages_list,
        db=db,
        progress_callback=phase1_progress
    )

    # Compter les ads uniques (déjà dédupliquées par search_keywords_parallel)
    seen_ad_ids = {ad.get("id") for ad in all_ads if ad.get("id")}

    phase1_stats = {
        "Mots-clés recherchés": len(keywords),
        "Annonces trouvées": len(all_ads),
        "Annonces uniques": len(seen_ad_ids),
        "Mode": "parallèle" if rotator.has_proxy_tokens() else "séquentiel",
    }
    tracker.complete_phase(f"{len(all_ads)} annonces trouvées", stats=phase1_stats)
    tracker.update_metric("total_ads_found", len(all_ads))

    # ═══ PHASE 2: Regroupement par page ═══
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

    pages_filtered = {pid: data for pid, data in pages.items() if data["ads_found_search"] >= ads_min}

    phase2_stats = {
        "Pages trouvées": len(pages),
        f"Pages ≥{ads_min} ads": len(pages_filtered),
        "Pages filtrées": len(pages) - len(pages_filtered),
        "Pages blacklistées": len(blacklisted_pages_found),
        "Ads blacklist ignorées": blacklisted_ads_count,
    }
    tracker.complete_phase(f"{len(pages_filtered)} pages avec ≥{ads_min} ads", stats=phase2_stats)
    tracker.update_metric("total_pages_found", len(pages))
    tracker.update_metric("pages_after_filter", len(pages_filtered))

    if not pages_filtered:
        update_search_log(db, log_id, status="no_results",
                         total_ads_found=len(all_ads),
                         total_pages_found=len(pages))
        return {"search_log_id": log_id, "status": "no_results", "pages": 0}

    # ═══ PHASE 3: Extraction sites web (avec cache) ═══
    tracker.start_phase(3, "Extraction sites web", total_phases=8)

    cached_pages = get_cached_pages_info(db, list(pages_filtered.keys()), cache_days=4)

    def extract_website_from_ads(ads_list):
        """Extrait l'URL du site depuis les annonces"""
        for ad in ads_list:
            link_url = ad.get("ad_creative_link_url")
            if link_url:
                return link_url
            captions = ad.get("ad_creative_link_captions", [])
            if captions and isinstance(captions, list):
                for cap in captions:
                    if cap and "." in cap:
                        return f"https://{cap}"
        return ""

    for i, (pid, data) in enumerate(pages_filtered.items()):
        cached = cached_pages.get(str(pid), {})

        if cached.get("lien_site") and not cached.get("needs_rescan"):
            data["website"] = cached["lien_site"]
            data["_from_cache"] = True
        else:
            data["website"] = extract_website_from_ads(page_ads.get(pid, []))
            data["_from_cache"] = False

        if i % 10 == 0:
            tracker.update_step("Extraction URL", i + 1, len(pages_filtered))

    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    cached_sites = sum(1 for d in pages_filtered.values() if d.get("_from_cache"))

    phase3_stats = {
        "Sites trouvés": sites_found,
        "Sites en cache": cached_sites,
        "Nouveaux sites": sites_found - cached_sites,
    }
    tracker.complete_phase(f"{sites_found} sites ({cached_sites} en cache)", stats=phase3_stats)

    # ═══ PHASE 4: Détection CMS (parallèle) ═══
    tracker.start_phase(4, "Détection CMS", total_phases=8)
    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}

    pages_need_cms = []
    for pid, data in pages_with_sites.items():
        cached = cached_pages.get(str(pid), {})
        if cached.get("cms") and cached["cms"] not in ("Unknown", "Inconnu", "") and not cached.get("needs_rescan"):
            data["cms"] = cached["cms"]
            data["is_shopify"] = cached["cms"] == "Shopify"
            data["_cms_cached"] = True
        else:
            pages_need_cms.append((pid, data))
            data["_cms_cached"] = False

    cms_cached_count = len(pages_with_sites) - len(pages_need_cms)

    def detect_cms_worker(pid_data):
        pid, data = pid_data
        try:
            cms_result = detect_cms_from_url(data["website"])
            return pid, cms_result
        except Exception:
            return pid, {"cms": "Unknown", "is_shopify": False}

    if pages_need_cms:
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(detect_cms_worker, item): item[0] for item in pages_need_cms}
            for future in as_completed(futures):
                pid, cms_result = future.result()
                pages_with_sites[pid]["cms"] = cms_result["cms"]
                pages_with_sites[pid]["is_shopify"] = cms_result.get("is_shopify", False)
                completed += 1
                if completed % 5 == 0:
                    tracker.update_step("Analyse CMS", completed, len(pages_need_cms))

    # Filtrer par CMS
    def cms_matches(cms_name):
        if cms_name in cms_filter:
            return True
        if "Autre/Inconnu" in cms_filter and cms_name not in cms_options[:-1]:
            return True
        return False

    pages_with_cms = {pid: data for pid, data in pages_with_sites.items() if cms_matches(data.get("cms", "Unknown"))}

    # Compter les CMS
    all_cms_counts = {}
    for pid, data in pages_with_sites.items():
        cms_name = data.get("cms", "Unknown")
        all_cms_counts[cms_name] = all_cms_counts.get(cms_name, 0) + 1

    phase4_stats = {
        "Pages analysées": len(pages_with_sites),
        "CMS en cache": cms_cached_count,
        "CMS détectés": len(pages_need_cms),
        "Pages CMS sélectionnés": len(pages_with_cms),
    }
    tracker.complete_phase(f"{len(pages_with_cms)} pages avec CMS sélectionnés", stats=phase4_stats)

    # ═══ PHASE 5: Comptage des annonces ═══
    tracker.start_phase(5, "Comptage des annonces", total_phases=8)

    page_ids_list = list(pages_with_cms.keys())
    batch_size = 10
    total_batches = (len(page_ids_list) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(page_ids_list), batch_size):
        batch_pids = page_ids_list[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        tracker.update_step("Batch API", batch_num, total_batches)

        batch_results = client.fetch_ads_for_pages_batch(batch_pids, countries_list, languages_list)

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

    pages_final = {pid: data for pid, data in pages_with_cms.items() if data["ads_active_total"] >= ads_min}

    # Calculer les états
    def get_etat_from_ads_count(count):
        if count >= 50:
            return "XXL"
        elif count >= 30:
            return "XL"
        elif count >= 20:
            return "L"
        elif count >= 10:
            return "M"
        elif count >= 5:
            return "S"
        else:
            return "XS"

    etat_counts = {}
    for data in pages_final.values():
        etat = get_etat_from_ads_count(data.get("ads_active_total", 0))
        etat_counts[etat] = etat_counts.get(etat, 0) + 1

    phase5_stats = {
        "Pages comptées": len(pages_with_cms),
        "Pages finales": len(pages_final),
    }
    for etat in ["XXL", "XL", "L", "M", "S", "XS"]:
        if etat in etat_counts:
            phase5_stats[f"État {etat}"] = etat_counts[etat]

    tracker.complete_phase(f"{len(pages_final)} pages finales", stats=phase5_stats)

    if not pages_final:
        update_search_log(db, log_id, status="no_results",
                         total_ads_found=len(all_ads),
                         total_pages_found=len(pages),
                         pages_after_filter=len(pages_filtered))
        return {"search_log_id": log_id, "status": "no_results", "pages": 0}

    # ═══ PHASE 6: Analyse sites web (parallèle) ═══
    tracker.start_phase(6, "Analyse sites web", total_phases=8)
    web_results = {}

    pages_need_analysis = []
    for pid, data in pages_final.items():
        cached = cached_pages.get(str(pid), {})
        # Vérifier si le cache a du contenu pour classification Gemini
        has_classification_content = (
            cached.get("site_title") or
            cached.get("site_description") or
            cached.get("site_h1")
        )

        if not cached.get("needs_rescan") and cached.get("nombre_produits") is not None and has_classification_content:
            # Page en cache AVEC contenu de classification
            web_results[pid] = {
                "product_count": cached.get("nombre_produits", 0),
                "theme": cached.get("template", ""),
                "category": cached.get("thematique", ""),
                "currency_from_site": cached.get("devise", ""),
                # Données pour classification Gemini (depuis le cache)
                "site_title": cached.get("site_title", ""),
                "site_description": cached.get("site_description", ""),
                "site_h1": cached.get("site_h1", ""),
                "site_keywords": cached.get("site_keywords", ""),
                "_from_cache": True
            }
            if cached.get("devise") and not data.get("currency"):
                data["currency"] = cached["devise"]
        elif data.get("website"):
            # Page sans contenu de classification OU qui nécessite un rescan
            pages_need_analysis.append((pid, data))

    cached_analysis = len(web_results)

    def analyze_web_worker(pid_data):
        pid, data = pid_data
        try:
            result = analyze_website_complete(data["website"], countries_list[0] if countries_list else "FR")
            return pid, result
        except Exception as e:
            return pid, {"product_count": 0, "error": str(e)}

    if pages_need_analysis:
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_web_worker, item): item[0] for item in pages_need_analysis}
            for future in as_completed(futures):
                pid, result = future.result()
                web_results[pid] = result
                data = pages_final[pid]
                if not data.get("currency") and result.get("currency_from_site"):
                    data["currency"] = result["currency_from_site"]
                completed += 1
                if completed % 5 == 0:
                    tracker.update_step("Analyse web", completed, len(pages_need_analysis))

    # ═══ Classification Gemini (intégrée à la phase 6) ═══
    classified_count = 0
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if gemini_key and web_results:
        tracker.update_step("Classification Gemini", 0, 1)

        try:
            from app.gemini_classifier import classify_pages_batch

            # Préparer les données pour classification
            pages_to_classify = []
            for pid, web_data in web_results.items():
                # Ne classifier que les pages avec du contenu extrait
                if web_data.get("site_title") or web_data.get("site_description") or web_data.get("site_h1"):
                    pages_to_classify.append({
                        "page_id": pid,
                        "url": pages_final.get(pid, {}).get("website", ""),
                        "site_title": web_data.get("site_title", ""),
                        "site_description": web_data.get("site_description", ""),
                        "site_h1": web_data.get("site_h1", ""),
                        "site_keywords": web_data.get("site_keywords", "")
                    })

            if pages_to_classify:
                # Classifier et stocker les résultats dans web_results
                classification_results = classify_pages_batch(db, pages_to_classify)

                for pid, classification in classification_results.items():
                    if pid in web_results:
                        web_results[pid]["gemini_category"] = classification.get("category", "")
                        web_results[pid]["gemini_subcategory"] = classification.get("subcategory", "")
                        web_results[pid]["gemini_confidence"] = classification.get("confidence", 0.0)

                classified_count = len(classification_results)
                print(f"[Search #{search_id}] Classification Gemini: {classified_count} pages")

        except Exception as e:
            print(f"[Search #{search_id}] Erreur classification Gemini: {e}")

    phase6_stats = {
        "Sites analysés": len(web_results),
        "En cache": cached_analysis,
        "Nouvelles analyses": len(pages_need_analysis),
        "Classifiées (Gemini)": classified_count,
    }
    tracker.complete_phase(f"{len(web_results)} sites, {classified_count} classifiées", stats=phase6_stats)

    # ═══ PHASE 7: Détection des Winning Ads ═══
    tracker.start_phase(7, "Détection Winning Ads", total_phases=8)
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
                    "age_days": age_days,
                    "reach": reach,
                    "matched_criteria": matched_criteria
                })
                page_winning_count += 1
            total_ads_checked += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

    # Compter par critère
    criteria_counts = {}
    for w in winning_ads_data:
        criteria = w.get("matched_criteria", "Unknown")
        criteria_counts[criteria] = criteria_counts.get(criteria, 0) + 1

    phase7_stats = {
        "Ads analysées": total_ads_checked,
        "Winning ads": len(winning_ads_data),
        "Pages avec winning": len(winning_ads_by_page),
    }
    tracker.complete_phase(f"{len(winning_ads_data)} winning ads", stats=phase7_stats)
    tracker.update_metric("winning_ads_count", len(winning_ads_data))

    # ═══ PHASE 8: Sauvegarde ═══
    tracker.start_phase(8, "Sauvegarde", total_phases=8)

    pages_saved = 0
    suivi_saved = 0
    ads_saved = 0
    winning_saved = 0
    winning_skipped = 0

    try:
        # D'abord, vérifier quelles pages existent déjà (pour l'historique)
        from app.database import PageRecherche, WinningAds
        existing_page_ids = set()
        existing_ad_ids = set()

        with db.get_session() as session:
            # Récupérer les page_ids existants
            page_ids_to_check = list(pages_final.keys())
            if page_ids_to_check:
                existing_pages = session.query(PageRecherche.page_id).filter(
                    PageRecherche.page_id.in_([str(pid) for pid in page_ids_to_check])
                ).all()
                existing_page_ids = {p.page_id for p in existing_pages}

            # Récupérer les ad_ids existants pour les winning ads
            ad_ids_to_check = [str(data.get("ad", {}).get("id", "")) for data in winning_ads_data if data.get("ad", {}).get("id")]
            if ad_ids_to_check:
                existing_ads = session.query(WinningAds.ad_id).filter(
                    WinningAds.ad_id.in_(ad_ids_to_check)
                ).all()
                existing_ad_ids = {a.ad_id for a in existing_ads}

        tracker.update_step("Sauvegarde pages", 1, 5)
        pages_saved = save_pages_recherche(db, pages_final, web_results, countries_list, languages_list, None, log_id)

        tracker.update_step("Sauvegarde suivi", 2, 5)
        suivi_saved = save_suivi_page(db, pages_final, web_results, MIN_ADS_SUIVI)

        tracker.update_step("Sauvegarde annonces", 3, 5)
        ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries_list, MIN_ADS_LISTE)

        tracker.update_step("Sauvegarde winning ads", 4, 5)
        winning_saved, winning_skipped = save_winning_ads(db, winning_ads_data, pages_final, log_id)

        # ═══ Enregistrer l'historique de recherche ═══
        tracker.update_step("Historique recherche", 5, 5)

        # Préparer les données d'historique pour les pages
        pages_history_data = []
        for pid, data in pages_final.items():
            pid_str = str(pid)
            # Trouver le keyword qui a trouvé cette page
            keyword = None
            for ad in data.get("_ads", []):
                if ad.get("_keyword"):
                    keyword = ad.get("_keyword")
                    break

            pages_history_data.append({
                "page_id": pid_str,
                "was_new": pid_str not in existing_page_ids,
                "ads_count": data.get("ads_active_total", 0),
                "keyword": keyword
            })

        # Préparer les données d'historique pour les winning ads
        winning_history_data = []
        for data in winning_ads_data:
            ad = data.get("ad", {})
            ad_id = str(ad.get("id", ""))
            if ad_id:
                winning_history_data.append({
                    "ad_id": ad_id,
                    "was_new": ad_id not in existing_ad_ids,
                    "reach": data.get("reach", 0),
                    "age_days": data.get("age_days", 0),
                    "matched_criteria": data.get("matched_criteria", "")
                })

        # Enregistrer l'historique
        pages_history_count = record_pages_search_history_batch(db, log_id, pages_history_data)
        winning_history_count = record_winning_ads_search_history_batch(db, log_id, winning_history_data)

        new_pages_count = sum(1 for d in pages_history_data if d.get("was_new"))
        new_winning_count = sum(1 for d in winning_history_data if d.get("was_new"))

        phase8_stats = {
            "Pages sauvées": pages_saved,
            "Nouvelles pages": new_pages_count,
            "Pages existantes": pages_saved - new_pages_count,
            "Suivi pages": suivi_saved,
            "Annonces sauvées": ads_saved,
            "Winning ads sauvées": winning_saved,
            "Nouvelles winning": new_winning_count,
        }
        tracker.complete_phase(f"{pages_saved} pages ({new_pages_count} new), {winning_saved} winning ({new_winning_count} new)", stats=phase8_stats)

    except Exception as e:
        print(f"[Search #{search_id}] Erreur sauvegarde: {e}")
        update_search_log(db, log_id, status="failed", error_message=str(e))
        raise

    # Finaliser le log
    api_metrics = api_tracker.get_api_metrics_for_log()
    update_search_log(
        db, log_id,
        status="completed",
        total_ads_found=len(all_ads),
        total_pages_found=len(pages),
        pages_after_filter=len(pages_filtered),
        winning_ads_count=len(winning_ads_data),
        pages_saved=pages_saved,
        ads_saved=ads_saved,
        phases_data=tracker.get_phases_data(),
        **api_metrics
    )

    print(f"[Search #{search_id}] Terminée: {pages_saved} pages, {ads_saved} ads, {winning_saved} winning, {classified_count} classifiées")

    return {
        "search_log_id": log_id,
        "status": "completed",
        "pages": pages_saved,
        "ads": ads_saved,
        "winning": winning_saved,
        "classified": classified_count,
        "phases_data": tracker.get_phases_data()
    }
