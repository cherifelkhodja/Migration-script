"""
Page Pages/Shops - Exploration et gestion des pages Facebook.

Ce module est le centre de gestion des pages detectees. Il permet
d'explorer, filtrer, scorer et organiser toutes les pages en base.

Systeme de Score (0-100 points):
--------------------------------
Le score de performance est calcule ainsi :
- **Ads actives** (max 40pts) :
  - >=150 ads : 40pts | >=80 : 35pts | >=35 : 25pts
  - >=20 : 15pts | >=10 : 10pts | >=1 : 5pts
- **Winning Ads** (max 30pts) :
  - >=10 winning : 30pts | >=5 : 25pts | >=3 : 20pts | >=1 : 15pts
- **Produits** (max 20pts) :
  - >=100 : 20pts | >=50 : 15pts | >=20 : 10pts | >=5 : 5pts
- **Bonus CMS** : Shopify = +10pts

Indicateurs visuels : 🟢 (>=80), 🟡 (>=60), 🟠 (>=40), 🔴 (<40)

Filtres disponibles:
--------------------
- Page ID : Recherche exacte par identifiant
- Recherche texte : Nom ou site (fuzzy)
- CMS : Shopify, WooCommerce, PrestaShop, Magento, Wix
- Etat : XXL, XL, L, M, S, XS, inactif
- Thematique/Classification : Taxonomie Gemini
- Pays : Filtrage geographique
- Limite : 50 a 500 resultats

Filtres sauvegardes:
--------------------
Possibilite de sauvegarder/charger des combinaisons de filtres
pour reutilisation rapide.

Modes d'affichage:
------------------
1. **Tableau** : Vue compacte avec colonnes configurables
2. **Detaille** : Expanders avec toutes les infos + actions
3. **Selection** : Mode checkbox pour actions groupees

Actions groupees (mode Selection):
----------------------------------
- Ajouter aux favoris
- Blacklister
- Ajouter a une collection
- Appliquer un tag

Actions individuelles (mode Detaille):
--------------------------------------
- Toggle favori
- Lien Ads Library
- Ajout a collection
- Ajout de tag
- Notes personnalisees
- Modification de classification
- Blacklist

Export CSV:
-----------
Colonnes personnalisables :
Page ID, Nom, Site, CMS, Etat, Ads, Winning, Produits, Score,
Dernier Scan, Thematique, Sous-categorie, Ads Library, Page Facebook
"""
from datetime import datetime
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import export_to_csv
from src.infrastructure.persistence.database import (
    search_pages, get_winning_ads_count_by_page,
    get_saved_filters, save_filter, delete_saved_filter,
    get_taxonomy_categories, get_all_subcategories, get_all_countries,
    get_collections, add_page_to_collection,
    get_all_tags, add_tag_to_page, get_page_tags,
    get_page_notes, add_page_note,
    is_favorite, toggle_favorite,
    add_to_blacklist,
    bulk_add_to_blacklist, bulk_add_to_collection, bulk_add_tag, bulk_add_to_favorites,
    update_page_classification
)


def calculate_page_score(page: dict, winning_count: int = 0) -> int:
    """Calcule un score de performance pour une page (0-100)."""
    score = 0
    ads = page.get("nombre_ads_active", 0) or 0
    produits = page.get("nombre_produits", 0) or 0
    cms = page.get("cms", "")

    # Points pour ads actives (max 40)
    if ads >= 150:
        score += 40
    elif ads >= 80:
        score += 35
    elif ads >= 35:
        score += 25
    elif ads >= 20:
        score += 15
    elif ads >= 10:
        score += 10
    elif ads >= 1:
        score += 5

    # Points pour winning ads (max 30)
    if winning_count >= 10:
        score += 30
    elif winning_count >= 5:
        score += 25
    elif winning_count >= 3:
        score += 20
    elif winning_count >= 1:
        score += 15

    # Points pour produits (max 20)
    if produits >= 100:
        score += 20
    elif produits >= 50:
        score += 15
    elif produits >= 20:
        score += 10
    elif produits >= 5:
        score += 5

    # Bonus CMS Shopify (+10)
    if cms and "shopify" in cms.lower():
        score += 10

    return min(score, 100)


