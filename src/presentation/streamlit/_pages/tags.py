"""
Page Tags - Gestion des tags.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.database import (
    get_all_tags, create_tag, delete_tag, get_pages_by_tag
)
from src.infrastructure.adapters.streamlit_tenant_context import StreamlitTenantContext


def render_tags():
    """Page Tags - Gestion des tags."""
    st.title("🏷️ Tags")
    st.markdown("Creez et gerez vos tags personnalises")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Multi-tenancy: recuperer l'utilisateur courant
    tenant_ctx = StreamlitTenantContext()
    user_id = tenant_ctx.user_uuid

    # Creer un nouveau tag
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        new_tag_name = st.text_input("Nouveau tag", placeholder="Ex: A surveiller")
    with col2:
        new_tag_color = st.color_picker("Couleur", "#3B82F6")
    with col3:
        st.write("")
        st.write("")
        if st.button("➕ Creer", type="primary"):
            if new_tag_name:
                result = create_tag(db, new_tag_name.strip(), new_tag_color, user_id=user_id)
                if result:
                    st.success(f"Tag '{new_tag_name}' cree!")
                    st.rerun()
                else:
                    st.error("Ce tag existe deja")
            else:
                st.error("Nom requis")

    st.markdown("---")

    # Liste des tags
    tags = get_all_tags(db, user_id=user_id)

    if tags:
        st.subheader(f"📋 {len(tags)} tag(s)")

        for tag in tags:
            tag_id = tag["id"]
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.markdown(
                    f"<span style='background-color:{tag['color']};color:white;padding:5px 15px;border-radius:15px;'>{tag['name']}</span>",
                    unsafe_allow_html=True
                )

            with col2:
                # Nombre de pages avec ce tag
                page_ids = get_pages_by_tag(db, tag_id, user_id=user_id)
                st.caption(f"{len(page_ids)} page(s)")

            with col3:
                if st.button("👁️ Voir", key=f"view_tag_{tag_id}"):
                    st.session_state.filter_tag_id = tag_id
                    st.session_state.current_page = "Pages / Shops"
                    st.rerun()

            with col4:
                if st.button("🗑️", key=f"del_tag_{tag_id}"):
                    delete_tag(db, tag_id, user_id=user_id)
                    st.success("Tag supprime")
                    st.rerun()
    else:
        st.info("Aucun tag cree. Creez votre premier tag ci-dessus.")
