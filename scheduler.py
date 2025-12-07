#!/usr/bin/env python3
"""
Scheduler APScheduler pour l'automatisation des recherches Meta Ads.

Ce worker execute deux types de taches en arriere-plan :
1. Scans programmes (daily/weekly/monthly)
2. Recherches de la SearchQueue soumises via l'UI

Architecture:
-------------
Utilise APScheduler en mode BlockingScheduler avec deux jobs :
- check_and_run_scheduled_scans : toutes les 5 minutes
- process_search_queue : toutes les 30 secondes

Deploiement Railway:
--------------------
Deployer comme service "worker" separe du web (dashboard).
Configuration recommandee :
- Service type: Worker
- Command: python scheduler.py
- Variables: META_ACCESS_TOKEN, DATABASE_URL

Variables d'environnement requises:
-----------------------------------
- META_ACCESS_TOKEN : Token API Meta Ads (obligatoire)
- DATABASE_URL : URL PostgreSQL (obligatoire)

Gestion des interruptions:
--------------------------
Au demarrage, le scheduler recupere les recherches interrompues
(status="running" mais worker arrete) et les remet en "pending".

Execution des scans:
--------------------
Pour chaque scan programme dont next_run <= now :
1. Recupere les keywords du scan
2. Appelle Meta API pour chaque keyword
3. Groupe les ads par page_id
4. Calcule l'etat (XS-XXL) selon le nombre d'ads
5. Sauvegarde les pages avec >= MIN_ADS_SUIVI ads
6. Met a jour next_run selon la frequence

Traitement de la queue:
-----------------------
Pour chaque recherche en "pending" :
1. Marque comme "running"
2. Execute via execute_background_search()
3. Marque comme "completed" ou "failed"

Lock anti-parallele:
--------------------
Variable globale _search_queue_running empeche les executions
concurrentes du traitement de queue.

Logs:
-----
Format: timestamp - logger - level - message
Niveau: INFO par defaut

Arret propre:
-------------
Ctrl+C declenche scheduler.shutdown() via KeyboardInterrupt.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import des modules de l'application
try:
    from app.database import (
        DatabaseManager, get_scheduled_scans, mark_scan_executed,
        upsert_page_recherche, get_pending_searches, update_search_queue_status,
        SearchQueue, recover_interrupted_searches
    )
    from app.meta_api import MetaAdsClient
    from app.web_analyzer import WebAnalyzer
    from app.config import DATABASE_URL, MIN_ADS_SUIVI
except ImportError as e:
    logger.error(f"Erreur d'import: {e}")
    logger.error("Assurez-vous que les modules sont accessibles")
    sys.exit(1)


def get_meta_token() -> str:
    """Récupère le token Meta depuis les variables d'environnement"""
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        raise ValueError("META_ACCESS_TOKEN non défini dans les variables d'environnement")
    return token