def get_score_color(score: int) -> str:
    """Retourne un emoji/indicateur de couleur pour le score."""
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    else:
        return "🔴"


def format_state_for_df(etat: str) -> str:
    """Formate l'etat pour affichage dans DataFrame."""
    state_badges = {
        "XXL": "🔥 XXL",
        "XL": "⭐ XL",
        "L": "📈 L",
        "M": "📊 M",
        "S": "📉 S",
        "XS": "💤 XS",
        "inactif": "⚫ Inactif"
    }
    return state_badges.get(etat, etat)


def render_pages_shops():
    """Page Pages/Shops - Liste des pages avec score et export"""
    st.title("🏪 Pages / Shops")
    st.markdown("Explorer toutes les pages et boutiques")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Initialiser les pages selectionnees dans session_state
    if 'selected_pages' not in st.session_state:
        st.session_state.selected_pages = []

    # Filtres sauvegardes
    saved_filters = get_saved_filters(db, filter_type="pages")

    col_saved, col_save_btn = st.columns([4, 1])
    with col_saved:
        filter_options = ["-- Filtres sauvegardes --"] + [f["name"] for f in saved_filters]
        selected_saved = st.selectbox("📂 Charger un filtre", filter_options, key="load_filter")

    # Charger le filtre selectionne
    loaded_filter = None
    if selected_saved != "-- Filtres sauvegardes --":
        for f in saved_filters:
            if f["name"] == selected_saved:
                loaded_filter = f["filters"]
                break

    # Filtres
    st.markdown("#### 🔍 Filtres")

    # Ligne 0: Filtre par ID
    col_id1, col_id2 = st.columns([3, 1])
    with col_id1:
        default_page_id = loaded_filter.get("page_id", "") if loaded_filter else ""
        page_id_filter = st.text_input(
            "🆔 Page ID",
            value=default_page_id,
            placeholder="Ex: 123456789012345",
            help="Filtrer par ID de page specifique"
        )

    # Ligne 1: Recherche, CMS, Etat
    col1, col2, col3 = st.columns(3)

    with col1:
        default_search = loaded_filter.get("search_term", "") if loaded_filter else ""
        search_term = st.text_input("🔍 Rechercher", value=default_search, placeholder="Nom ou site...")

    with col2:
        cms_options = ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"]
        default_cms = loaded_filter.get("cms", "Tous") if loaded_filter else "Tous"
        cms_idx = cms_options.index(default_cms) if default_cms in cms_options else 0
        cms_filter = st.selectbox("CMS", cms_options, index=cms_idx)

    with col3:
        etat_options = ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"]
        default_etat = loaded_filter.get("etat", "Tous") if loaded_filter else "Tous"
        etat_idx = etat_options.index(default_etat) if default_etat in etat_options else 0
        etat_filter = st.selectbox("Etat", etat_options, index=etat_idx)

    # Ligne 2: Classification
    col4, col5, col6, col7 = st.columns(4)

    with col4:
        thematique_options = ["Toutes", "Non classifiees"] + get_taxonomy_categories(db)
        thematique_filter = st.selectbox("Thematique", thematique_options, index=0, key="pages_thematique")

    with col5:
        if thematique_filter not in ["Toutes", "Non classifiees"]:
            subcategory_options = ["Toutes"] + get_all_subcategories(db, category=thematique_filter)
        else:
            subcategory_options = ["Toutes"] + get_all_subcategories(db)
        subcategory_filter = st.selectbox("Classification", subcategory_options, index=0, key="pages_subcategory")

    with col6:
        countries = get_all_countries(db)
        country_names = {
            "FR": "🇫🇷 France", "DE": "🇩🇪 Allemagne", "ES": "🇪🇸 Espagne",
            "IT": "🇮🇹 Italie", "GB": "🇬🇧 UK", "US": "🇺🇸 USA",
            "BE": "🇧🇪 Belgique", "CH": "🇨🇭 Suisse", "NL": "🇳🇱 Pays-Bas",
        }
        pays_display = ["Tous"] + [country_names.get(c, c) for c in countries]
        pays_values = [None] + countries
        pays_idx = st.selectbox(
            "🌍 Pays",
            range(len(pays_display)),
            format_func=lambda i: pays_display[i],
            index=0,
            key="pages_pays"
        )
        pays_filter = pays_values[pays_idx]

    with col7:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    # Sauvegarder le filtre
    with col_save_btn:
        st.write("")
        with st.popover("💾 Sauver"):
            new_filter_name = st.text_input("Nom du filtre", key="new_filter_name")
            if st.button("Sauvegarder", key="save_filter_btn"):
                if new_filter_name:
                    current_filters = {
                        "search_term": search_term,
                        "cms": cms_filter,
                        "etat": etat_filter
                    }
                    save_filter(db, new_filter_name, current_filters, "pages")
                    st.success(f"Filtre '{new_filter_name}' sauvegarde!")
                    st.rerun()

    # Gerer les filtres sauvegardes
    if saved_filters:
        with st.expander("🗑️ Gerer les filtres sauvegardes"):
            for sf in saved_filters:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"📂 {sf['name']}")
                with col2:
                    if st.button("❌", key=f"del_filter_{sf['id']}"):
                        delete_saved_filter(db, sf['id'])
                        st.rerun()

    # Mode d'affichage
    col_mode, col_bulk, col_export = st.columns([2, 1, 1])
    with col_mode:
        view_mode = st.radio("Mode d'affichage", ["Tableau", "Detaille", "Selection"], horizontal=True)

    # Recherche
    try:
        thematique_param = None
        if thematique_filter == "Non classifiees":
            thematique_param = "__unclassified__"
        elif thematique_filter != "Toutes":
            thematique_param = thematique_filter

        subcategory_param = None
        if subcategory_filter != "Toutes":
            subcategory_param = subcategory_filter

        results = search_pages(
            db,
            cms=cms_filter if cms_filter != "Tous" else None,
            etat=etat_filter if etat_filter != "Tous" else None,
            search_term=search_term if search_term else None,
            thematique=thematique_param,
            subcategory=subcategory_param,
            pays=pays_filter,
            page_id=page_id_filter.strip() if page_id_filter else None,
            limit=limit
        )

        if results:
            # Enrichir avec scores et winning ads
            winning_by_page = get_winning_ads_count_by_page(db, days=30)
            winning_counts = {str(k): v for k, v in winning_by_page.items()}

            for page in results:
                pid = str(page.get("page_id", ""))
                winning_count = winning_counts.get(pid, 0)
                page["winning_ads"] = winning_count
                page["score"] = calculate_page_score(page, winning_count)

            # Trier par score
            results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

            # Export CSV
            _render_export_csv(col_export, results)

            col_results, col_help = st.columns([3, 1])
            with col_results:
                st.markdown(f"**{len(results)} resultats**")
            with col_help:
                _render_score_help()

            # Affichage selon le mode
            if view_mode == "Selection":
                _render_selection_mode(db, results)
            elif view_mode == "Tableau":
                _render_table_mode(results)
            else:
                _render_detailed_mode(db, results)
        else:
            st.info("Aucun resultat trouve")

    except Exception as e:
        st.error(f"Erreur: {e}")


