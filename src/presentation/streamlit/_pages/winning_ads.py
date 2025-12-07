"""
Page Winning Ads - Detection et analyse des annonces performantes.

Ce module affiche les annonces considerees comme "winning" selon
des criteres de performance reach/age.

Criteres de Winning Ads:
------------------------
Une annonce est winning si elle valide AU MOINS UN de ces criteres :

| Age max | Reach min |  Interpretation                    |
|---------|-----------|-------------------------------------|
| <=4j    | >15 000   | Ad tres recente, deja virale       |
| <=5j    | >20 000   | Excellente traction initiale       |
| <=6j    | >30 000   | Performance confirmee              |
| <=7j    | >40 000   | Ad qui scale bien                  |
| <=8j    | >50 000   | Performance soutenue               |
| <=15j   | >100 000  | Ad mature performante              |
| <=22j   | >200 000  | Gros volume sur duree              |
| <=29j   | >400 000  | Blockbuster                        |

Logique : Plus une ad est recente avec un reach eleve, plus elle
est performante. Le ratio reach/age est l'indicateur cle.

Filtres disponibles:
--------------------
- **Page ID** : Filtrer les winning ads d'une page specifique
- **Ad ID** : Rechercher une annonce particuliere
- **Thematique** : Classification Gemini
- **Sous-categorie** : Affinage de la thematique
- **Pays** : Filtrage geographique
- **Periode** : 7, 14, 30, 60 ou 90 jours
- **Limite** : 50 a 1000, ou "Toutes"
- **Tri** : Reach, Date de scan, Age de l'ad

Modes de groupement:
--------------------
1. **Aucun** : Liste plate triee
2. **Par Page** : Expanders par page avec total reach
3. **Par Age** : Tranches 0-4j, 5-7j, 8-14j, 15-21j, 22-30j, 30+j

Statistiques:
-------------
- Total winning ads sur la periode
- Nombre de pages avec winning
- Reach moyen
- Critere le plus frequent
- Top pages (tableau)
- Graphique repartition par critere

Export CSV personnalise:
------------------------
Colonnes selectionnables :
Page, Page ID, Ad ID, Reach, Age, Critere, Texte Ad, Site, CMS,
URL Ad, Date scan, Page Facebook, Ad Library

Presets : Essentiel (4 cols), Complet (toutes)
"""
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import (
    CHART_COLORS, info_card, chart_header,
    create_horizontal_bar_chart, export_to_csv
)
from src.infrastructure.persistence.database import (
    get_winning_ads, get_winning_ads_stats, get_winning_ads_filtered,
    get_winning_ads_stats_filtered
)


def parse_ad_body(body_raw: str, max_length: int = 80) -> str:
    """
    Parse le texte d'une ad depuis le format brut (JSON ou string).

    Args:
        body_raw: Texte brut (peut etre JSON array ou string simple)
        max_length: Longueur max avant troncature

    Returns:
        Texte propre sans crochets, tronque si necessaire
    """
    if not body_raw:
        return ""

    body = body_raw

    # Si c'est une string qui ressemble a du JSON array
    if isinstance(body, str):
        body = body.strip()
        if body.startswith("["):
            try:
                import json
                parsed = json.loads(body)
                if isinstance(parsed, list) and parsed:
                    body = parsed[0]
            except (json.JSONDecodeError, IndexError):
                # Enlever les crochets manuellement si le parsing echoue
                body = body.strip("[]'\"")

    # Si c'est deja une liste
    if isinstance(body, list):
        body = body[0] if body else ""

    # Nettoyer et tronquer
    body = str(body).strip()
    if len(body) > max_length:
        return body[:max_length] + "..."
    return body


