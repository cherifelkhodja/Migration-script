"""
Page Favoris - Acces rapide aux pages marquees comme favorites.

Ce module permet de gerer une liste de pages favorites pour un acces
rapide aux pages les plus suivies ou interessantes.

Fonctionnalites:
----------------
- Affichage des pages favorites avec leurs details
- Tags associes a chaque page (affichage colore)
- Notes attachees aux pages
- Lien direct vers la Facebook Ads Library
- Suppression des favoris en un clic

Informations affichees:
-----------------------
Pour chaque page favorite :
- Nom de la page et etat (XS a XXL)
- Nombre d'ads actives
- Site web associe
- CMS et nombre de produits
- Tags (badges colores)
- Nombre de notes

Cas d'usage:
------------
- Marquer les concurrents a surveiller regulierement
- Creer une shortlist de pages performantes
- Organiser sa veille quotidienne

Note technique:
---------------
Les favoris sont stockes en base via la table dediee.
Une page peut etre ajoutee/retiree depuis Pages/Shops.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database

# Design System imports
from src.presentation.streamlit.ui import (
    apply_theme, ICONS,
    page_header, section_header,
    alert, empty_state, format_number,
)
from src.infrastructure.persistence.database import (
    get_favorites, remove_favorite, search_pages,
    get_page_tags, get_page_notes
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext


def render_favorites():
    """Page Favoris - Pages favorites."""
    # Appliquer le thème
    apply_theme()

    # Header avec Design System
    page_header(
        title="Favoris",
        subtitle="Vos pages favorites pour un acces rapide",
        icon=ICONS.get("star", "⭐"),
        show_divider=True
    )

    db = get_database()
    if not db:
        alert("Base de donnees non connectee", variant="warning")
        return

    # Multi-tenancy: recuperer l'utilisateur courant
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    try:
        favorite_ids = get_favorites(db, user_id=user_id)

        if favorite_ids:
            st.info(f"⭐ {len(favorite_ids)} page(s) en favoris")

            # Recuperer les details des pages favorites
            pages = []
            for fav_id in favorite_ids:
                page_results = search_pages(db, search_term=fav_id, limit=1, user_id=user_id)
                if page_results:
                    pages.append(page_results[0])

            if pages:
                for page in pages:
                    pid = page.get("page_id")
                    with st.expander(f"⭐ **{page.get('page_name', 'N/A')}** - {page.get('etat', 'N/A')} ({page.get('nombre_ads_active', 0)} ads)"):
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                            st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")

                            # Tags
                            tags = get_page_tags(db, pid, user_id=user_id)
                            if tags:
                                tag_html = " ".join([
                                    f"<span style='background-color:{t['color']};color:white;padding:2px 8px;border-radius:10px;margin-right:5px;font-size:12px;'>{t['name']}</span>"
                                    for t in tags
                                ])
                                st.markdown(tag_html, unsafe_allow_html=True)

                            # Notes
                            notes = get_page_notes(db, pid, user_id=user_id)
                            if notes:
                                st.caption(f"📝 {len(notes)} note(s)")

                        with col2:
                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                        with col3:
                            if st.button("❌ Retirer", key=f"unfav_{pid}"):
                                remove_favorite(db, pid, user_id=user_id)
                                st.success("Retire des favoris")
                                st.rerun()
        else:
            empty_state(
                title="Aucune page en favoris",
                description="Ajoutez des pages depuis la page Pages/Shops.",
                icon="⭐"
            )

    except Exception as e:
        st.error(f"Erreur: {e}")
