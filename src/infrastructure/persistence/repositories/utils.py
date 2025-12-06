"""
Fonctions utilitaires pour les repositories.
"""
from typing import Dict, Any


def get_etat_from_ads_count(ads_count: int, thresholds: Dict = None) -> str:
    """
    Determine l'etat base sur le nombre d'ads actives.

    Args:
        ads_count: Nombre d'ads actives
        thresholds: Dictionnaire des seuils personnalises (optionnel)

    Returns:
        Etat: inactif, XS, S, M, L, XL, XXL
    """
    if thresholds is None:
        thresholds = {
            "XS": 1,
            "S": 10,
            "M": 20,
            "L": 35,
            "XL": 80,
            "XXL": 150,
        }

    if ads_count == 0:
        return "inactif"
    elif ads_count < thresholds.get("S", 10):
        return "XS"
    elif ads_count < thresholds.get("M", 20):
        return "S"
    elif ads_count < thresholds.get("L", 35):
        return "M"
    elif ads_count < thresholds.get("XL", 80):
        return "L"
    elif ads_count < thresholds.get("XXL", 150):
        return "XL"
    else:
        return "XXL"


def to_str_list(val: Any) -> str:
    """Convertit une valeur en chaine (pour les listes)"""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""
