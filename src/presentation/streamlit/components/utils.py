"""
Fonctions utilitaires pour le dashboard Streamlit.

Ce module contient les fonctions de calcul et d'export
indépendantes de l'interface utilisateur.
"""

import pandas as pd
from typing import List, Optional


def calculate_page_score(page_data: dict, winning_count: int = 0) -> int:
    """
    Calcule un score de performance pour une page (0-100).

    Basé sur:
    - Nombre d'ads actives (max 40 points)
    - Winning ads (max 30 points)
    - Nombre de produits (max 20 points)
    - Bonus CMS Shopify (10 points)

    Args:
        page_data: Données de la page
        winning_count: Nombre de winning ads

    Returns:
        Score entre 0 et 100
    """
    score = 0

    # Score basé sur le nombre d'ads (max 40 points)
    ads_count = page_data.get("nombre_ads_active", 0) or page_data.get("ads_active_total", 0)
    if ads_count >= 150:
        score += 40
    elif ads_count >= 80:
        score += 35
    elif ads_count >= 35:
        score += 25
    elif ads_count >= 20:
        score += 15
    elif ads_count >= 10:
        score += 10
    elif ads_count >= 1:
        score += 5

    # Score basé sur les winning ads (max 30 points)
    if winning_count >= 10:
        score += 30
    elif winning_count >= 5:
        score += 25
    elif winning_count >= 3:
        score += 20
    elif winning_count >= 1:
        score += 15

    # Score basé sur le nombre de produits (max 20 points)
    products = page_data.get("nombre_produits", 0) or 0
    if products >= 100:
        score += 20
    elif products >= 50:
        score += 15
    elif products >= 20:
        score += 10
    elif products >= 5:
        score += 5

    # Bonus CMS Shopify (10 points)
    cms = page_data.get("cms", "")
    if cms == "Shopify":
        score += 10

    return min(score, 100)


def get_score_color(score: int) -> str:
    """
    Retourne l'emoji de couleur selon le score.

    Args:
        score: Score entre 0 et 100

    Returns:
        Emoji de couleur (vert, jaune, orange, rouge)
    """
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    else:
        return "🔴"


def get_score_level(score: int) -> str:
    """
    Retourne le niveau textuel selon le score.

    Args:
        score: Score entre 0 et 100

    Returns:
        Niveau (Excellent, Bon, Moyen, Faible)
    """
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Bon"
    elif score >= 40:
        return "Moyen"
    else:
        return "Faible"


def export_to_csv(data: list, columns: list = None, separator: str = ";") -> str:
    """
    Convertit une liste de dictionnaires en CSV.

    Args:
        data: Liste de dictionnaires
        columns: Colonnes à inclure (optionnel)
        separator: Séparateur (défaut: ";")

    Returns:
        Contenu CSV en string
    """
    if not data:
        return ""

    df = pd.DataFrame(data)
    if columns:
        df = df[[c for c in columns if c in df.columns]]

    return df.to_csv(index=False, sep=separator)


def df_to_csv(df: pd.DataFrame, separator: str = ";") -> bytes:
    """
    Convertit un DataFrame en bytes CSV pour téléchargement.

    Args:
        df: DataFrame à convertir
        separator: Séparateur (défaut: ";")

    Returns:
        Contenu CSV en bytes UTF-8
    """
    return df.to_csv(index=False, sep=separator).encode("utf-8")


def format_number(value: int, suffix: str = "") -> str:
    """
    Formate un nombre avec séparateur de milliers.

    Args:
        value: Nombre à formater
        suffix: Suffixe optionnel

    Returns:
        Nombre formaté
    """
    formatted = f"{value:,}".replace(",", " ")
    return f"{formatted}{suffix}" if suffix else formatted


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Formate un pourcentage.

    Args:
        value: Valeur à formater
        decimals: Nombre de décimales

    Returns:
        Pourcentage formaté
    """
    return f"{value:.{decimals}f}%"


def format_time_elapsed(seconds: float) -> str:
    """
    Formate un temps écoulé en format lisible.

    Args:
        seconds: Temps en secondes

    Returns:
        Temps formaté (ex: "1m 30s" ou "45.2s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.0f}s"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Tronque un texte s'il dépasse la longueur max.

    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        suffix: Suffixe si tronqué

    Returns:
        Texte tronqué ou original
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def get_delta_indicator(current: int, previous: int) -> tuple:
    """
    Calcule le delta et retourne l'indicateur visuel.

    Args:
        current: Valeur actuelle
        previous: Valeur précédente

    Returns:
        Tuple (delta_value, delta_emoji, delta_color)
    """
    if previous == 0:
        if current > 0:
            return (current, "🆕", "green")
        return (0, "—", "gray")

    delta = current - previous
    pct = (delta / previous) * 100

    if delta > 0:
        return (f"+{delta} ({pct:+.1f}%)", "📈", "green")
    elif delta < 0:
        return (f"{delta} ({pct:.1f}%)", "📉", "red")
    else:
        return ("0", "➡️", "gray")
