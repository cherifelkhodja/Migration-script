"""
Page Historique des Recherches - Logs detailles de toutes les recherches.
"""
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext


def render_search_logs():
    """Page Historique des Recherches - Logs detailles de toutes les recherches"""
    st.title("📜 Historique des Recherches")
    st.markdown("Consultez l'historique complet de vos recherches avec les metriques detaillees.")

    db = get_database()
    if not db:
        st.error("Base de donnees non connectee")
        return

    # Multi-tenancy: recuperer l'utilisateur courant
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # S'assurer que les migrations sont executees (ajoute les colonnes manquantes)
    from src.infrastructure.persistence.database import ensure_tables_exist
    ensure_tables_exist(db)

    # Import des fonctions de log
    from src.infrastructure.persistence.database import get_search_logs, get_search_logs_stats, delete_search_log

    # Stats globales
    stats = get_search_logs_stats(db, days=30, user_id=user_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Recherches (30j)", stats.get("total_searches", 0))
    with col2:
        completed = stats.get("by_status", {}).get("completed", 0)
        st.metric("Completees", completed)
    with col3:
        avg_duration = stats.get("avg_duration_seconds", 0)
        if avg_duration > 60:
            st.metric("Duree moyenne", f"{avg_duration/60:.1f}m")
        else:
            st.metric("Duree moyenne", f"{avg_duration:.1f}s")
    with col4:
        st.metric("Total pages trouvees", stats.get("total_pages_found", 0))

    # Stats API globales
    total_api = (stats.get("total_meta_api_calls", 0) +
                 stats.get("total_scraper_api_calls", 0) +
                 stats.get("total_web_requests", 0))

    if total_api > 0:
        st.markdown("##### Statistiques API (30 jours)")
        api1, api2, api3, api4, api5 = st.columns(5)
        with api1:
            st.metric("Meta API", stats.get("total_meta_api_calls", 0))
        with api2:
            st.metric("ScraperAPI", stats.get("total_scraper_api_calls", 0))
        with api3:
            st.metric("Web Direct", stats.get("total_web_requests", 0))
        with api4:
            st.metric("Rate Limits", stats.get("total_rate_limit_hits", 0))
        with api5:
            cost = stats.get("total_scraper_api_cost", 0)
            st.metric("Cout ScraperAPI", f"${cost:.2f}")

    st.markdown("---")

    # Filtres
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.selectbox(
            "Filtrer par statut",
            options=["Tous", "completed", "preview", "no_results", "failed", "running"],
            index=0
        )
    with col2:
        limit = st.selectbox("Nombre de resultats", options=[20, 50, 100], index=0)

    # Recuperer les logs
    status_param = None if status_filter == "Tous" else status_filter
    logs = get_search_logs(db, limit=limit, status=status_param, user_id=user_id)

    if not logs:
        st.info("Aucun historique de recherche disponible.")
        return

    st.markdown(f"### {len(logs)} recherche(s)")

    for log in logs:
        _render_single_log(db, log, user_id)


def _render_single_log(db, log: dict, user_id=None):
    """Affiche un log de recherche individuel."""
    log_id = log["id"]
    started = log["started_at"]
    status = log["status"]
    keywords = log["keywords"] or "-"
    duration = log.get("duration_seconds", 0)

    # Status badge
    status_emoji = {
        "completed": "✅",
        "preview": "👁️",
        "failed": "❌",
        "running": "🔄",
        "no_results": "⚠️"
    }.get(status, "❓")

    # Format duration
    if duration:
        if duration > 60:
            duration_str = f"{duration/60:.1f}m"
        else:
            duration_str = f"{duration:.1f}s"
    else:
        duration_str = "-"

    # Format date
    if started:
        date_str = started.strftime("%d/%m/%Y %H:%M")
    else:
        date_str = "-"

    from src.infrastructure.persistence.database import delete_search_log

    with st.expander(f"{status_emoji} **#{log_id}** - {date_str} - {keywords[:50]}{'...' if len(keywords) > 50 else ''} ({duration_str})"):
        # Metriques principales
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Ads trouvees", log.get("total_ads_found", 0))
        with m2:
            st.metric("Pages trouvees", log.get("total_pages_found", 0))
        with m3:
            st.metric("Pages filtrees", log.get("pages_after_filter", 0))
        with m4:
            st.metric("Winning Ads", log.get("winning_ads_count", 0))

        # Tableaux pages et winning ads
        _render_pages_and_winning_ads(db, log_id, user_id=user_id)

        # Parametres de recherche
        st.markdown("**Parametres:**")
        param_cols = st.columns(4)
        with param_cols[0]:
            st.caption(f"📍 Pays: {log.get('countries', '-')}")
        with param_cols[1]:
            st.caption(f"🌐 Langues: {log.get('languages', '-')}")
        with param_cols[2]:
            st.caption(f"📊 Min ads: {log.get('min_ads', '-')}")
        with param_cols[3]:
            st.caption(f"🛍️ CMS: {log.get('selected_cms', '-') or 'Tous'}")

        # Mots-cles complets
        st.markdown("**Mots-cles:**")
        st.code(keywords)

        # Details des phases avec stats
        _render_phases(log)

        # Statistiques API
        _render_api_stats(log)

        # Message d'erreur ou d'avertissement
        _render_status_message(log, status)

        # Details supplementaires
        with st.columns([3, 1])[1]:
            if st.button("🗑️ Supprimer", key=f"del_log_{log_id}"):
                delete_search_log(db, log_id, user_id=user_id)
                st.success("Log supprime")
                st.rerun()


def _render_pages_and_winning_ads(db, log_id: int, user_id=None):
    """Affiche les tableaux des pages et winning ads pour un log."""
    from src.infrastructure.persistence.database import (
        get_pages_for_search, get_winning_ads_for_search,
        get_search_history_stats, PageRecherche, WinningAds
    )
    from src.infrastructure.persistence.models import PageSearchHistory, WinningAdSearchHistory

    # Recuperer les stats d'historique
    history_stats = get_search_history_stats(db, log_id)

    # Tableau des pages trouvees (utilise les tables d'historique many-to-many)
    pages_from_search = get_pages_for_search(db, log_id, limit=100, user_id=user_id)

    # FALLBACK 1: Si pas d'historique, utiliser last_search_log_id
    if not pages_from_search and user_id:
        with db.get_session() as session:
            fallback_pages = session.query(PageRecherche).filter(
                PageRecherche.last_search_log_id == log_id,
                PageRecherche.user_id == user_id
            ).limit(100).all()
            if fallback_pages:
                pages_from_search = [
                    {
                        "page_id": p.page_id,
                        "page_name": p.page_name,
                        "lien_site": p.lien_site,
                        "cms": p.cms,
                        "etat": p.etat,
                        "nombre_ads_active": p.nombre_ads_active,
                        "thematique": p.thematique,
                        "pays": p.pays,
                        "was_new": p.was_created_in_last_search,
                        "ads_count_at_discovery": p.nombre_ads_active,
                        "keyword_matched": None
                    }
                    for p in fallback_pages
                ]

    # FALLBACK 2: Si toujours rien, chercher dans PageSearchHistory sans join
    if not pages_from_search and user_id:
        with db.get_session() as session:
            history_entries = session.query(PageSearchHistory).filter(
                PageSearchHistory.search_log_id == log_id,
                PageSearchHistory.user_id == user_id
            ).limit(100).all()
            if history_entries:
                # Recuperer les infos des pages separement
                page_ids = [h.page_id for h in history_entries]
                pages_dict = {}
                for p in session.query(PageRecherche).filter(
                    PageRecherche.page_id.in_(page_ids),
                    PageRecherche.user_id == user_id
                ).all():
                    pages_dict[p.page_id] = p

                pages_from_search = []
                for h in history_entries:
                    p = pages_dict.get(h.page_id)
                    pages_from_search.append({
                        "page_id": h.page_id,
                        "page_name": p.page_name if p else h.page_id,
                        "lien_site": p.lien_site if p else "",
                        "cms": p.cms if p else "N/A",
                        "etat": p.etat if p else "N/A",
                        "nombre_ads_active": p.nombre_ads_active if p else 0,
                        "thematique": p.thematique if p else "",
                        "pays": p.pays if p else "",
                        "was_new": h.was_new,
                        "ads_count_at_discovery": h.ads_count_at_discovery,
                        "keyword_matched": h.keyword_matched
                    })

    if pages_from_search:
        new_pages = history_stats.get("new_pages", 0)
        existing_pages = history_stats.get("existing_pages", 0)

        with st.expander(f"📄 **Pages trouvees ({len(pages_from_search)})** — 🆕 {new_pages} nouvelles | 📝 {existing_pages} existantes", expanded=False):
            _render_pages_table(pages_from_search, log_id)

    # Tableau des winning ads (utilise les tables d'historique many-to-many)
    winning_from_search = get_winning_ads_for_search(db, log_id, limit=100, user_id=user_id)

    # FALLBACK 1: Si pas d'historique, utiliser search_log_id sur winning_ads
    if not winning_from_search and user_id:
        with db.get_session() as session:
            fallback_winning = session.query(WinningAds).filter(
                WinningAds.search_log_id == log_id,
                WinningAds.user_id == user_id
            ).limit(100).all()
            if fallback_winning:
                winning_from_search = [
                    {
                        "ad_id": w.ad_id,
                        "page_id": w.page_id,
                        "page_name": w.page_name,
                        "lien_site": w.lien_site,
                        "ad_age_days": w.ad_age_days,
                        "eu_total_reach": w.eu_total_reach,
                        "matched_criteria": w.matched_criteria,
                        "ad_snapshot_url": w.ad_snapshot_url,
                        "was_new": w.is_new,
                        "reach_at_discovery": w.eu_total_reach,
                        "age_days_at_discovery": w.ad_age_days
                    }
                    for w in fallback_winning
                ]

    # FALLBACK 2: Si toujours rien, chercher dans WinningAdSearchHistory sans join
    if not winning_from_search and user_id:
        with db.get_session() as session:
            history_entries = session.query(WinningAdSearchHistory).filter(
                WinningAdSearchHistory.search_log_id == log_id,
                WinningAdSearchHistory.user_id == user_id
            ).limit(100).all()
            if history_entries:
                # Recuperer les infos des ads separement
                ad_ids = [h.ad_id for h in history_entries]
                ads_dict = {}
                for w in session.query(WinningAds).filter(
                    WinningAds.ad_id.in_(ad_ids),
                    WinningAds.user_id == user_id
                ).all():
                    ads_dict[w.ad_id] = w

                winning_from_search = []
                for h in history_entries:
                    w = ads_dict.get(h.ad_id)
                    winning_from_search.append({
                        "ad_id": h.ad_id,
                        "page_id": w.page_id if w else "",
                        "page_name": w.page_name if w else h.ad_id,
                        "lien_site": w.lien_site if w else "",
                        "ad_age_days": w.ad_age_days if w else h.age_days_at_discovery,
                        "eu_total_reach": w.eu_total_reach if w else h.reach_at_discovery,
                        "matched_criteria": h.matched_criteria or (w.matched_criteria if w else ""),
                        "ad_snapshot_url": w.ad_snapshot_url if w else "",
                        "was_new": h.was_new,
                        "reach_at_discovery": h.reach_at_discovery,
                        "age_days_at_discovery": h.age_days_at_discovery
                    })

    if winning_from_search:
        new_winning = history_stats.get("new_winning_ads", 0)
        existing_winning = history_stats.get("existing_winning_ads", 0)

        with st.expander(f"🏆 **Winning Ads ({len(winning_from_search)})** — 🆕 {new_winning} nouvelles | 📝 {existing_winning} existantes", expanded=False):
            _render_winning_table(winning_from_search, log_id)


def _render_pages_table(pages_from_search: list, log_id: int):
    """Affiche le tableau des pages pour un log."""
    # Selecteur de colonnes
    all_page_columns = ["Status", "Page", "Site", "CMS", "Etat", "Ads", "Thematique", "Pays", "Keyword", "Ads (decouverte)"]
    default_page_cols = ["Status", "Page", "Site", "CMS", "Etat", "Ads"]

    selected_page_cols = st.multiselect(
        "Colonnes a afficher",
        options=all_page_columns,
        default=default_page_cols,
        key=f"page_cols_{log_id}"
    )

    # Creer DataFrame avec toutes les colonnes disponibles
    pages_df_data = []
    for p in pages_from_search:
        row = {}
        if "Status" in selected_page_cols:
            row["Status"] = "🆕 Nouveau" if p.get("was_new") else "📝 Existant"
        if "Page" in selected_page_cols:
            row["Page"] = (p.get("page_name") or "")[:30]
        if "Site" in selected_page_cols:
            row["Site"] = (p.get("lien_site") or "")[:35]
        if "CMS" in selected_page_cols:
            row["CMS"] = p.get("cms", "-")
        if "Etat" in selected_page_cols:
            row["Etat"] = p.get("etat", "-")
        if "Ads" in selected_page_cols:
            row["Ads"] = p.get("nombre_ads_active", 0)
        if "Thematique" in selected_page_cols:
            row["Thematique"] = (p.get("thematique") or "-")[:20]
        if "Pays" in selected_page_cols:
            row["Pays"] = (p.get("pays") or "-")[:15]
        if "Keyword" in selected_page_cols:
            row["Keyword"] = (p.get("keyword_matched") or "-")[:20]
        if "Ads (decouverte)" in selected_page_cols:
            row["Ads (decouverte)"] = p.get("ads_count_at_discovery", 0)

        if row:
            pages_df_data.append(row)

    if pages_df_data:
        df_pages = pd.DataFrame(pages_df_data)
        st.dataframe(df_pages, hide_index=True, use_container_width=True)


def _render_winning_table(winning_from_search: list, log_id: int):
    """Affiche le tableau des winning ads pour un log."""
    # Selecteur de colonnes
    all_winning_columns = ["Status", "Page", "Age", "Reach", "Critere", "Site", "Snapshot", "Reach (decouverte)", "Age (decouverte)"]
    default_winning_cols = ["Status", "Page", "Age", "Reach", "Critere", "Site"]

    selected_winning_cols = st.multiselect(
        "Colonnes a afficher",
        options=all_winning_columns,
        default=default_winning_cols,
        key=f"winning_cols_{log_id}"
    )

    # Creer DataFrame
    winning_df_data = []
    for a in winning_from_search:
        row = {}
        if "Status" in selected_winning_cols:
            row["Status"] = "🆕 Nouveau" if a.get("was_new") else "📝 Existant"
        if "Page" in selected_winning_cols:
            row["Page"] = (a.get("page_name") or "")[:25]
        if "Age" in selected_winning_cols:
            row["Age"] = f"{a.get('ad_age_days', '-')}j" if a.get("ad_age_days") is not None else "-"
        if "Reach" in selected_winning_cols:
            reach = a.get("eu_total_reach")
            row["Reach"] = f"{reach:,}".replace(",", " ") if reach else "-"
        if "Critere" in selected_winning_cols:
            row["Critere"] = a.get("matched_criteria", "-")
        if "Site" in selected_winning_cols:
            row["Site"] = (a.get("lien_site") or "")[:25]
        if "Snapshot" in selected_winning_cols:
            snapshot_url = a.get("ad_snapshot_url", "")
            row["Snapshot"] = "🔗" if snapshot_url else "-"
        if "Reach (decouverte)" in selected_winning_cols:
            reach_d = a.get("reach_at_discovery", 0)
            row["Reach (decouverte)"] = f"{reach_d:,}".replace(",", " ") if reach_d else "-"
        if "Age (decouverte)" in selected_winning_cols:
            row["Age (decouverte)"] = f"{a.get('age_days_at_discovery', '-')}j"

        if row:
            winning_df_data.append(row)

    if winning_df_data:
        df_winning = pd.DataFrame(winning_df_data)
        st.dataframe(df_winning, hide_index=True, use_container_width=True)


def _render_phases(log: dict):
    """Affiche les details des phases de recherche."""
    phases_data = log.get("phases_data", [])
    if not phases_data:
        return

    st.markdown("**📊 Details par phase:**")

    for p in phases_data:
        phase_num = p.get('num', '?')
        phase_name = p.get('name', 'N/A')
        phase_time = p.get("time_formatted", "-")
        phase_result = p.get("result", "-")
        phase_stats = p.get("stats", {})

        # Header de la phase avec expander
        with st.expander(f"**Phase {phase_num}:** {phase_name} — {phase_result} ({phase_time})", expanded=False):
            if phase_stats:
                # Afficher les stats en 2 colonnes
                stat_items = list(phase_stats.items())
                for i in range(0, len(stat_items), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        if i + j < len(stat_items):
                            key, value = stat_items[i + j]
                            with col:
                                # Formater la valeur
                                if isinstance(value, int) and value >= 1000:
                                    display_val = f"{value:,}".replace(",", " ")
                                elif isinstance(value, float):
                                    display_val = f"{value:.1f}"
                                elif isinstance(value, dict):
                                    display_val = ", ".join(f"{k}: {v}" for k, v in value.items())
                                else:
                                    display_val = str(value)
                                st.metric(key, display_val)
            else:
                st.caption("Pas de statistiques detaillees pour cette phase")


def _render_api_stats(log: dict):
    """Affiche les statistiques API."""
    meta_api_calls = log.get("meta_api_calls", 0) or 0
    scraper_api_calls = log.get("scraper_api_calls", 0) or 0
    web_requests = log.get("web_requests", 0) or 0
    total_api_calls = meta_api_calls + scraper_api_calls + web_requests

    if total_api_calls == 0:
        return

    st.markdown("**Statistiques API:**")

    # Ligne 1: Compteurs principaux
    api_cols = st.columns(4)
    with api_cols[0]:
        st.metric("🔗 Meta API", meta_api_calls)
    with api_cols[1]:
        st.metric("🌐 ScraperAPI", scraper_api_calls)
    with api_cols[2]:
        st.metric("📡 Web Direct", web_requests)
    with api_cols[3]:
        st.metric("📊 Total", total_api_calls)

    # Ligne 2: Erreurs et couts
    meta_errors = log.get("meta_api_errors", 0) or 0
    scraper_errors = log.get("scraper_api_errors", 0) or 0
    web_errors = log.get("web_errors", 0) or 0
    rate_limits = log.get("rate_limit_hits", 0) or 0
    scraper_cost = log.get("scraper_api_cost", 0) or 0

    err_cols = st.columns(5)
    with err_cols[0]:
        st.caption(f"❌ Meta erreurs: {meta_errors}")
    with err_cols[1]:
        st.caption(f"❌ Scraper erreurs: {scraper_errors}")
    with err_cols[2]:
        st.caption(f"❌ Web erreurs: {web_errors}")
    with err_cols[3]:
        st.caption(f"⏱️ Rate limits: {rate_limits}")
    with err_cols[4]:
        st.caption(f"💰 Cout ScraperAPI: ${scraper_cost:.4f}")

    # Detail des erreurs scraper par type (si disponibles)
    scraper_errors_by_type = log.get("scraper_errors_by_type")
    if scraper_errors_by_type and isinstance(scraper_errors_by_type, dict) and len(scraper_errors_by_type) > 0:
        error_labels = {
            "timeout": "⏰ Timeout",
            "403_forbidden": "🚫 403 Bloque",
            "404_not_found": "🔍 404 Non trouve",
            "429_rate_limit": "⏱️ 429 Rate limit",
            "500_server_error": "💥 500 Erreur serveur",
            "502_bad_gateway": "🌐 502 Bad Gateway",
            "503_unavailable": "🔧 503 Indisponible",
            "unknown": "❓ Inconnu"
        }
        err_details = []
        for err_type, count in sorted(scraper_errors_by_type.items(), key=lambda x: -x[1]):
            label = error_labels.get(err_type, f"⚠️ {err_type}")
            err_details.append(f"{label}: {count}")
        st.caption("📊 **Detail erreurs scraper:** " + " | ".join(err_details))

    # Liste detaillee des erreurs
    _render_errors_list(log)

    # Ligne 3: Temps moyens
    meta_avg = log.get("meta_api_avg_time", 0) or 0
    scraper_avg = log.get("scraper_api_avg_time", 0) or 0
    web_avg = log.get("web_avg_time", 0) or 0

    time_cols = st.columns(3)
    with time_cols[0]:
        st.caption(f"⏱️ Meta avg: {meta_avg:.0f}ms")
    with time_cols[1]:
        st.caption(f"⏱️ Scraper avg: {scraper_avg:.0f}ms")
    with time_cols[2]:
        st.caption(f"⏱️ Web avg: {web_avg:.0f}ms")

    # Details par mot-cle (si disponibles)
    api_details = log.get("api_details")
    if api_details and isinstance(api_details, dict) and len(api_details) > 0:
        with st.expander("📋 Details par mot-cle"):
            details_table = []
            for kw, kw_stats in api_details.items():
                details_table.append({
                    "Mot-cle": kw[:30] + "..." if len(kw) > 30 else kw,
                    "Appels": kw_stats.get("calls", 0),
                    "Ads": kw_stats.get("ads_found", 0),
                    "Erreurs": kw_stats.get("errors", 0),
                    "Temps (ms)": f"{kw_stats.get('time_ms', 0):.0f}"
                })
            if details_table:
                df_details = pd.DataFrame(details_table)
                st.dataframe(df_details, hide_index=True, width="stretch")


def _render_errors_list(log: dict):
    """Affiche la liste detaillee des erreurs."""
    errors_list = log.get("errors_list", [])
    if not errors_list or len(errors_list) == 0:
        return

    # Si errors_list est une string JSON, la parser
    if isinstance(errors_list, str):
        try:
            import json
            errors_list = json.loads(errors_list)
        except:
            errors_list = [{"type": "unknown", "message": errors_list}]

    # Si les erreurs sont des strings simples, les convertir en dicts
    if errors_list and isinstance(errors_list[0], str):
        errors_list = [{"type": "unknown", "message": err} for err in errors_list]

    with st.expander(f"🚨 **{len(errors_list)} erreur(s) detaillee(s)**", expanded=False):
        # Grouper par type d'erreur
        errors_by_type = {}
        for err in errors_list:
            if isinstance(err, dict):
                err_type = err.get("type", "unknown")
            else:
                err_type = "unknown"
                err = {"type": "unknown", "message": str(err)}
            if err_type not in errors_by_type:
                errors_by_type[err_type] = []
            errors_by_type[err_type].append(err)

        # Afficher par type
        type_icons = {
            "meta_api": "🔵 Meta API",
            "scraper_api": "🟠 ScraperAPI",
            "web": "🌐 Web",
            "rate_limit": "⏱️ Rate Limit",
            "unknown": "❓ Autre"
        }

        for err_type, errs in errors_by_type.items():
            type_label = type_icons.get(err_type, f"⚠️ {err_type}")
            st.markdown(f"**{type_label}** ({len(errs)})")

            for err in errs[:10]:  # Limiter a 10 par type
                timestamp = err.get("timestamp", "")
                message = err.get("message", "Erreur inconnue")[:200]
                keyword = err.get("keyword", "")
                url = err.get("url", "")

                details = []
                if keyword:
                    details.append(f"Mot-cle: {keyword}")
                if url:
                    details.append(f"URL: {url[:50]}...")
                if timestamp:
                    details.append(f"A: {timestamp}")

                st.error(f"❌ {message}")
                if details:
                    st.caption(" | ".join(details))

            if len(errs) > 10:
                st.caption(f"... et {len(errs) - 10} autres erreurs de ce type")


def _render_status_message(log: dict, status: str):
    """Affiche le message d'erreur ou d'avertissement."""
    if status == "failed" and log.get("error_message"):
        st.error(f"Erreur: {log.get('error_message')}")
    elif status == "no_results":
        # Afficher la raison pour les recherches sans resultats
        error_msg = log.get("error_message")
        if error_msg:
            st.warning(f"⚠️ {error_msg}")
        else:
            # Message par defaut si pas d'erreur specifique
            total_ads = log.get("total_ads_found", 0)
            pages_found = log.get("total_pages_found", 0)
            pages_filtered = log.get("pages_after_filter", 0)
            min_ads = log.get("min_ads", 0)

            if total_ads == 0:
                st.warning("⚠️ Aucune publicite trouvee pour ces mots-cles dans les pays/langues selectionnes")
            elif pages_found == 0:
                st.warning("⚠️ Publicites trouvees mais aucune page n'a pu etre extraite")
            elif pages_filtered == 0:
                st.warning(f"⚠️ {pages_found} pages trouvees mais aucune ne correspond aux filtres (min {min_ads} ads, CMS: {log.get('selected_cms', 'Tous')})")
