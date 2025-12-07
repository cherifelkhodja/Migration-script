"""
Repository pour les parametres (AppSettings, UserSettings).
"""
from datetime import datetime
from typing import Dict, Optional

from src.infrastructure.persistence.models import AppSettings, UserSettings


# Constantes pour les cles de parametres
SETTING_GEMINI_MODEL = "gemini_model_name"
SETTING_GEMINI_MODEL_DEFAULT = "gemini-2.5-flash-lite"


def get_app_setting(db, key: str, default: str = None) -> Optional[str]:
    """Recupere un parametre de l'application."""
    with db.get_session() as session:
        setting = session.query(AppSettings).filter(AppSettings.key == key).first()
        if setting:
            return setting.value
        return default


def set_app_setting(db, key: str, value: str, description: str = None) -> bool:
    """Definit ou met a jour un parametre de l'application."""
    with db.get_session() as session:
        setting = session.query(AppSettings).filter(AppSettings.key == key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
            setting.updated_at = datetime.utcnow()
        else:
            setting = AppSettings(
                key=key,
                value=value,
                description=description
            )
            session.add(setting)
        return True


def get_all_app_settings(db) -> Dict[str, str]:
    """Recupere tous les parametres de l'application."""
    with db.get_session() as session:
        settings = session.query(AppSettings).all()
        return {s.key: s.value for s in settings}


def get_setting(db, key: str, default: str = None) -> Optional[str]:
    """Recupere un parametre utilisateur."""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        return setting.setting_value if setting else default


def set_setting(db, key: str, value: str) -> bool:
    """Definit un parametre utilisateur."""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        if setting:
            setting.setting_value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = UserSettings(setting_key=key, setting_value=value)
            session.add(setting)
        return True


def get_all_settings(db) -> Dict[str, str]:
    """Recupere tous les parametres utilisateur."""
    with db.get_session() as session:
        settings = session.query(UserSettings).all()
        return {s.setting_key: s.setting_value for s in settings}