def render_classification_filters(db, key_prefix: str = "", columns: int = 3):
    """Filtres de classification (thematique, subcategory, pays)."""
    from src.infrastructure.persistence.database import (
        get_taxonomy_categories, get_all_subcategories, get_all_countries
    )

    filters = {}
    cols = st.columns(columns)

    with cols[0]:
        categories = get_taxonomy_categories(db)
        thematique = st.selectbox(
            "🏷️ Thematique",
            options=["Toutes"] + categories,
            key=f"{key_prefix}_thematique"
        )
        filters["thematique"] = thematique if thematique != "Toutes" else None

    with cols[1]:
        subcategories = get_all_subcategories(db)
        subcategory = st.selectbox(
            "📂 Sous-categorie",
            options=["Toutes"] + subcategories,
            key=f"{key_prefix}_subcategory"
        )
        filters["subcategory"] = subcategory if subcategory != "Toutes" else None

    if columns >= 3:
        with cols[2]:
            countries = get_all_countries(db)
            pays = st.selectbox(
                "🌍 Pays",
                options=["Tous"] + countries,
                key=f"{key_prefix}_pays"
            )
            filters["pays"] = pays if pays != "Tous" else None

    return filters


def render_winning_ads():
    """Page Winning Ads - Annonces performantes detectees"""
    st.title("🏆 Winning Ads")
    st.markdown("Annonces performantes basees sur reach + age")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Criteres expliques
    with st.expander("ℹ️ Criteres de detection des Winning Ads", expanded=False):
        st.markdown("""
        Une annonce est consideree comme **winning** si elle valide **au moins un** de ces criteres :

        | Age max | Reach min |
        |---------|-----------|
        | ≤4 jours | >15 000 |
        | ≤5 jours | >20 000 |
        | ≤6 jours | >30 000 |
        | ≤7 jours | >40 000 |
        | ≤8 jours | >50 000 |
        | ≤15 jours | >100 000 |
        | ≤22 jours | >200 000 |
        | ≤29 jours | >400 000 |

        Plus une annonce est recente avec un reach eleve, plus elle est performante.
        """)

    # Filtres de classification
    st.markdown("#### 🔍 Filtres")

    # Filtre par ID (Page ID ou Ad ID)
    col_id1, col_id2 = st.columns(2)
    with col_id1:
        page_id_filter = st.text_input(
            "🆔 Page ID",
            placeholder="Ex: 123456789012345",
            help="Filtrer les winning ads d'une page specifique",
            key="winning_page_id"
        )
    with col_id2:
        ad_id_filter = st.text_input(
            "📢 Ad ID",
            placeholder="Ex: 987654321098765",
            help="Rechercher une annonce specifique par son ID",
            key="winning_ad_id"
        )

    class_filters = render_classification_filters(db, key_prefix="winning", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if page_id_filter:
        active_filters.append(f"🆔 Page: {page_id_filter}")
    if ad_id_filter:
        active_filters.append(f"📢 Ad: {ad_id_filter}")
    if class_filters.get("thematique"):
        active_filters.append(f"🏷️ {class_filters['thematique']}")
    if class_filters.get("subcategory"):
        active_filters.append(f"📂 {class_filters['subcategory']}")
    if class_filters.get("pays"):
        active_filters.append(f"🌍 {class_filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' • '.join(active_filters)}")

    st.markdown("---")

    # Filtres existants
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        period = st.selectbox(
            "📅 Periode",
            options=[7, 14, 30, 60, 90],
            format_func=lambda x: f"{x} jours",
            index=2
        )

    with col2:
        limit_options = [50, 100, 200, 500, 1000, 0]  # 0 = Toutes
        limit = st.selectbox(
            "Limite",
            limit_options,
            format_func=lambda x: "Toutes" if x == 0 else str(x),
            index=1
        )

    with col3:
        sort_by = st.selectbox(
            "Trier par",
            options=["Reach", "Date de scan", "Age de l'ad"],
            index=0
        )

    with col4:
        group_by = st.selectbox(
            "Grouper par",
            options=["Aucun", "Par Page", "Par Age"],
            index=0,
            help="Grouper les winning ads par page ou par age"
        )

    try:
        # Statistiques globales (avec filtres si actifs)
        if any(class_filters.values()):
            stats = get_winning_ads_stats_filtered(
                db, days=period,
                thematique=class_filters.get("thematique"),
                subcategory=class_filters.get("subcategory"),
                pays=class_filters.get("pays")
            )
        else:
            stats = get_winning_ads_stats(db, days=period)

        st.markdown("---")
        st.subheader("📊 Statistiques")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏆 Total Winning Ads", stats.get("total", 0))
        col2.metric("📄 Pages avec Winning", stats.get("unique_pages", 0))
        col3.metric("📈 Reach moyen", f"{stats.get('avg_reach', 0):,}".replace(",", " "))

        # Criteres les plus frequents
        by_criteria = stats.get("by_criteria", {})
        if by_criteria:
            top_criteria = max(by_criteria.items(), key=lambda x: x[1]) if by_criteria else ("N/A", 0)
            col4.metric("🎯 Critere top", top_criteria[0])

        # Graphique par critere
        if by_criteria:
            st.markdown("---")

            # Info card
            info_card(
                "Comprendre les criteres de Winning Ads",
                """
                Chaque critere represente une combinaison age/reach :<br>
                • <b>≤4j >15k</b> : Ad de moins de 4 jours avec plus de 15 000 personnes touchees<br>
                • Plus le ratio reach/age est eleve, plus l'ad est performante<br>
                • Une ad qui touche beaucoup de monde rapidement indique un bon produit/creative
                """,
                "🎯"
            )

            col1, col2 = st.columns(2)

            with col1:
                chart_header(
                    "📊 Repartition par critere",
                    "Quels seuils sont les plus atteints",
                    "Le critere le plus frequent indique le niveau de performance moyen"
                )
                # Trier par valeur
                sorted_criteria = sorted(by_criteria.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_criteria]
                values = [c[1] for c in sorted_criteria]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    colors=[CHART_COLORS["success"]] * len(labels),
                    value_suffix=" ads",
                    height=280
                )
                st.plotly_chart(fig, key="winning_by_criteria", width="stretch")

            with col2:
                chart_header(
                    "🏆 Top Pages avec Winning Ads",
                    "Pages ayant le plus d'annonces performantes",
                    "Ces pages ont probablement trouve des produits/creatives gagnants"
                )
                by_page = stats.get("by_page", [])
                if by_page:
                    df_pages = pd.DataFrame(by_page)
                    df_pages.columns = ["Page ID", "Nom", "Winning Ads"]
                    st.dataframe(df_pages, width="stretch", hide_index=True)
                else:
                    st.info("Aucune page avec winning ads")

        # Liste des winning ads
        st.markdown("---")

        # limit=0 signifie "Toutes" -> on utilise une tres grande limite
        actual_limit = limit if limit > 0 else 100000

        # Preparer les filtres ID
        page_id_param = page_id_filter.strip() if page_id_filter else None
        ad_id_param = ad_id_filter.strip() if ad_id_filter else None

        # Utiliser la fonction filtree si des filtres sont actifs
        if any(class_filters.values()) or page_id_param or ad_id_param:
            winning_ads = get_winning_ads_filtered(
                db, limit=actual_limit, days=period,
                page_id=page_id_param,
                ad_id=ad_id_param,
                thematique=class_filters.get("thematique"),
                subcategory=class_filters.get("subcategory"),
                pays=class_filters.get("pays")
            )
        else:
            winning_ads = get_winning_ads(db, limit=actual_limit, days=period)

        if winning_ads:
            _render_winning_ads_list(winning_ads, group_by, period)
        else:
            st.info("Aucune winning ad trouvee pour cette periode. Lancez une recherche pour en detecter.")

    except Exception as e:
        st.error(f"Erreur: {e}")