def _render_export_csv(col_export, results: list):
    """Affiche le bouton d'export CSV personnalise."""
    with col_export:
        all_export_columns = {
            "Page ID": lambda p: p.get("page_id", ""),
            "Nom": lambda p: p.get("page_name", ""),
            "Site": lambda p: p.get("lien_site", ""),
            "CMS": lambda p: p.get("cms", ""),
            "Etat": lambda p: p.get("etat", ""),
            "Ads Actives": lambda p: p.get("nombre_ads_active", 0),
            "Winning Ads": lambda p: p.get("winning_ads", 0),
            "Produits": lambda p: p.get("nombre_produits", 0),
            "Score": lambda p: p.get("score", 0),
            "Dernier Scan": lambda p: p.get("dernier_scan").strftime("%Y-%m-%d %H:%M") if p.get("dernier_scan") else "",
            "Thematique": lambda p: p.get("thematique", ""),
            "Sous-categorie": lambda p: p.get("subcategory", ""),
            "Ads Library": lambda p: p.get("lien_fb_ad_library", ""),
            "Page Facebook": lambda p: f"https://www.facebook.com/{p.get('page_id', '')}",
        }

        default_columns = ["Page ID", "Nom", "Site", "CMS", "Etat", "Ads Actives", "Winning Ads", "Score"]

        with st.popover("📥 Export CSV"):
            st.markdown("**Colonnes a exporter:**")
            selected_columns = st.multiselect(
                "Selectionner les colonnes",
                options=list(all_export_columns.keys()),
                default=default_columns,
                key="export_columns_pages",
                label_visibility="collapsed"
            )

            if selected_columns:
                export_data = []
                for p in results:
                    row = {col: all_export_columns[col](p) for col in selected_columns}
                    export_data.append(row)

                csv_data = export_to_csv(export_data)
                st.download_button(
                    f"📥 Telecharger ({len(selected_columns)} colonnes)",
                    csv_data,
                    file_name=f"pages_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    width="stretch"
                )
            else:
                st.warning("Selectionnez au moins une colonne")


