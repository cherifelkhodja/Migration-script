"""
Gestion de la blacklist de pages.

Ce module fournit des fonctions pour charger et verifier
la liste noire des pages a exclure.
"""

import csv
import os


def load_blacklist(filepath: str = "blacklist.csv") -> tuple[set[str], set[str]]:
    """
    Charge la liste noire depuis un fichier CSV.

    Args:
        filepath: Chemin vers le fichier CSV.

    Returns:
        Tuple (set des page_id, set des page_name en minuscules).
    """
    blacklist_ids: set[str] = set()
    blacklist_names: set[str] = set()

    if not os.path.exists(filepath):
        return blacklist_ids, blacklist_names

    try:
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                pid = row.get("page_id", "").strip()
                pname = row.get("page_name", "").strip()
                if pid:
                    blacklist_ids.add(pid)
                if pname:
                    blacklist_names.add(pname.lower())
    except Exception:
        pass

    return blacklist_ids, blacklist_names


def is_blacklisted(
    page_id: str,
    page_name: str,
    blacklist_ids: set[str],
    blacklist_names: set[str],
) -> bool:
    """
    Verifie si une page est dans la blacklist.

    Args:
        page_id: ID de la page.
        page_name: Nom de la page.
        blacklist_ids: Set des page_id blacklistes.
        blacklist_names: Set des page_name blacklistes (en minuscules).

    Returns:
        True si la page est blacklistee.
    """
    if str(page_id).strip() in blacklist_ids:
        return True
    if page_name and page_name.strip().lower() in blacklist_names:
        return True
    return False
