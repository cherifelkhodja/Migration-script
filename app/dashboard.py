"""
Dashboard Streamlit - Shim de compatibilite.

Ce module redirige vers src.presentation.streamlit.dashboard pour la compatibilite
avec le code existant et les scripts de lancement.
"""

# Re-export depuis la nouvelle localisation
from src.presentation.streamlit.dashboard import *  # noqa: F401, F403
from src.presentation.streamlit.dashboard import main  # noqa: F401

# Pour permettre l'execution directe: python -m app.dashboard ou streamlit run app/dashboard.py
if __name__ == "__main__":
    main()
