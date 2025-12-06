#!/usr/bin/env python3
"""
Script de nettoyage des doublons dans la base de données.
Garde uniquement les entrées les plus récentes pour chaque ad_id.

Usage:
    python scripts/cleanup_duplicates.py [--dry-run]

Options:
    --dry-run   Affiche les doublons sans les supprimer
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import func, text
from app.database import (
    DatabaseManager, AdsRecherche, WinningAds, SuiviPage, PageRecherche
)


def cleanup_ads_recherche(db, dry_run=False):
    """
    Nettoie les doublons dans liste_ads_recherche.
    Garde uniquement l'entrée la plus récente pour chaque ad_id.
    """
    print("\n" + "="*60)
    print("📋 LISTE_ADS_RECHERCHE - Recherche de doublons par ad_id")
    print("="*60)

    with db.get_session() as session:
        # Trouver les ad_id avec plusieurs entrées
        duplicates = session.query(
            AdsRecherche.ad_id,
            func.count(AdsRecherche.id).label('count')
        ).group_by(
            AdsRecherche.ad_id
        ).having(
            func.count(AdsRecherche.id) > 1
        ).all()

        if not duplicates:
            print("✅ Aucun doublon trouvé")
            return 0

        print(f"🔍 {len(duplicates)} ad_id avec doublons trouvés")

        total_deleted = 0

        for ad_id, count in duplicates:
            # Récupérer toutes les entrées pour cet ad_id
            entries = session.query(AdsRecherche).filter(
                AdsRecherche.ad_id == ad_id
            ).order_by(
                AdsRecherche.date_scan.desc()
            ).all()

            # Garder la première (plus récente), supprimer les autres
            to_keep = entries[0]
            to_delete = entries[1:]

            if dry_run:
                print(f"  [DRY-RUN] ad_id={ad_id}: garder #{to_keep.id} ({to_keep.date_scan}), supprimer {len(to_delete)} autres")
            else:
                for entry in to_delete:
                    session.delete(entry)
                total_deleted += len(to_delete)

        if not dry_run:
            session.commit()
            print(f"🗑️ {total_deleted} doublons supprimés")
        else:
            print(f"📊 {sum(c-1 for _, c in duplicates)} doublons seraient supprimés")

        return total_deleted


def cleanup_winning_ads(db, dry_run=False):
    """
    Nettoie les doublons dans winning_ads.
    Garde uniquement l'entrée la plus récente pour chaque ad_id.
    """
    print("\n" + "="*60)
    print("🏆 WINNING_ADS - Recherche de doublons par ad_id")
    print("="*60)

    with db.get_session() as session:
        # Trouver les ad_id avec plusieurs entrées
        duplicates = session.query(
            WinningAds.ad_id,
            func.count(WinningAds.id).label('count')
        ).group_by(
            WinningAds.ad_id
        ).having(
            func.count(WinningAds.id) > 1
        ).all()

        if not duplicates:
            print("✅ Aucun doublon trouvé")
            return 0

        print(f"🔍 {len(duplicates)} ad_id avec doublons trouvés")

        total_deleted = 0

        for ad_id, count in duplicates:
            # Récupérer toutes les entrées pour cet ad_id
            entries = session.query(WinningAds).filter(
                WinningAds.ad_id == ad_id
            ).order_by(
                WinningAds.date_scan.desc()
            ).all()

            # Garder la première (plus récente), supprimer les autres
            to_keep = entries[0]
            to_delete = entries[1:]

            if dry_run:
                print(f"  [DRY-RUN] ad_id={ad_id}: garder #{to_keep.id} ({to_keep.date_scan}), supprimer {len(to_delete)} autres")
            else:
                for entry in to_delete:
                    session.delete(entry)
                total_deleted += len(to_delete)

        if not dry_run:
            session.commit()
            print(f"🗑️ {total_deleted} doublons supprimés")
        else:
            print(f"📊 {sum(c-1 for _, c in duplicates)} doublons seraient supprimés")

        return total_deleted


def cleanup_suivi_page(db, dry_run=False):
    """
    Nettoie les doublons dans suivi_page.
    Garde uniquement l'entrée la plus récente pour chaque page_id par jour.
    (Plusieurs scans le même jour = doublon)
    """
    print("\n" + "="*60)
    print("📈 SUIVI_PAGE - Recherche de doublons par page_id/jour")
    print("="*60)

    with db.get_session() as session:
        # Utiliser une requête SQL brute pour grouper par page_id et date (jour)
        # Trouver les page_id avec plusieurs entrées le même jour
        sql = text("""
            SELECT page_id, DATE(date_scan) as scan_date, COUNT(*) as cnt
            FROM suivi_page
            GROUP BY page_id, DATE(date_scan)
            HAVING COUNT(*) > 1
        """)

        result = session.execute(sql).fetchall()

        if not result:
            print("✅ Aucun doublon trouvé")
            return 0

        print(f"🔍 {len(result)} combinaisons page_id/jour avec doublons")

        total_deleted = 0

        for page_id, scan_date, count in result:
            # Récupérer toutes les entrées pour cette page ce jour-là
            entries = session.query(SuiviPage).filter(
                SuiviPage.page_id == page_id,
                func.date(SuiviPage.date_scan) == scan_date
            ).order_by(
                SuiviPage.date_scan.desc()
            ).all()

            # Garder la première (plus récente), supprimer les autres
            to_keep = entries[0]
            to_delete = entries[1:]

            if dry_run:
                print(f"  [DRY-RUN] page_id={page_id} ({scan_date}): garder #{to_keep.id}, supprimer {len(to_delete)} autres")
            else:
                for entry in to_delete:
                    session.delete(entry)
                total_deleted += len(to_delete)

        if not dry_run:
            session.commit()
            print(f"🗑️ {total_deleted} doublons supprimés")
        else:
            print(f"📊 {sum(c-1 for _, _, c in result)} doublons seraient supprimés")

        return total_deleted


def show_stats(db):
    """Affiche les statistiques actuelles"""
    print("\n" + "="*60)
    print("📊 STATISTIQUES ACTUELLES")
    print("="*60)

    with db.get_session() as session:
        pages_count = session.query(func.count(PageRecherche.id)).scalar()
        ads_count = session.query(func.count(AdsRecherche.id)).scalar()
        winning_count = session.query(func.count(WinningAds.id)).scalar()
        suivi_count = session.query(func.count(SuiviPage.id)).scalar()

        # Compter les ad_id uniques
        ads_unique = session.query(func.count(func.distinct(AdsRecherche.ad_id))).scalar()
        winning_unique = session.query(func.count(func.distinct(WinningAds.ad_id))).scalar()

        print(f"📄 Pages (liste_page_recherche): {pages_count:,}")
        print(f"📢 Ads (liste_ads_recherche): {ads_count:,} total, {ads_unique:,} uniques")
        if ads_count > ads_unique:
            print(f"   ⚠️ {ads_count - ads_unique:,} doublons potentiels")
        print(f"🏆 Winning Ads: {winning_count:,} total, {winning_unique:,} uniques")
        if winning_count > winning_unique:
            print(f"   ⚠️ {winning_count - winning_unique:,} doublons potentiels")
        print(f"📈 Suivi Pages: {suivi_count:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Nettoie les doublons dans la base de données"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les doublons sans les supprimer"
    )
    args = parser.parse_args()

    print("🧹 NETTOYAGE DES DOUBLONS")
    print("=" * 60)

    if args.dry_run:
        print("⚠️ MODE DRY-RUN - Aucune modification ne sera effectuée")

    try:
        db = DatabaseManager()
        print("✅ Connexion à la base de données établie")

        # Afficher les stats avant
        show_stats(db)

        # Nettoyer chaque table
        ads_deleted = cleanup_ads_recherche(db, dry_run=args.dry_run)
        winning_deleted = cleanup_winning_ads(db, dry_run=args.dry_run)
        suivi_deleted = cleanup_suivi_page(db, dry_run=args.dry_run)

        # Résumé
        print("\n" + "="*60)
        print("📊 RÉSUMÉ")
        print("="*60)

        total = ads_deleted + winning_deleted + suivi_deleted

        if args.dry_run:
            print(f"Total doublons qui seraient supprimés: {total}")
            print("\n💡 Relancez sans --dry-run pour effectuer le nettoyage")
        else:
            print(f"Total doublons supprimés: {total}")

            # Afficher les stats après
            if total > 0:
                show_stats(db)

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
