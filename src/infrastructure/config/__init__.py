"""
Configuration de l'application.

Ce module re-exporte les configurations depuis app.config
pour integration dans l'architecture hexagonale.
"""

# Re-export depuis app.config (source de verite)
from app.config import *  # noqa: F401, F403
