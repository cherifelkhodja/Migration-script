"""
Fonctions partagees entre les pages du dashboard.
"""
import streamlit as st

from src.infrastructure.persistence.database import DatabaseManager


def get_database() -> DatabaseManager:
    """
    Retourne une instance de DatabaseManager.
    Utilise le cache Streamlit pour eviter les reconnexions.
    """
    if st.session_state.get("db") is None:
        try:
            from src.infrastructure.config import DATABASE_URL
            db = DatabaseManager(DATABASE_URL)
            db.create_tables()  # S'assurer que les tables existent
            st.session_state.db = db
        except Exception as e:
            import traceback
            st.error(f"Erreur connexion DB: {e}")
            st.code(traceback.format_exc())
            return None
    return st.session_state.db
