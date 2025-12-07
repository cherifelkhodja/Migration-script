"""
Fonctions utilitaires pour les repositories.

Ce module contient les fonctions partagees entre plusieurs repositories,
notamment la classification des pages par niveau d'activite publicitaire.
"""
from typing import Dict, Any, List, Union


# Seuils par defaut pour la classification des pages par activite publicitaire
# Ces valeurs sont calibrees sur l'observation du marche e-commerce europeen
DEFAULT_STATE_THRESHOLDS = {
    "XS": 1,    # 1-9 ads: Tres petite activite (test ou debut)
    "S": 10,    # 10-19 ads: Petite activite (lancement)
    "M": 20,    # 20-34 ads: Activite moyenne (croissance)
    "L": 35,    # 35-79 ads: Grande activite (etabli)
    "XL": 80,   # 80-149 ads: Tres grande activite (performant)
    "XXL": 150, # 150+ ads: Activite massive (leader/scaler)
}


def get_etat_from_ads_count(
    ads_count: int,
    thresholds: Dict[str, int] = None
) -> str:
    """
    Determine l'etat (niveau d'activite) d'une page selon son nombre d'ads actives.

    La classification utilise une echelle de taille inspiree des tailles de vetements
    (XS a XXL) pour representer intuitivement le niveau d'activite publicitaire
    d'un annonceur. Plus une page a d'ads actives simultanement, plus elle est
    consideree comme un "gros" annonceur.

    Classification par defaut:
        - inactif: 0 ads (page dormante ou arretee)
        - XS: 1-9 ads (test ou demarrage)
        - S: 10-19 ads (petite activite)
        - M: 20-34 ads (activite moyenne)
        - L: 35-79 ads (grande activite)
        - XL: 80-149 ads (tres grande activite)
        - XXL: 150+ ads (activite massive, scalers/leaders)

    Args:
        ads_count: Nombre d'annonces actives de la page
        thresholds: Dictionnaire optionnel de seuils personnalises.
                    Cles: "XS", "S", "M", "L", "XL", "XXL"
                    Valeurs: seuil minimum pour ce niveau

    Returns:
        Code etat: "inactif", "XS", "S", "M", "L", "XL" ou "XXL"

    Example:
        >>> get_etat_from_ads_count(0)
        'inactif'
        >>> get_etat_from_ads_count(25)
        'M'
        >>> get_etat_from_ads_count(200)
        'XXL'

    Note:
        Les seuils par defaut sont optimises pour le marche e-commerce.
        Ils peuvent etre ajustes via les parametres de recherche pour
        d'autres secteurs (SaaS, apps mobiles, etc.).
    """
    if thresholds is None:
        thresholds = DEFAULT_STATE_THRESHOLDS

    # Cas special: aucune ad active
    if ads_count == 0:
        return "inactif"

    # Evaluation sequentielle des seuils (ordre croissant)
    # Chaque condition verifie si on est EN DESSOUS du seuil suivant
    if ads_count < thresholds.get("S", 10):
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
    """
    Convertit une valeur (scalaire ou liste) en chaine de caracteres.

    Utile pour normaliser les donnees avant stockage en base de donnees,
    notamment pour les champs qui peuvent recevoir des listes de l'API Meta.

    Args:
        val: Valeur a convertir (str, int, list, None, etc.)

    Returns:
        Chaine de caracteres:
            - Si liste: elements joints par ", "
            - Si scalaire: conversion str()
            - Si None/vide: chaine vide ""

    Example:
        >>> to_str_list(["FR", "BE", "CH"])
        'FR, BE, CH'
        >>> to_str_list("simple")
        'simple'
        >>> to_str_list(None)
        ''
    """
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""