def execute_scan(scan: dict, db: DatabaseManager, meta_client: MetaAdsClient) -> dict:
    """
    Exécute un scan programmé.

    Args:
        scan: Dictionnaire contenant les infos du scan
        db: Instance DatabaseManager
        meta_client: Client Meta API

    Returns:
        dict avec les résultats du scan
    """
    scan_id = scan["id"]
    scan_name = scan["name"]
    keywords = scan.get("keywords", "").split(",")
    countries = scan.get("countries", "FR").split(",")
    languages = scan.get("languages", "fr").split(",")

    logger.info(f"▶ Démarrage scan '{scan_name}' (ID: {scan_id})")
    logger.info(f"  Keywords: {keywords}")
    logger.info(f"  Pays: {countries}, Langues: {languages}")

    results = {
        "scan_id": scan_id,
        "scan_name": scan_name,
        "keywords_processed": 0,
        "pages_found": 0,
        "pages_saved": 0,
        "errors": []
    }

    web_analyzer = WebAnalyzer()

    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue

        try:
            logger.info(f"  🔍 Recherche: '{keyword}'")

            # Recherche des ads
            ads = meta_client.search_ads(
                keyword=keyword,
                countries=countries,
                languages=languages
            )

            # Grouper par page
            pages_ads = {}
            for ad in ads:
                page_id = ad.get("page_id")
                if page_id:
                    if page_id not in pages_ads:
                        pages_ads[page_id] = {
                            "page_id": page_id,
                            "page_name": ad.get("page_name", ""),
                            "ads": [],
                            "keywords": set()
                        }
                    pages_ads[page_id]["ads"].append(ad)
                    pages_ads[page_id]["keywords"].add(keyword)

            results["pages_found"] += len(pages_ads)

            # Analyser et sauvegarder les pages significatives
            for page_id, page_data in pages_ads.items():
                ads_count = len(page_data["ads"])

                if ads_count < MIN_ADS_SUIVI:
                    continue

                # Déterminer l'état
                if ads_count >= 150:
                    etat = "XXL"
                elif ads_count >= 80:
                    etat = "XL"
                elif ads_count >= 35:
                    etat = "L"
                elif ads_count >= 20:
                    etat = "M"
                elif ads_count >= 10:
                    etat = "S"
                else:
                    etat = "XS"

                # Analyser le site web (simplifié pour le scheduler)
                first_ad = page_data["ads"][0]
                lien_site = ""
                cms = "Inconnu"

                # Essayer de trouver le lien du site
                link_captions = first_ad.get("ad_creative_link_captions", [])
                if link_captions and isinstance(link_captions, list):
                    lien_site = link_captions[0] if link_captions else ""

                # Sauvegarder la page
                page_info = {
                    "page_id": page_id,
                    "page_name": page_data["page_name"],
                    "lien_site": lien_site,
                    "lien_fb_ad_library": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=FR&view_all_page_id={page_id}",
                    "keywords": "|".join(page_data["keywords"]),
                    "pays": ",".join(countries),
                    "langue": ",".join(languages),
                    "cms": cms,
                    "etat": etat,
                    "nombre_ads_active": ads_count
                }

                upsert_page_recherche(db, page_info)
                results["pages_saved"] += 1
                logger.info(f"    ✅ Page sauvegardée: {page_data['page_name']} ({ads_count} ads, {etat})")

            results["keywords_processed"] += 1

        except Exception as e:
            error_msg = f"Erreur keyword '{keyword}': {str(e)}"
            logger.error(f"    ❌ {error_msg}")
            results["errors"].append(error_msg)

    # Marquer le scan comme exécuté
    mark_scan_executed(db, scan_id)
    logger.info(f"✅ Scan '{scan_name}' terminé: {results['pages_saved']} pages sauvegardées")

    return results


def check_and_run_scheduled_scans():
    """
    Vérifie et exécute les scans dont l'heure est venue.
    Appelé périodiquement par le scheduler.
    """
    logger.info("=" * 60)
    logger.info("🔄 Vérification des scans programmés...")

    try:
        # Connexion à la base
        db = DatabaseManager(DATABASE_URL)

        # Token Meta
        meta_token = get_meta_token()
        meta_client = MetaAdsClient(meta_token)

        # Récupérer les scans actifs
        scans = get_scheduled_scans(db, active_only=True)
        logger.info(f"📋 {len(scans)} scan(s) actif(s) trouvé(s)")

        now = datetime.utcnow()
        executed_count = 0

        for scan in scans:
            next_run = scan.get("next_run")

            # Vérifier si c'est l'heure
            if next_run and next_run <= now:
                try:
                    results = execute_scan(scan, db, meta_client)
                    executed_count += 1

                    # Log des résultats
                    logger.info(f"📊 Résultats scan '{scan['name']}':")
                    logger.info(f"   - Keywords traités: {results['keywords_processed']}")
                    logger.info(f"   - Pages trouvées: {results['pages_found']}")
                    logger.info(f"   - Pages sauvegardées: {results['pages_saved']}")
                    if results['errors']:
                        logger.warning(f"   - Erreurs: {len(results['errors'])}")

                except Exception as e:
                    logger.error(f"❌ Erreur lors du scan '{scan['name']}': {e}")
            else:
                if next_run:
                    time_until = next_run - now
                    logger.info(f"⏳ '{scan['name']}': prochain run dans {time_until}")
                else:
                    logger.info(f"⏸️ '{scan['name']}': pas de next_run défini")

        if executed_count > 0:
            logger.info(f"✅ {executed_count} scan(s) exécuté(s)")
        else:
            logger.info("💤 Aucun scan à exécuter pour le moment")

    except Exception as e:
        logger.error(f"❌ Erreur générale: {e}")

    logger.info("=" * 60)


# Variable globale pour éviter les exécutions parallèles
_search_queue_running = False


