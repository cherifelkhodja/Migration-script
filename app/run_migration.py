#!/usr/bin/env python3
"""
Script de migration pour appliquer:
1. Classification Gemini à toutes les pages existantes
2. Pays "FR" à toutes les pages existantes
"""
import os
import sys
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import (
    DatabaseManager,
    migration_add_country_to_all_pages,
    get_all_pages_for_classification,
    get_pages_count,
    update_pages_classification_batch,
    build_taxonomy_prompt,
    init_default_taxonomy
)
from app.gemini_classifier import classify_pages_sync, BATCH_SIZE


def print_stats(db, title=""):
    """Affiche les statistiques actuelles"""
    stats = get_pages_count(db)
    print(f"\n{'='*50}")
    if title:
        print(f"  {title}")
        print(f"{'='*50}")
    print(f"  Total pages:        {stats['total']}")
    print(f"  Avec URL:           {stats['with_url']}")
    print(f"  Classifiées:        {stats['classified']}")
    print(f"  Non classifiées:    {stats['unclassified']}")
    print(f"  Avec FR:            {stats['with_fr']}")
    print(f"  Sans FR:            {stats['without_fr']}")
    print(f"{'='*50}\n")
    return stats


def run_migration_add_france(db):
    """Ajoute FR à toutes les pages"""
    print("\n" + "="*60)
    print("  MIGRATION: Ajout du pays France (FR) à toutes les pages")
    print("="*60)

    stats_before = get_pages_count(db)
    print(f"Pages sans FR avant: {stats_before['without_fr']}")

    if stats_before['without_fr'] == 0:
        print("✓ Toutes les pages ont déjà FR")
        return 0

    print(f"Mise à jour de {stats_before['without_fr']} pages...")
    updated = migration_add_country_to_all_pages(db, "FR")

    print(f"✓ {updated} pages mises à jour avec FR")
    return updated


def run_migration_classification(db, reclassify_all=True, batch_size=100):
    """
    Lance la classification Gemini sur les pages.

    Args:
        db: DatabaseManager
        reclassify_all: Si True, re-classifie toutes les pages. Sinon seulement les non classifiées.
        batch_size: Nombre de pages à traiter par lot
    """
    print("\n" + "="*60)
    print("  MIGRATION: Classification Gemini des pages")
    print("="*60)

    # Vérifier la clé API
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("❌ ERREUR: GEMINI_API_KEY non configurée dans .env")
        return 0

    print(f"✓ Clé API Gemini configurée")

    # Initialiser la taxonomie
    init_default_taxonomy(db)
    taxonomy_text = build_taxonomy_prompt(db)
    if not taxonomy_text:
        print("❌ ERREUR: Aucune taxonomie configurée")
        return 0

    print(f"✓ Taxonomie chargée")

    # Récupérer les pages
    pages = get_all_pages_for_classification(db, include_classified=reclassify_all)
    total_pages = len(pages)

    if total_pages == 0:
        print("✓ Aucune page à classifier")
        return 0

    print(f"\nPages à classifier: {total_pages}")
    print(f"Mode: {'Re-classification de TOUTES les pages' if reclassify_all else 'Seulement les non classifiées'}")
    print(f"Batch size: {batch_size} (avec rate limit 4.5s entre chaque batch Gemini)")

    # Estimer le temps
    gemini_batches = (total_pages + BATCH_SIZE - 1) // BATCH_SIZE
    estimated_time = gemini_batches * 4.5 / 60  # en minutes
    print(f"Temps estimé: ~{estimated_time:.1f} minutes ({gemini_batches} batches Gemini)")

    input("\nAppuyez sur Entrée pour continuer (Ctrl+C pour annuler)...")

    # Traiter par lots
    total_classified = 0
    total_errors = 0

    for i in range(0, total_pages, batch_size):
        batch = pages[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_pages + batch_size - 1) // batch_size

        print(f"\n--- Batch {batch_num}/{total_batches} ({len(batch)} pages) ---")

        def progress_callback(current, total, message):
            print(f"  [{current}/{total}] {message}")

        try:
            # Classifier
            results = classify_pages_sync(batch, taxonomy_text, progress_callback=progress_callback)

            # Préparer les données pour la mise à jour
            classifications = [
                {
                    "page_id": r.page_id,
                    "category": r.category,
                    "subcategory": r.subcategory,
                    "confidence": r.confidence_score
                }
                for r in results
            ]

            # Sauvegarder
            updated = update_pages_classification_batch(db, classifications)

            errors = sum(1 for r in results if r.error)
            total_classified += updated
            total_errors += errors

            print(f"  ✓ Batch terminé: {updated} pages classifiées, {errors} erreurs")

        except Exception as e:
            print(f"  ❌ Erreur batch: {e}")
            total_errors += len(batch)

    print(f"\n{'='*60}")
    print(f"  RÉSULTAT FINAL")
    print(f"{'='*60}")
    print(f"  Pages classifiées: {total_classified}")
    print(f"  Erreurs: {total_errors}")
    print(f"{'='*60}")

    return total_classified


def main():
    """Point d'entrée principal"""
    print("\n" + "="*60)
    print("  SCRIPT DE MIGRATION - Meta Ads Analyzer")
    print("="*60)

    # Connexion à la base
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ ERREUR: DATABASE_URL non configurée")
        sys.exit(1)

    db = DatabaseManager(db_url)
    print(f"✓ Connecté à la base de données")

    # Afficher stats initiales
    print_stats(db, "ÉTAT INITIAL")

    # Menu
    print("\nOptions disponibles:")
    print("  1. Ajouter FR à toutes les pages")
    print("  2. Classifier TOUTES les pages (re-classification)")
    print("  3. Classifier seulement les non classifiées")
    print("  4. Faire 1 + 2 (FR + re-classification complète)")
    print("  5. Afficher les stats et quitter")
    print("  0. Quitter")

    choice = input("\nVotre choix: ").strip()

    if choice == "1":
        run_migration_add_france(db)
    elif choice == "2":
        run_migration_classification(db, reclassify_all=True)
    elif choice == "3":
        run_migration_classification(db, reclassify_all=False)
    elif choice == "4":
        run_migration_add_france(db)
        run_migration_classification(db, reclassify_all=True)
    elif choice == "5":
        print_stats(db, "STATISTIQUES ACTUELLES")
    elif choice == "0":
        print("Au revoir!")
    else:
        print("Choix invalide")

    # Afficher stats finales
    if choice in ["1", "2", "3", "4"]:
        print_stats(db, "ÉTAT FINAL")

    print("\n✓ Migration terminée\n")


if __name__ == "__main__":
    main()