def _render_score_help():
    """Affiche l'aide sur le calcul du score."""
    with st.popover("ℹ️ Calcul du score"):
        st.markdown("""
**Score de performance (0-100 pts)**

**Nombre d'ads actives** (max 40 pts)
- ≥150 ads → 40 pts
- ≥80 ads → 35 pts
- ≥35 ads → 25 pts

**Winning Ads** (max 30 pts)
- ≥10 winning → 30 pts
- ≥5 winning → 25 pts
- ≥3 winning → 20 pts

**Produits** (max 20 pts)
- ≥100 produits → 20 pts
- ≥50 produits → 15 pts

**Bonus CMS** (+10 pts)
- Shopify → +10 pts
""")


def _render_selection_mode(db, results: list):
    """Mode selection avec actions groupees."""
    st.info("☑️ Cochez les pages puis appliquez une action groupee")

    col_actions = st.columns([1, 1, 1, 1, 2])

    with col_actions[0]:
        if st.button("☑️ Tout selectionner"):
            st.session_state.selected_pages = [p.get("page_id") for p in results]
            st.rerun()

    with col_actions[1]:
        if st.button("❎ Tout deselectionner"):
            st.session_state.selected_pages = []
            st.rerun()

    selected_count = len(st.session_state.selected_pages)
    st.caption(f"**{selected_count}** page(s) selectionnee(s)")

    if selected_count > 0:
        st.markdown("---")
        st.markdown("**Actions groupees:**")
        action_cols = st.columns(5)

        with action_cols[0]:
            if st.button("⭐ Ajouter favoris", width="stretch"):
                count = bulk_add_to_favorites(db, st.session_state.selected_pages)
                st.success(f"{count} page(s) ajoutee(s) aux favoris")
                st.session_state.selected_pages = []
                st.rerun()

        with action_cols[1]:
            if st.button("🚫 Blacklister", width="stretch"):
                count = bulk_add_to_blacklist(db, st.session_state.selected_pages, "Bulk blacklist")
                st.success(f"{count} page(s) blacklistee(s)")
                st.session_state.selected_pages = []
                st.rerun()

        with action_cols[2]:
            collections = get_collections(db)
            if collections:
                coll_names = [c["name"] for c in collections]
                selected_coll = st.selectbox("📁 Collection", ["--"] + coll_names, key="bulk_coll")
                if selected_coll != "--":
                    coll_id = next(c["id"] for c in collections if c["name"] == selected_coll)
                    if st.button("Ajouter", key="bulk_add_coll"):
                        count = bulk_add_to_collection(db, coll_id, st.session_state.selected_pages)
                        st.success(f"{count} page(s) ajoutee(s)")
                        st.session_state.selected_pages = []
                        st.rerun()

        with action_cols[3]:
            all_tags = get_all_tags(db)
            if all_tags:
                tag_names = [t["name"] for t in all_tags]
                selected_tag = st.selectbox("🏷️ Tag", ["--"] + tag_names, key="bulk_tag")
                if selected_tag != "--":
                    tag_id = next(t["id"] for t in all_tags if t["name"] == selected_tag)
                    if st.button("Ajouter", key="bulk_add_tag"):
                        count = bulk_add_tag(db, tag_id, st.session_state.selected_pages)
                        st.success(f"Tag ajoute a {count} page(s)")
                        st.session_state.selected_pages = []
                        st.rerun()

    st.markdown("---")

    # Liste avec checkboxes
    for page in results:
        pid = page.get("page_id")
        score = page.get("score", 0)
        score_icon = get_score_color(score)

        col_check, col_info = st.columns([1, 10])

        with col_check:
            is_selected = pid in st.session_state.selected_pages
            if st.checkbox("", value=is_selected, key=f"sel_{pid}"):
                if pid not in st.session_state.selected_pages:
                    st.session_state.selected_pages.append(pid)
            else:
                if pid in st.session_state.selected_pages:
                    st.session_state.selected_pages.remove(pid)

        with col_info:
            st.write(f"{score_icon} **{page.get('page_name', 'N/A')}** | {page.get('etat', 'N/A')} | {page.get('nombre_ads_active', 0)} ads | Score: {score}")


