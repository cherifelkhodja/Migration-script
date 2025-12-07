"""
Page Collections - Organisation des pages en dossiers thematiques.

Ce module permet de regrouper les pages en collections personnalisees
pour une organisation optimale de la veille concurrentielle.

Fonctionnalites:
----------------
- Creation de collections avec nom, icone et couleur
- Ajout/suppression de pages dans les collections
- Vue par collection avec statistiques agregees
- Suppression de collections

Cas d'usage:
------------
- Regrouper les concurrents directs d'un client
- Creer des collections par niche (Mode, Tech, Beauty, etc.)
- Suivre un groupe de pages performantes
- Organiser sa veille par projet/client

Structure:
----------
Une page peut appartenir a plusieurs collections simultanement.
Les collections sont liees aux pages via une table de jointure.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.database import (
    get_collections, create_collection, delete_collection,
    get_collection_pages, remove_page_from_collection, search_pages
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext


def render_collections():
    """Page Collections - Dossiers de pages."""
    st.title("📁 Collections")
    st.markdown("Organisez vos pages en dossiers thematiques")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Multi-tenancy: recuperer l'utilisateur courant
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # Creer une nouvelle collection
    with st.expander("➕ Nouvelle collection", expanded=False):
        with st.form("new_collection"):
            col1, col2 = st.columns(2)
            with col1:
                coll_name = st.text_input("Nom *", placeholder="Ex: Concurrents mode")
            with col2:
                coll_icon = st.selectbox("Icone", ["📁", "🎯", "🔥", "💎", "🚀", "⭐", "🏆", "📊"])

            coll_desc = st.text_area("Description", placeholder="Description optionnelle...")
            coll_color = st.color_picker("Couleur", "#6366F1")

            if st.form_submit_button("Creer", type="primary"):
                if coll_name:
                    create_collection(db, coll_name, coll_desc, coll_color, coll_icon, user_id=user_id)
                    st.success(f"Collection '{coll_name}' creee!")
                    st.rerun()
                else:
                    st.error("Nom requis")

    st.markdown("---")

    # Liste des collections
    collections = get_collections(db, user_id=user_id)

    if collections:
        for coll in collections:
            coll_id = coll["id"]
            with st.expander(f"{coll['icon']} **{coll['name']}** ({coll['page_count']} pages)"):
                st.caption(coll.get("description", ""))

                # Pages de la collection
                page_ids = get_collection_pages(db, coll_id, user_id=user_id)
                if page_ids:
                    for pid in page_ids[:10]:  # Limiter a 10
                        page_results = search_pages(db, search_term=pid, limit=1, user_id=user_id)
                        if page_results:
                            page = page_results[0]
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"• {page.get('page_name', pid)} - {page.get('etat', 'N/A')}")
                            with col2:
                                if st.button("❌", key=f"rm_{coll_id}_{pid}"):
                                    remove_page_from_collection(db, coll_id, pid, user_id=user_id)
                                    st.rerun()
                else:
                    st.caption("Aucune page dans cette collection")

                # Actions
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col2:
                    if st.button("🗑️ Supprimer collection", key=f"del_coll_{coll_id}"):
                        delete_collection(db, coll_id, user_id=user_id)
                        st.success("Collection supprimee")
                        st.rerun()
    else:
        st.info("Aucune collection. Creez-en une pour organiser vos pages.")
