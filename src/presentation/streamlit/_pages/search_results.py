"""
Module d'affichage des resultats de recherche.

Ce module gere l'affichage et la sauvegarde des resultats
de recherche en mode apercu.

Fonctions:
----------
- render_preview_results: Affichage interactif des resultats
- format_state_for_df: Formatage de l'etat pour dataframes
"""
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database

# Design System imports
from src.presentation.streamlit.ui import (
    section_header, alert, empty_state,
    kpi_row, format_number,
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext
from src.infrastructure.persistence.database import (
    add_to_blacklist,
    save_pages_recherche, save_suivi_page, save_ads_recherche, save_winning_ads,
)
from src.infrastructure.config import MIN_ADS_SUIVI, MIN_ADS_LISTE


def format_state_for_df(etat: str) -> str:
    """
    Formate l'etat pour l'affichage dans un dataframe.

    Args:
        etat: Code de l'etat (XXL, XL, L, M, S, XS, inactif)

    Returns:
        Libelle formate avec plage de valeurs
    """
    state_colors = {
        "XXL": "XXL (80+)",
        "XL": "XL (40-79)",
        "L": "L (20-39)",
        "M": "M (10-19)",
        "S": "S (5-9)",
        "XS": "XS (1-4)",
        "inactif": "Inactif"
    }
    return state_colors.get(etat, etat)


def render_preview_results():
    """
    Affiche les resultats en mode apercu.

    Permet de:
    - Visualiser les pages, ads et winning ads trouvees
    - Blacklister des pages avant sauvegarde
    - Sauvegarder en base de donnees
    - Relancer une nouvelle recherche
    """
    section_header("Apercu des resultats", icon="📋")
    alert("Mode apercu active - Les donnees ne sont pas encore enregistrees", variant="warning")

    db = get_database()
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid
    pages_final = st.session_state.get("pages_final", {})
    web_results = st.session_state.get("web_results", {})
    winning_ads_data = st.session_state.get("winning_ads_data", [])
    countries = st.session_state.get("countries", ["FR"])

    if not pages_final:
        empty_state(
            title="Aucun resultat a afficher",
            description="Lancez une nouvelle recherche pour voir des resultats.",
            icon="📋"
        )
        if st.button("🔙 Nouvelle recherche"):
            st.session_state.show_preview_results = False
            st.rerun()
        return

    # Compter winning ads par page
    winning_by_page = {}
    for w in winning_ads_data:
        wpid = w.get("page_id")
        winning_by_page[wpid] = winning_by_page.get(wpid, 0) + 1

    # Recuperer les ads
    page_ads = st.session_state.get("page_ads", {})

    # Statistiques globales avec Design System
    total_winning = len(winning_ads_data)
    total_ads = sum(d.get('ads_active_total', 0) for d in pages_final.values())

    preview_kpis = [
        {"label": "Pages", "value": format_number(len(pages_final)), "icon": "📊"},
        {"label": "Ads totales", "value": format_number(total_ads), "icon": "📢"},
        {"label": "Winning Ads", "value": format_number(total_winning), "icon": "🏆"},
        {"label": "Pages avec Winning", "value": format_number(len(winning_by_page)), "icon": "📈"},
    ]
    kpi_row(preview_kpis, columns=4)

    # ═══ 4 ONGLETS POUR LES DIFFERENTES DONNEES ═══
    tab_pages, tab_ads, tab_winning, tab_pages_winning = st.tabs([
        f"📊 Pages ({len(pages_final)})",
        f"📢 Ads ({total_ads})",
        f"🏆 Winning Ads ({total_winning})",
        f"📈 Pages avec Winning ({len(winning_by_page)})"
    ])

    # TAB 1: PAGES
    with tab_pages:
        pages_data = []
        for pid, data in pages_final.items():
            web = web_results.get(pid, {})
            winning_count = winning_by_page.get(pid, 0)

            pages_data.append({
                "Page ID": str(pid),
                "Nom": data.get('page_name', 'N/A'),
                "Site": data.get('website', ''),
                "CMS": data.get('cms', 'N/A'),
                "Etat": data.get('etat', 'N/A'),
                "Ads": data.get('ads_active_total', 0),
                "🏆": winning_count,
                "Produits": web.get('product_count', 0),
                "Thematique": web.get('category', '') or web.get('gemini_category', ''),
                "Classification": web.get('gemini_subcategory', ''),
            })

        if pages_data:
            df_pages = pd.DataFrame(pages_data)
            df_pages["Etat"] = df_pages["Etat"].apply(lambda x: format_state_for_df(x) if x else "")

            st.dataframe(
                df_pages,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Site": st.column_config.LinkColumn("Site"),
                    "Page ID": st.column_config.TextColumn("Page ID", width="small"),
                }
            )

    # TAB 2: ADS TOTALES
    with tab_ads:
        ads_data = []
        for pid, data in pages_final.items():
            ads_list = page_ads.get(pid, [])
            for ad in ads_list:
                ad_text = ""
                if ad.get('ad_creative_bodies'):
                    bodies = ad.get('ad_creative_bodies')
                    ad_text = (bodies[0] if isinstance(bodies, list) else bodies)[:100]

                ads_data.append({
                    "Ad ID": ad.get('id', ''),
                    "Page": data.get('page_name', 'N/A'),
                    "Page ID": str(pid),
                    "Reach": ad.get('eu_total_reach', 0),
                    "Creation": ad.get('ad_creation_time', '')[:10] if ad.get('ad_creation_time') else '',
                    "Texte": ad_text,
                    "URL": ad.get('ad_snapshot_url', ''),
                })

        if ads_data:
            df_ads = pd.DataFrame(ads_data)
            st.dataframe(
                df_ads,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn("URL"),
                    "Ad ID": st.column_config.TextColumn("Ad ID", width="small"),
                    "Page ID": st.column_config.TextColumn("Page ID", width="small"),
                }
            )
        else:
            st.info("Aucune ad detaillee disponible")

    # TAB 3: WINNING ADS
    with tab_winning:
        winning_data = []
        for w in winning_ads_data:
            ad = w.get('ad', {})
            ad_text = ""
            if ad and ad.get('ad_creative_bodies'):
                bodies = ad.get('ad_creative_bodies')
                ad_text = (bodies[0] if isinstance(bodies, list) else bodies)[:100]

            winning_data.append({
                "Ad ID": ad.get('id', '') if ad else '',
                "Page": w.get('page_name', '') or pages_final.get(w.get('page_id'), {}).get('page_name', 'N/A'),
                "Page ID": str(w.get('page_id', '')),
                "Reach": w.get('reach', 0),
                "Age (j)": w.get('age_days', 0),
                "Critere": w.get('matched_criteria', ''),
                "Texte": ad_text,
                "URL": ad.get('ad_snapshot_url', '') if ad else '',
            })

        if winning_data:
            df_winning = pd.DataFrame(winning_data)
            st.dataframe(
                df_winning,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn("URL"),
                    "Ad ID": st.column_config.TextColumn("Ad ID", width="small"),
                    "Page ID": st.column_config.TextColumn("Page ID", width="small"),
                }
            )
        else:
            st.info("Aucune winning ad trouvee")

    # TAB 4: PAGES AVEC WINNING
    with tab_pages_winning:
        pages_winning_data = []
        for pid, count in sorted(winning_by_page.items(), key=lambda x: -x[1]):
            data = pages_final.get(pid, {})
            web = web_results.get(pid, {})

            pages_winning_data.append({
                "Page ID": str(pid),
                "Nom": data.get('page_name', 'N/A'),
                "Site": data.get('website', ''),
                "🏆 Winning": count,
                "Ads Totales": data.get('ads_active_total', 0),
                "CMS": data.get('cms', 'N/A'),
                "Etat": data.get('etat', 'N/A'),
                "Produits": web.get('product_count', 0),
            })

        if pages_winning_data:
            df_pages_winning = pd.DataFrame(pages_winning_data)
            df_pages_winning["Etat"] = df_pages_winning["Etat"].apply(lambda x: format_state_for_df(x) if x else "")

            st.dataframe(
                df_pages_winning,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Site": st.column_config.LinkColumn("Site"),
                    "Page ID": st.column_config.TextColumn("Page ID", width="small"),
                }
            )
        else:
            st.info("Aucune page avec winning ads")

    st.markdown("---")

    # Actions de blacklist (expandable)
    with st.expander("🚫 Actions de blacklist par page"):
        for pid, data in list(pages_final.items()):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{data.get('page_name', 'N/A')}** ({pid})")
            with col2:
                if st.button("🚫", key=f"bl_preview_{pid}", help="Blacklister cette page"):
                    if db and add_to_blacklist(db, pid, data.get("page_name", ""), "Blackliste depuis apercu", user_id=user_id):
                        del st.session_state.pages_final[pid]
                        if pid in st.session_state.web_results:
                            del st.session_state.web_results[pid]
                        st.rerun()

    st.markdown("---")

    # Boutons d'action
    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Sauvegarder en base de donnees", type="primary", use_container_width=True):
            if db:
                try:
                    thresholds = st.session_state.get("state_thresholds", None)
                    languages = st.session_state.get("languages", ["fr"])
                    search_log_id = st.session_state.get("search_log_id")
                    pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds, search_log_id, user_id=user_id)
                    det = st.session_state.get("detection_thresholds", {})
                    suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI), user_id=user_id)
                    ads_saved = save_ads_recherche(db, pages_final, st.session_state.get("page_ads", {}), countries, det.get("min_ads_liste", MIN_ADS_LISTE), user_id=user_id)
                    winning_ads_data = st.session_state.get("winning_ads_data", [])
                    winning_saved, winning_new, winning_updated = save_winning_ads(db, winning_ads_data, search_log_id, user_id=user_id)

                    # Mettre a jour le search_log avec les IDs JSON pour l'historique
                    if search_log_id:
                        import json
                        from src.infrastructure.persistence.database import update_search_log
                        page_ids_list = [str(pid) for pid in pages_final.keys()]
                        winning_ad_ids_list = [str(data.get("ad", {}).get("id", "")) for data in winning_ads_data if data.get("ad", {}).get("id")]
                        update_search_log(
                            db, search_log_id,
                            status="completed",
                            page_ids=json.dumps(page_ids_list),
                            winning_ad_ids=json.dumps(winning_ad_ids_list),
                            pages_saved=pages_saved,
                            winning_ads_count=len(winning_ads_data)
                        )

                    msg = f"✅ Sauvegarde : {pages_saved} pages, {suivi_saved} suivi, {ads_saved} ads, {winning_saved} winning"
                    if winning_updated > 0:
                        msg += f" ({winning_new} 🆕, {winning_updated} 📝)"
                    st.success(msg)
                    st.session_state.show_preview_results = False
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Erreur sauvegarde: {e}")

    with col2:
        if st.button("🔙 Nouvelle recherche", use_container_width=True):
            st.session_state.show_preview_results = False
            st.session_state.pages_final = {}
            st.session_state.web_results = {}
            st.rerun()
