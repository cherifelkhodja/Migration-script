"""
Module utilitaire pour la gestion des fichiers et exports
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Set, Tuple, List, Dict
import pandas as pd


def load_blacklist(filepath: str = "blacklist.csv") -> Tuple[Set[str], Set[str]]:
    """
    Charge la liste noire depuis un fichier CSV

    Args:
        filepath: Chemin vers le fichier CSV

    Returns:
        Tuple (set des page_id, set des page_name)
    """
    blacklist_ids = set()
    blacklist_names = set()

    if not os.path.exists(filepath):
        return blacklist_ids, blacklist_names

    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
    blacklist_ids: Set[str],
    blacklist_names: Set[str]
) -> bool:
    """Vérifie si une page est dans la blacklist"""
    if str(page_id).strip() in blacklist_ids:
        return True
    if page_name and page_name.strip().lower() in blacklist_names:
        return True
    return False


def export_pages_csv(
    pages_final: Dict,
    web_results: Dict,
    countries: List[str],
    languages: List[str],
    output_dir: str = "résultats"
) -> str:
    """
    Exporte la liste des pages en CSV

    Returns:
        Chemin du fichier créé
    """
    results_dir = Path(output_dir)
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_time = datetime.now().isoformat()

    csv_path = results_dir / f"liste_pages_recherche_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "page_id", "page_name", "lien_site", "lien_fb_ad_library",
            "thematique", "type_produits", "moyens_paiements",
            "pays", "langue", "cms", "template", "devise",
            "dernier_scan", "actif", "suivi_hebdomadaire"
        ])

        for pid, data in sorted(pages_final.items(),
                               key=lambda x: x[1].get("ads_active_total", 0),
                               reverse=True):
            web = web_results.get(pid, {})
            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

            writer.writerow([
                pid,
                data.get("page_name", ""),
                data.get("website", ""),
                fb_link,
                web.get("thematique", ""),
                web.get("type_produits", ""),
                web.get("payments", ""),
                ",".join(countries),
                ",".join(languages),
                web.get("cms", ""),
                web.get("theme", ""),
                data.get("currency", ""),
                scan_time,
                "",
                ""
            ])

    return str(csv_path)


def export_ads_csv(
    pages_for_ads: Dict,
    page_ads: Dict,
    countries: List[str],
    output_dir: str = "résultats"
) -> Tuple[str, int]:
    """
    Exporte la liste des annonces en CSV

    Returns:
        Tuple (chemin du fichier, nombre d'annonces exportées)
    """
    results_dir = Path(output_dir)
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = results_dir / f"liste_ads_recherche_{timestamp}.csv"

    def to_str(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val else ""

    ads_exported = 0

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "ad_id", "page_id", "page_name", "ad_creation_time",
            "ad_creative_bodies", "ad_creative_link_captions",
            "ad_creative_link_titles", "ad_snapshot_url",
            "eu_total_reach", "languages", "country",
            "publisher_platforms", "target_ages", "target_gender",
            "beneficiary_payers"
        ])

        for pid in pages_for_ads.keys():
            for ad in page_ads.get(pid, []):
                writer.writerow([
                    ad.get("id", ""),
                    pid,
                    ad.get("page_name", ""),
                    ad.get("ad_creation_time", ""),
                    to_str(ad.get("ad_creative_bodies")),
                    to_str(ad.get("ad_creative_link_captions")),
                    to_str(ad.get("ad_creative_link_titles")),
                    ad.get("ad_snapshot_url", ""),
                    ad.get("eu_total_reach", ""),
                    to_str(ad.get("languages")),
                    ",".join(countries),
                    to_str(ad.get("publisher_platforms")),
                    ad.get("target_ages", ""),
                    ad.get("target_gender", ""),
                    to_str(ad.get("beneficiary_payers"))
                ])
                ads_exported += 1

    return str(csv_path), ads_exported


def export_suivi_csv(
    pages_final: Dict,
    web_results: Dict,
    output_dir: str = "résultats"
) -> str:
    """
    Exporte le fichier de suivi en CSV

    Returns:
        Chemin du fichier créé
    """
    results_dir = Path(output_dir)
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_time = datetime.now().isoformat()

    csv_path = results_dir / f"suivi_site_{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "cle_suivi", "nom_site", "nombre_ads_active",
            "nombre_produits", "date_scan"
        ])

        for pid, data in sorted(pages_final.items(),
                               key=lambda x: x[1].get("ads_active_total", 0),
                               reverse=True):
            web = web_results.get(pid, {})

            writer.writerow([
                "",
                data.get("page_name", ""),
                data.get("ads_active_total", 0),
                web.get("product_count", 0),
                scan_time
            ])

    return str(csv_path)


def create_dataframe_pages(pages_final: Dict, web_results: Dict, countries: List[str]) -> pd.DataFrame:
    """Crée un DataFrame pandas pour les pages"""
    rows = []
    for pid, data in pages_final.items():
        web = web_results.get(pid, {})
        # CMS peut venir de data (détection) ou de web (analyse)
        cms = data.get("cms") or web.get("cms", "Unknown")
        rows.append({
            "Page ID": pid,
            "Nom": data.get("page_name", ""),
            "Site Web": data.get("website", ""),
            "Ads Actives": data.get("ads_active_total", 0),
            "Produits": web.get("product_count", 0),
            "CMS": cms,
            "Thématique": web.get("thematique", ""),
            "Thème": web.get("theme", ""),
            "Devise": data.get("currency", ""),
            "Paiements": web.get("payments", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Ads Actives", ascending=False)
    return df