def _render_table_mode(results: list):
    """Mode tableau."""
    df = pd.DataFrame(results)

    df["score_display"] = df.apply(
        lambda r: f"{get_score_color(r.get('score', 0))} {r.get('score', 0)}", axis=1
    )
    df["etat_display"] = df["etat"].apply(lambda x: format_state_for_df(x) if x else "")
    df["thematique_display"] = df["thematique"].apply(lambda x: x if x else "—")
    df["scan_display"] = df["dernier_scan"].apply(
        lambda x: x.strftime("%d/%m %H:%M") if pd.notna(x) and x else "—"
    )

    def format_classification(row):
        subcat = row.get("subcategory", "")
        conf = row.get("classification_confidence", 0)
        if subcat:
            if conf and conf >= 0.5:
                return f"{subcat} ({int(conf*100)}%)"
            return subcat
        return "—"

    df["classification_display"] = df.apply(format_classification, axis=1)

    display_cols = ["score_display", "page_name", "lien_site", "cms", "etat_display", "nombre_ads_active", "winning_ads", "scan_display", "thematique_display", "classification_display"]
    df_display = df[[c for c in display_cols if c in df.columns]]

    col_names = ["Score", "Nom", "Site", "CMS", "Etat", "Ads", "🏆", "Scan", "Thematique", "Classification"]
    df_display.columns = col_names[:len(df_display.columns)]

    st.dataframe(
        df_display,
        width="stretch",
        hide_index=True,
        column_config={"Site": st.column_config.LinkColumn("Site")}
    )