def _render_winning_ads_list(winning_ads: list, group_by: str, period: int):
    """Affiche la liste des winning ads avec options de groupement."""
    # Header avec export personnalise
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 Liste des Winning Ads")
    with col2:
        # Colonnes disponibles pour export
        all_winning_columns = {
            "Page": lambda ad: ad.get("page_name", ""),
            "Page ID": lambda ad: ad.get("page_id", ""),
            "Ad ID": lambda ad: ad.get("ad_id", ""),
            "Reach": lambda ad: ad.get("eu_total_reach", 0),
            "Age (jours)": lambda ad: ad.get("ad_age_days", 0),
            "Critere": lambda ad: ad.get("matched_criteria", ""),
            "Texte Ad": lambda ad: parse_ad_body(ad.get("ad_creative_bodies", ""), 200),
            "Site": lambda ad: ad.get("lien_site", ""),
            "CMS": lambda ad: ad.get("cms", ""),
            "URL Ad": lambda ad: ad.get("ad_snapshot_url", ""),
            "Date scan": lambda ad: ad.get("date_scan").strftime("%Y-%m-%d") if ad.get("date_scan") else "",
            "Page Facebook": lambda ad: f"https://www.facebook.com/{ad.get('page_id', '')}",
            "Ad Library": lambda ad: f"https://www.facebook.com/ads/library/?id={ad.get('ad_id', '')}"
        }

        default_winning_cols = ["Page", "Ad ID", "Reach", "Age (jours)", "Critere", "Site"]

        with st.popover("📥 Export CSV"):
            st.markdown("**Colonnes a exporter:**")
            selected_winning_cols = st.multiselect(
                "Colonnes",
                options=list(all_winning_columns.keys()),
                default=default_winning_cols,
                key="export_columns_winning",
                label_visibility="collapsed"
            )

            # Presets
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                if st.button("📋 Essentiel", key="preset_win_ess", width="stretch"):
                    st.session_state.export_columns_winning = ["Page", "Ad ID", "Reach", "Critere"]
                    st.rerun()
            with col_w2:
                if st.button("📊 Complet", key="preset_win_full", width="stretch"):
                    st.session_state.export_columns_winning = list(all_winning_columns.keys())
                    st.rerun()

            if selected_winning_cols:
                export_data = []
                for ad in winning_ads:
                    row = {col: all_winning_columns[col](ad) for col in selected_winning_cols}
                    export_data.append(row)

                csv_data = export_to_csv(export_data)
                group_suffix = f"_{group_by.lower().replace(' ', '_')}" if group_by != "Aucun" else ""
                st.download_button(
                    f"📥 Telecharger ({len(selected_winning_cols)} col.)",
                    csv_data,
                    f"winning_ads_{period}j{group_suffix}.csv",
                    "text/csv",
                    key="export_winning",
                    width="stretch"
                )
            else:
                st.warning("Selectionnez au moins une colonne")

    group_info = f" (groupe: {group_by})" if group_by != "Aucun" else ""
    st.info(f"🏆 {len(winning_ads)} winning ads trouvees{group_info}")

    # === AFFICHAGE GROUPE ===
    if group_by == "Par Page":
        _render_grouped_by_page(winning_ads)
    elif group_by == "Par Age":
        _render_grouped_by_age(winning_ads)
    else:
        _render_winning_ads_table(winning_ads)