def process_search_queue():
    """
    Traite les recherches en file d'attente (SearchQueue).
    Appelé périodiquement par le scheduler.
    """
    global _search_queue_running

    # Éviter les exécutions parallèles
    if _search_queue_running:
        logger.debug("Traitement queue déjà en cours, skip...")
        return

    _search_queue_running = True

    try:
        db = DatabaseManager(DATABASE_URL)

        # Récupérer les recherches interrompues au redémarrage
        try:
            interrupted = recover_interrupted_searches(db)
            if interrupted > 0:
                logger.info(f"⚠️ {interrupted} recherche(s) interrompue(s) récupérée(s)")
        except Exception as e:
            logger.error(f"Erreur récupération recherches interrompues: {e}")

        # Récupérer les recherches en attente (max 1 à la fois pour éviter surcharge)
        pending = get_pending_searches(db, limit=1)

        if not pending:
            return

        search = pending[0]
        search_id = search.id

        logger.info("=" * 60)
        logger.info(f"🔍 Traitement recherche #{search_id}")

        try:
            # Récupérer les paramètres
            with db.get_session() as session:
                search_data = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
                if not search_data or search_data.status != "pending":
                    logger.warning(f"Recherche #{search_id} n'est plus en attente")
                    return

                keywords = json.loads(search_data.keywords) if search_data.keywords else []
                cms_filter = json.loads(search_data.cms_filter) if search_data.cms_filter else []
                ads_min = search_data.ads_min
                countries = search_data.countries
                languages = search_data.languages

            logger.info(f"   Keywords: {keywords[:3]}{'...' if len(keywords) > 3 else ''}")
            logger.info(f"   CMS: {cms_filter}")
            logger.info(f"   Pays: {countries}")

            # Marquer comme en cours
            update_search_queue_status(db, search_id, "running")

            # Exécuter la recherche
            from app.search_executor import execute_background_search

            result = execute_background_search(
                db=db,
                search_id=search_id,
                keywords=keywords,
                cms_filter=cms_filter,
                ads_min=ads_min,
                countries=countries,
                languages=languages
            )

            # Marquer comme terminé
            update_search_queue_status(
                db,
                search_id,
                "completed",
                search_log_id=result.get("search_log_id")
            )

            logger.info(f"✅ Recherche #{search_id} terminée avec succès")
            logger.info(f"   Pages trouvées: {result.get('pages_saved', 0)}")

        except Exception as e:
            logger.error(f"❌ Recherche #{search_id} échouée: {e}")
            update_search_queue_status(db, search_id, "failed", error=str(e)[:500])

        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Erreur traitement queue: {e}")
    finally:
        _search_queue_running = False


def main():
    """Point d'entrée principal du scheduler"""
    logger.info("🚀 Démarrage du Meta Ads Scheduler")
    logger.info(f"📅 Heure actuelle: {datetime.utcnow()}")

    # Vérifier la configuration
    try:
        get_meta_token()
        logger.info("✅ META_ACCESS_TOKEN configuré")
    except ValueError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)

    # Tester la connexion DB
    try:
        db = DatabaseManager(DATABASE_URL)
        scans = get_scheduled_scans(db)
        logger.info(f"✅ Connexion DB OK - {len(scans)} scans programmés")
    except Exception as e:
        logger.error(f"❌ Erreur connexion DB: {e}")
        sys.exit(1)

    # Récupérer les recherches interrompues au démarrage
    try:
        interrupted = recover_interrupted_searches(db)
        if interrupted > 0:
            logger.info(f"⚠️ {interrupted} recherche(s) interrompue(s) au démarrage")
    except Exception as e:
        logger.warning(f"Erreur récupération: {e}")

    # Vérifier s'il y a des recherches en attente
    try:
        pending = get_pending_searches(db, limit=10)
        logger.info(f"📋 {len(pending)} recherche(s) en attente dans la queue")
    except Exception as e:
        logger.warning(f"Erreur vérification queue: {e}")

    # Créer le scheduler
    scheduler = BlockingScheduler()

    # Job 1: Vérifier les scans programmés toutes les 5 minutes
    scheduler.add_job(
        check_and_run_scheduled_scans,
        trigger=IntervalTrigger(minutes=5),
        id='check_scans',
        name='Vérification des scans programmés',
        replace_existing=True
    )

    # Job 2: Traiter la queue de recherches toutes les 30 secondes
    scheduler.add_job(
        process_search_queue,
        trigger=IntervalTrigger(seconds=30),
        id='process_queue',
        name='Traitement queue de recherches',
        replace_existing=True
    )

    # Exécuter immédiatement au démarrage
    logger.info("🔍 Vérification initiale des scans...")
    check_and_run_scheduled_scans()

    # Traiter immédiatement les recherches en attente
    logger.info("🔍 Traitement initial de la queue...")
    process_search_queue()

    logger.info("=" * 60)
    logger.info("⏰ Scheduler démarré:")
    logger.info("   - Scans programmés: toutes les 5 minutes")
    logger.info("   - Queue de recherches: toutes les 30 secondes")
    logger.info("   Appuyez sur Ctrl+C pour arrêter")
    logger.info("=" * 60)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Arrêt du scheduler")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
