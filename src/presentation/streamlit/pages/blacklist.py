"""
Page Blacklist - Gestion des pages exclues.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.database import (
    add_to_blacklist, remove_from_blacklist, get_blacklist
)


def render_blacklist():
    """Page Blacklist - Gestion des pages blacklistees."""
    st.title("🚫 Blacklist")
    st.markdown("Gerer les pages exclues des recherches")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    # Formulaire d'ajout
    st.subheader("➕ Ajouter une page")
    with st.form("add_blacklist_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_page_id = st.text_input("Page ID *", placeholder="123456789")
        with col2:
            new_page_name = st.text_input("Nom de la page", placeholder="Nom optionnel")

        new_raison = st.text_input("Raison", placeholder="Raison du blacklistage")

        submitted = st.form_submit_button("➕ Ajouter a la blacklist", type="primary")

        if submitted:
            if new_page_id:
                if add_to_blacklist(db, new_page_id.strip(), new_page_name.strip(), new_raison.strip()):
                    st.success(f"Page {new_page_id} ajoutee a la blacklist")
                    st.rerun()
                else:
                    st.warning("Cette page est deja dans la blacklist")
            else:
                st.error("Page ID requis")

    st.markdown("---")

    # Liste des pages blacklistees
    st.subheader("📋 Pages en blacklist")

    try:
        blacklist = get_blacklist(db)

        if blacklist:
            # Barre de recherche
            search_bl = st.text_input("🔍 Rechercher", placeholder="Filtrer par ID ou nom...")

            # Filtrer si recherche
            if search_bl:
                search_lower = search_bl.lower()
                blacklist = [
                    entry for entry in blacklist
                    if search_lower in str(entry.get("page_id", "")).lower()
                    or search_lower in str(entry.get("page_name", "")).lower()
                ]

            st.info(f"🚫 {len(blacklist)} pages en blacklist")

            # Affichage en tableau avec actions
            for entry in blacklist:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                    with col1:
                        st.write(f"**{entry.get('page_name') or 'Sans nom'}**")
                        st.caption(f"ID: `{entry['page_id']}`")

                    with col2:
                        if entry.get('raison'):
                            st.write(f"📝 {entry['raison']}")
                        else:
                            st.caption("Pas de raison")

                    with col3:
                        if entry.get('added_at'):
                            st.write(f"📅 {entry['added_at'].strftime('%Y-%m-%d %H:%M')}")

                    with col4:
                        if st.button("🗑️ Retirer", key=f"remove_bl_{entry['page_id']}", help="Retirer de la blacklist"):
                            if remove_from_blacklist(db, entry['page_id']):
                                st.success("Retire de la blacklist")
                                st.rerun()

                    st.markdown("---")
        else:
            st.info("Aucune page en blacklist")

        # Statistiques
        if blacklist:
            st.subheader("📊 Statistiques")
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total pages blacklistees", len(blacklist))

            with col2:
                with_reason = sum(1 for e in blacklist if e.get("raison"))
                st.metric("Avec raison", with_reason)

    except Exception as e:
        st.error(f"Erreur: {e}")
