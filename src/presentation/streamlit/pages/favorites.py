"""
Page Favoris - Pages favorites.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.database import (
    get_favorites, remove_favorite, search_pages,
    get_page_tags, get_page_notes
)


def render_favorites():
    """Page Favoris - Pages favorites."""
    st.title("⭐ Favoris")
    st.markdown("Vos pages favorites pour un acces rapide")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    try:
        favorite_ids = get_favorites(db)

        if favorite_ids:
            st.info(f"⭐ {len(favorite_ids)} page(s) en favoris")

            # Recuperer les details des pages favorites
            pages = []
            for fav_id in favorite_ids:
                page_results = search_pages(db, search_term=fav_id, limit=1)
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
                            tags = get_page_tags(db, pid)
                            if tags:
                                tag_html = " ".join([
                                    f"<span style='background-color:{t['color']};color:white;padding:2px 8px;border-radius:10px;margin-right:5px;font-size:12px;'>{t['name']}</span>"
                                    for t in tags
                                ])
                                st.markdown(tag_html, unsafe_allow_html=True)

                            # Notes
                            notes = get_page_notes(db, pid)
                            if notes:
                                st.caption(f"📝 {len(notes)} note(s)")

                        with col2:
                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                        with col3:
                            if st.button("❌ Retirer", key=f"unfav_{pid}"):
                                remove_favorite(db, pid)
                                st.success("Retire des favoris")
                                st.rerun()
        else:
            st.info("Aucune page en favoris. Ajoutez des pages depuis la page Pages/Shops.")

    except Exception as e:
        st.error(f"Erreur: {e}")