def _render_detailed_mode(db, results: list):
    """Mode detaille avec actions par page."""
    for page in results:
        score = page.get("score", 0)
        winning = page.get("winning_ads", 0)
        score_icon = get_score_color(score)

        with st.expander(f"{score_icon} **{page.get('page_name', 'N/A')}** - Score: {score} | {page.get('etat', 'N/A')} ({page.get('nombre_ads_active', 0)} ads, {winning} 🏆)"):
            col1, col2 = st.columns([3, 1])

            with col1:
                pid = page.get('page_id')

                st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")
                st.write(f"**Score:** {score}/100 | **Winning Ads:** {winning}")

                # Classification editable
                st.markdown("---")
                st.markdown("**Classification:**")
                edit_col1, edit_col2 = st.columns(2)

                current_thematique = page.get('thematique', '') or ''
                current_subcat = page.get('subcategory', '') or ''
                conf = page.get('classification_confidence', 0)

                with edit_col1:
                    thematique_options_edit = [""] + get_taxonomy_categories(db)
                    current_idx = thematique_options_edit.index(current_thematique) if current_thematique in thematique_options_edit else 0
                    new_thematique = st.selectbox(
                        "Thematique",
                        thematique_options_edit,
                        index=current_idx,
                        key=f"edit_them_{pid}"
                    )

                with edit_col2:
                    if new_thematique:
                        subcat_options_edit = [""] + get_all_subcategories(db, category=new_thematique)
                    else:
                        subcat_options_edit = [""] + get_all_subcategories(db)
                    current_subcat_idx = subcat_options_edit.index(current_subcat) if current_subcat in subcat_options_edit else 0
                    new_classification = st.selectbox(
                        "Classification",
                        subcat_options_edit,
                        index=current_subcat_idx,
                        key=f"edit_class_{pid}"
                    )

                if new_thematique != current_thematique or new_classification != current_subcat:
                    if st.button("💾 Sauvegarder classification", key=f"save_class_{pid}"):
                        update_page_classification(db, pid, new_thematique, new_classification, confidence=1.0)
                        st.success("Classification mise a jour!")
                        st.rerun()
                elif conf:
                    st.caption(f"Confiance: {int(conf*100)}%")

                # Tags
                page_tags = get_page_tags(db, pid)
                if page_tags:
                    tag_html = " ".join([f"<span style='background-color:{t['color']};color:white;padding:2px 8px;border-radius:10px;margin-right:5px;font-size:11px;'>{t['name']}</span>" for t in page_tags])
                    st.markdown(tag_html, unsafe_allow_html=True)

                # Notes
                st.markdown("---")
                notes = get_page_notes(db, pid)
                if notes:
                    st.caption(f"📝 {len(notes)} note(s)")
                    for note in notes[:2]:
                        st.caption(f"• {note['content'][:50]}...")

                with st.popover("📝 Ajouter note"):
                    new_note = st.text_area("Note", key=f"note_{pid}", placeholder="Votre note...")
                    if st.button("Sauvegarder", key=f"save_note_{pid}"):
                        if new_note:
                            add_page_note(db, pid, new_note)
                            st.success("Note ajoutee!")
                            st.rerun()

            with col2:
                # Favori
                is_fav = is_favorite(db, pid)
                fav_icon = "⭐" if is_fav else "☆"
                if st.button(f"{fav_icon} Favori", key=f"fav_{pid}"):
                    toggle_favorite(db, pid)
                    st.rerun()

                if page.get('lien_fb_ad_library'):
                    st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                st.code(pid, language=None)

                # Collection
                collections = get_collections(db)
                if collections:
                    with st.popover("📁 Collection"):
                        for coll in collections:
                            if st.button(f"{coll['icon']} {coll['name']}", key=f"addcoll_{pid}_{coll['id']}"):
                                add_page_to_collection(db, coll['id'], pid)
                                st.success(f"Ajoute a {coll['name']}")
                                st.rerun()

                # Tag
                all_tags = get_all_tags(db)
                if all_tags:
                    with st.popover("🏷️ Tag"):
                        for tag in all_tags:
                            if st.button(f"{tag['name']}", key=f"addtag_{pid}_{tag['id']}"):
                                add_tag_to_page(db, pid, tag['id'])
                                st.success(f"Tag ajoute!")
                                st.rerun()

                if st.button("🚫 Blacklist", key=f"bl_page_{pid}"):
                    if add_to_blacklist(db, pid, page.get('page_name', ''), "Blackliste depuis Pages/Shops"):
                        st.success(f"✓ Blackliste")
                        st.rerun()
                    else:
                        st.warning("Deja blackliste")