def _render_grouped_by_page(winning_ads: list):
    """Affiche les winning ads groupees par page."""
    groups = {}
    for ad in winning_ads:
        page_name = ad.get('page_name', 'N/A')
        page_id = ad.get('page_id', '')
        key = f"{page_name}||{page_id}"
        if key not in groups:
            groups[key] = []
        groups[key].append(ad)

    # Trier les groupes par nombre d'ads (decroissant)
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    for group_key, ads in sorted_groups:
        page_name, page_id = group_key.split("||")
        total_reach = sum(ad.get('eu_total_reach', 0) or 0 for ad in ads)

        with st.expander(f"📄 **{page_name}** - {len(ads)} winning ads (Total reach: {total_reach:,}".replace(",", " ") + ")"):
            # Tableau des ads de cette page
            table_data = []
            for ad in sorted(ads, key=lambda x: x.get('eu_total_reach', 0) or 0, reverse=True):
                reach_val = ad.get('eu_total_reach', 0) or 0
                table_data.append({
                    "Ad ID": ad.get('ad_id', '')[:15],
                    "Reach": f"{reach_val:,}".replace(",", " "),
                    "Age (j)": ad.get('ad_age_days', 0) or 0,
                    "Critere": ad.get('matched_criteria', 'N/A'),
                    "Texte": parse_ad_body(ad.get('ad_creative_bodies', ''), 60),
                    "Ad URL": ad.get('ad_snapshot_url', '')
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, width="stretch", hide_index=True,
                       column_config={"Ad URL": st.column_config.LinkColumn("Voir")})

            # Lien vers le site
            site = ads[0].get('lien_site', '')
            if site:
                st.link_button("🌐 Voir le site", site)
            st.code(page_id, language=None)


def _render_grouped_by_age(winning_ads: list):
    """Affiche les winning ads groupees par tranches d'age."""
    age_ranges = [
        (0, 4, "0-4 jours (tres recent)"),
        (5, 7, "5-7 jours"),
        (8, 14, "8-14 jours"),
        (15, 21, "15-21 jours"),
        (22, 30, "22-30 jours"),
        (31, 999, "30+ jours")
    ]

    groups = {label: [] for _, _, label in age_ranges}

    for ad in winning_ads:
        age = ad.get('ad_age_days', 0) or 0
        for min_age, max_age, label in age_ranges:
            if min_age <= age <= max_age:
                groups[label].append(ad)
                break

    for _, _, label in age_ranges:
        ads = groups[label]
        if not ads:
            continue

        total_reach = sum(ad.get('eu_total_reach', 0) or 0 for ad in ads)
        avg_reach = total_reach // len(ads) if ads else 0

        with st.expander(f"📅 **{label}** - {len(ads)} ads (Reach moyen: {avg_reach:,}".replace(",", " ") + ")"):
            table_data = []
            for ad in sorted(ads, key=lambda x: x.get('eu_total_reach', 0) or 0, reverse=True):
                reach_val = ad.get('eu_total_reach', 0) or 0
                table_data.append({
                    "Page": ad.get('page_name', 'N/A')[:30],
                    "Reach": f"{reach_val:,}".replace(",", " "),
                    "Age": f"{ad.get('ad_age_days', 0)}j",
                    "Critere": ad.get('matched_criteria', 'N/A'),
                    "Site": ad.get('lien_site', ''),
                    "Ad URL": ad.get('ad_snapshot_url', '')
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, width="stretch", hide_index=True,
                       column_config={
                           "Site": st.column_config.LinkColumn("Site"),
                           "Ad URL": st.column_config.LinkColumn("Voir")
                       }, height=min(400, 50 + len(ads) * 35))


def _render_winning_ads_table(winning_ads: list):
    """Affiche les winning ads dans un tableau simple."""
    table_data = []
    for ad in winning_ads:
        reach_val = ad.get('eu_total_reach', 0) or 0
        table_data.append({
            "Page": ad.get('page_name', 'N/A')[:40],
            "Reach": f"{reach_val:,}".replace(",", " "),
            "Age (j)": ad.get('ad_age_days', 0) or 0,
            "Critere": ad.get('matched_criteria', 'N/A'),
            "Texte": parse_ad_body(ad.get('ad_creative_bodies', ''), 80),
        })

    df_winning = pd.DataFrame(table_data)

    st.dataframe(
        df_winning,
        width="stretch",
        hide_index=True,
        height=600
    )
