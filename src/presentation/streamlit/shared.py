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
    if "db" not in st.session_state:
        try:
            from src.infrastructure.config import DATABASE_URL
            db = DatabaseManager(DATABASE_URL)
            st.session_state.db = db
        except Exception as e:
            st.error(f"Erreur connexion DB: {e}")
            return None
    return st.session_state.db
