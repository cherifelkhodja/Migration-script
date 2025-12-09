"""
Page Search Ads - Recherche d'annonces Meta Ad Library.

Ce module constitue le point d'entree de la fonctionnalite de recherche.
Il orchestre les differents modes de recherche via des sous-modules dedies.

Architecture du module:
-----------------------
- search.py: Point d'entree et routage entre modes
- search_keyword.py: Recherche par mots-cles + pipeline 8 phases
- search_page_id.py: Recherche directe par Page IDs
- search_results.py: Apercu interactif et sauvegarde

Modes de recherche:
-------------------
1. Par mots-cles: Recherche classique via l'API Meta Ad Library
2. Par Page IDs: Recherche directe par batch de 10 IDs

Pipeline de recherche (8 phases):
---------------------------------
    Phase 1: Recherche par mots-cles
    Phase 2: Regroupement par page
    Phase 3: Extraction sites web + CMS
    Phase 4: Filtrage par CMS
    Phase 5: Comptage des annonces (batch)
    Phase 6: Analyse sites + Classification Gemini
    Phase 7: Detection Winning Ads
    Phase 8: Sauvegarde ou Apercu
"""
import streamlit as st

# Design System imports
from src.presentation.streamlit.ui import (
    apply_theme, ICONS,
    page_header,
)

# Sous-modules de recherche
from src.presentation.streamlit._pages.search_keyword import render_keyword_search
from src.presentation.streamlit._pages.search_page_id import render_page_id_search
from src.presentation.streamlit._pages.search_results import render_preview_results


def render_search_ads():
    """
    Page Search Ads - Recherche d'annonces.

    Point d'entree principal qui:
    - Affiche le header de page
    - Route vers l'apercu si des resultats sont en attente
    - Affiche le selecteur de mode de recherche
    - Delegue aux sous-modules selon le mode choisi
    """
    from src.presentation.streamlit.dashboard import get_search_history, render_search_history_selector

    # Appliquer le theme
    apply_theme()

    # Header avec Design System
    page_header(
        title="Search Ads",
        subtitle="Rechercher et analyser des annonces Meta",
        icon=ICONS.get("search", "🔍"),
        show_divider=False
    )

    # Verifier si on a des resultats en apercu a afficher
    if st.session_state.get("show_preview_results", False):
        render_preview_results()
        return

    # Historique de recherche
    col_title, col_history = st.columns([2, 1])
    with col_title:
        pass  # Subtitle already in header
    with col_history:
        # Selecteur d'historique
        history = get_search_history()
        if history:
            selected_history = render_search_history_selector("search")
            if selected_history:
                st.session_state['_prefill_search'] = selected_history

    # Selection du mode de recherche
    search_mode = st.radio(
        "Mode de recherche",
        ["🔤 Par mots-cles", "🆔 Par Page IDs"],
        horizontal=True,
        help="Choisissez entre recherche par mots-cles ou directement par Page IDs"
    )

    if search_mode == "🔤 Par mots-cles":
        render_keyword_search()
    else:
        render_page_id_search()
