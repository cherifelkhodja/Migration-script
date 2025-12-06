"""
Composants de filtres pour le dashboard Streamlit.

Ce module contient les filtres réutilisables pour
les différentes pages du dashboard.
"""

import streamlit as st
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════

# Noms lisibles pour les pays
COUNTRY_NAMES = {
    "FR": "🇫🇷 France",
    "DE": "🇩🇪 Allemagne",
    "ES": "🇪🇸 Espagne",
    "IT": "🇮🇹 Italie",
    "GB": "🇬🇧 Royaume-Uni",
    "US": "🇺🇸 États-Unis",
    "BE": "🇧🇪 Belgique",
    "CH": "🇨🇭 Suisse",
    "NL": "🇳🇱 Pays-Bas",
    "PT": "🇵🇹 Portugal",
    "AT": "🇦🇹 Autriche",
    "CA": "🇨🇦 Canada",
    "AU": "🇦🇺 Australie",
    "LU": "🇱🇺 Luxembourg",
    "PL": "🇵🇱 Pologne",
}

DATE_FILTER_OPTIONS = {
    "Toutes les données": 0,
    "Dernières 24h": 1,
    "7 derniers jours": 7,
    "30 derniers jours": 30,
    "90 derniers jours": 90
}


# ═══════════════════════════════════════════════════════════════════════════════
# FILTRES
# ═══════════════════════════════════════════════════════════════════════════════

def render_classification_filters(
    db,
    key_prefix: str = "",
    show_thematique: bool = True,
    show_subcategory: bool = True,
    show_pays: bool = True,
    columns: int = 3
) -> dict:
    """
    Affiche les filtres de classification réutilisables.

    Args:
        db: DatabaseManager
        key_prefix: Préfixe pour les clés Streamlit (éviter conflits)
        show_thematique: Afficher le filtre thématique
        show_subcategory: Afficher le filtre classification
        show_pays: Afficher le filtre pays
        columns: Nombre de colonnes pour l'affichage

    Returns:
        Dict avec les valeurs sélectionnées:
        {
            "thematique": str or None,
            "subcategory": str or None,
            "pays": str or None
        }
    """
    # Import local pour éviter les dépendances circulaires
    from src.infrastructure.persistence import get_taxonomy_categories, get_all_countries, get_all_subcategories

    result = {
        "thematique": None,
        "subcategory": None,
        "pays": None
    }

    # Déterminer les colonnes actives
    active_filters = []
    if show_thematique:
        active_filters.append("thematique")
    if show_subcategory:
        active_filters.append("subcategory")
    if show_pays:
        active_filters.append("pays")

    if not active_filters:
        return result

    # Créer les colonnes
    cols = st.columns(min(len(active_filters), columns))
    col_idx = 0

    # Récupérer les options
    categories = get_taxonomy_categories(db) if show_thematique else []
    countries = get_all_countries(db) if show_pays else []

    # Filtre Thématique (catégorie principale)
    selected_thematique = "Toutes"
    if show_thematique:
        with cols[col_idx % len(cols)]:
            thematique_options = ["Toutes"] + categories
            selected_thematique = st.selectbox(
                "Thématique",
                thematique_options,
                index=0,
                key=f"{key_prefix}_thematique"
            )
            if selected_thematique != "Toutes":
                result["thematique"] = selected_thematique
        col_idx += 1

    # Filtre Classification (dépend de la thématique sélectionnée)
    if show_subcategory:
        with cols[col_idx % len(cols)]:
            # Filtrer les classifications selon la thématique choisie
            if selected_thematique != "Toutes":
                subcategories = get_all_subcategories(db, category=selected_thematique)
            else:
                subcategories = get_all_subcategories(db)

            subcategory_options = ["Toutes"] + subcategories
            selected_subcategory = st.selectbox(
                "Classification",
                subcategory_options,
                index=0,
                key=f"{key_prefix}_subcategory"
            )
            if selected_subcategory != "Toutes":
                result["subcategory"] = selected_subcategory
        col_idx += 1

    # Filtre Pays
    if show_pays:
        with cols[col_idx % len(cols)]:
            pays_display = ["Tous"] + [COUNTRY_NAMES.get(c, c) for c in countries]
            pays_values = [None] + countries

            selected_pays_idx = st.selectbox(
                "🌍 Pays",
                range(len(pays_display)),
                format_func=lambda i: pays_display[i],
                index=0,
                key=f"{key_prefix}_pays"
            )
            if selected_pays_idx > 0:
                result["pays"] = pays_values[selected_pays_idx]

    return result


def render_date_filter(key_prefix: str = "") -> int:
    """
    Affiche un filtre de période réutilisable.

    Args:
        key_prefix: Préfixe pour les clés Streamlit

    Returns:
        Nombre de jours (0 = tous, sinon 1, 7, 30, 90)
    """
    selected = st.selectbox(
        "📅 Période",
        options=list(DATE_FILTER_OPTIONS.keys()),
        index=2,  # Par défaut: 30 derniers jours
        key=f"{key_prefix}_date_filter"
    )

    return DATE_FILTER_OPTIONS[selected]


def apply_classification_filters(query, filters: dict, model_class):
    """
    Applique les filtres de classification à une requête SQLAlchemy.

    Args:
        query: Requête SQLAlchemy
        filters: Dict retourné par render_classification_filters
        model_class: Classe du modèle (PageRecherche)

    Returns:
        Requête filtrée
    """
    if filters.get("thematique"):
        query = query.filter(model_class.thematique == filters["thematique"])

    if filters.get("subcategory"):
        query = query.filter(model_class.subcategory == filters["subcategory"])

    if filters.get("pays"):
        # Le champ pays est multi-valeurs "FR,DE,ES"
        query = query.filter(model_class.pays.ilike(f"%{filters['pays']}%"))

    return query


def render_state_filter(key_prefix: str = "") -> Optional[str]:
    """
    Affiche un filtre d'état (XXL, XL, L, M, S, XS).

    Returns:
        État sélectionné ou None pour tous
    """
    state_options = ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"]
    selected = st.selectbox(
        "📊 État",
        state_options,
        index=0,
        key=f"{key_prefix}_state_filter"
    )
    return None if selected == "Tous" else selected


def render_cms_filter(key_prefix: str = "") -> Optional[str]:
    """
    Affiche un filtre CMS.

    Returns:
        CMS sélectionné ou None pour tous
    """
    cms_options = ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"]
    selected = st.selectbox(
        "🛒 CMS",
        cms_options,
        index=0,
        key=f"{key_prefix}_cms_filter"
    )
    return None if selected == "Tous" else selected
