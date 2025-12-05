"""
Module de gestion des recherches en arrière-plan.
Utilise un ThreadPoolExecutor pour exécuter les recherches sans bloquer l'UI.
"""
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class SearchTask:
    """Représente une tâche de recherche"""
    search_id: int
    future: Optional[Future] = None
    started_at: Optional[datetime] = None
    cancelled: bool = False


class BackgroundSearchWorker:
    """
    Worker pour exécuter les recherches en arrière-plan.

    Singleton pattern pour avoir une seule instance partagée.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 2):
        """
        Initialise le worker.

        Args:
            max_workers: Nombre maximum de recherches simultanées
        """
        if self._initialized:
            return

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="search_worker")
        self.active_tasks: Dict[int, SearchTask] = {}
        self._task_lock = threading.Lock()
        self._running = True
        self._initialized = True

        # Démarrer le thread de surveillance
        self._monitor_thread = threading.Thread(
            target=self._monitor_queue,
            daemon=True,
            name="search_queue_monitor"
        )
        self._monitor_thread.start()

        print("[BackgroundWorker] Initialisé avec {} workers".format(max_workers))

    def _monitor_queue(self):
        """
        Thread de surveillance qui poll la DB pour les nouvelles tâches.
        S'exécute en continu en arrière-plan.
        """
        from app.database import (
            DatabaseManager, get_pending_searches,
            update_search_queue_status, recover_interrupted_searches
        )

        # Au démarrage, récupérer les recherches interrompues
        try:
            db = DatabaseManager()
            interrupted = recover_interrupted_searches(db)
            if interrupted > 0:
                print(f"[BackgroundWorker] {interrupted} recherche(s) marquée(s) comme interrompue(s)")
        except Exception as e:
            print(f"[BackgroundWorker] Erreur récupération: {e}")

        while self._running:
            try:
                # Vérifier s'il y a de la place pour de nouvelles tâches
                with self._task_lock:
                    active_count = len([t for t in self.active_tasks.values() if not t.future.done()])

                if active_count < self.max_workers:
                    db = DatabaseManager()
                    pending = get_pending_searches(db, limit=self.max_workers - active_count)

                    for search in pending:
                        if search.id not in self.active_tasks:
                            self._start_search(search.id)

                # Nettoyer les tâches terminées
                self._cleanup_completed_tasks()

            except Exception as e:
                print(f"[BackgroundWorker] Erreur monitor: {e}")

            # Poll toutes les 3 secondes
            time.sleep(3)

    def _start_search(self, search_id: int):
        """Démarre l'exécution d'une recherche"""
        with self._task_lock:
            if search_id in self.active_tasks:
                return

            task = SearchTask(
                search_id=search_id,
                started_at=datetime.utcnow()
            )

            # Soumettre la tâche au pool
            task.future = self.executor.submit(self._execute_search, search_id)
            self.active_tasks[search_id] = task

            print(f"[BackgroundWorker] Recherche #{search_id} démarrée")

    def _execute_search(self, search_id: int):
        """
        Exécute une recherche complète.
        Cette méthode s'exécute dans un thread séparé.
        """
        from app.database import (
            DatabaseManager, get_search_queue, SearchQueue,
            update_search_queue_status, update_search_queue_progress
        )

        db = DatabaseManager()

        try:
            # Récupérer les paramètres de la recherche
            with db.get_session() as session:
                search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
                if not search or search.status != "pending":
                    return

                keywords = json.loads(search.keywords) if search.keywords else []
                cms_filter = json.loads(search.cms_filter) if search.cms_filter else []
                ads_min = search.ads_min
                countries = search.countries
                languages = search.languages

            # Marquer comme en cours
            update_search_queue_status(db, search_id, "running")

            # Importer et exécuter la recherche
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

            print(f"[BackgroundWorker] Recherche #{search_id} terminée avec succès")

        except Exception as e:
            print(f"[BackgroundWorker] Recherche #{search_id} échouée: {e}")
            update_search_queue_status(db, search_id, "failed", error=str(e)[:500])
            raise

    def _cleanup_completed_tasks(self):
        """Supprime les références aux tâches terminées"""
        with self._task_lock:
            completed = [
                search_id for search_id, task in self.active_tasks.items()
                if task.future and task.future.done()
            ]

            for search_id in completed:
                del self.active_tasks[search_id]

    def submit_search(
        self,
        keywords: list,
        cms_filter: list,
        ads_min: int = 3,
        countries: str = "FR",
        languages: str = "fr",
        user_session: str = None,
        priority: int = 0
    ) -> int:
        """
        Soumet une nouvelle recherche.

        Args:
            keywords: Liste des mots-clés
            cms_filter: Liste des CMS à inclure
            ads_min: Nombre minimum d'ads
            countries: Pays
            languages: Langues
            user_session: ID de session utilisateur
            priority: Priorité (0 = normale)

        Returns:
            ID de la recherche créée
        """
        from app.database import DatabaseManager, create_search_queue

        db = DatabaseManager()
        search_id = create_search_queue(
            db=db,
            keywords=keywords,
            cms_filter=cms_filter,
            ads_min=ads_min,
            countries=countries,
            languages=languages,
            user_session=user_session,
            priority=priority
        )

        print(f"[BackgroundWorker] Recherche #{search_id} ajoutée à la queue")
        return search_id

    def cancel_search(self, search_id: int) -> bool:
        """
        Annule une recherche.

        Note: Si la recherche est en cours, elle continuera jusqu'à la fin
        de la phase actuelle. Seules les recherches 'pending' sont vraiment annulables.

        Args:
            search_id: ID de la recherche

        Returns:
            True si annulée, False sinon
        """
        from app.database import DatabaseManager, cancel_search_queue

        db = DatabaseManager()
        return cancel_search_queue(db, search_id)

    def get_search_status(self, search_id: int) -> Optional[Dict]:
        """
        Récupère le statut d'une recherche.

        Args:
            search_id: ID de la recherche

        Returns:
            Dict avec le statut ou None
        """
        from app.database import DatabaseManager, SearchQueue

        db = DatabaseManager()

        with db.get_session() as session:
            search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()

            if not search:
                return None

            return {
                "id": search.id,
                "status": search.status,
                "phase": search.current_phase,
                "phase_name": search.current_phase_name,
                "progress": search.progress_percent,
                "message": search.progress_message,
                "phases_data": json.loads(search.phases_data) if search.phases_data else [],
                "keywords": json.loads(search.keywords) if search.keywords else [],
                "created_at": search.created_at,
                "started_at": search.started_at,
                "completed_at": search.completed_at,
                "search_log_id": search.search_log_id,
                "error": search.error_message
            }

    def get_active_searches(self, user_session: str = None) -> list:
        """
        Récupère les recherches actives.

        Args:
            user_session: Filtrer par session (optionnel)

        Returns:
            Liste des recherches actives
        """
        from app.database import DatabaseManager, get_active_searches as db_get_active, SearchQueue

        db = DatabaseManager()

        with db.get_session() as session:
            query = session.query(SearchQueue).filter(
                SearchQueue.status.in_(["pending", "running"])
            )

            if user_session:
                query = query.filter(SearchQueue.user_session == user_session)

            searches = query.order_by(SearchQueue.created_at.asc()).all()

            return [
                {
                    "id": s.id,
                    "status": s.status,
                    "phase": s.current_phase,
                    "phase_name": s.current_phase_name,
                    "progress": s.progress_percent,
                    "message": s.progress_message,
                    "keywords": json.loads(s.keywords) if s.keywords else [],
                    "created_at": s.created_at,
                    "started_at": s.started_at,
                }
                for s in searches
            ]

    def get_stats(self) -> Dict:
        """Retourne les statistiques du worker"""
        from app.database import DatabaseManager, get_queue_stats

        db = DatabaseManager()
        queue_stats = get_queue_stats(db)

        with self._task_lock:
            active_in_memory = len(self.active_tasks)

        return {
            "worker_active": self._running,
            "max_workers": self.max_workers,
            "active_in_memory": active_in_memory,
            "queue_stats": queue_stats
        }

    def shutdown(self):
        """Arrête proprement le worker"""
        print("[BackgroundWorker] Arrêt en cours...")
        self._running = False
        self.executor.shutdown(wait=True)
        print("[BackgroundWorker] Arrêté")


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS HELPER GLOBALES
# ═══════════════════════════════════════════════════════════════════════════════

_worker: Optional[BackgroundSearchWorker] = None
_worker_lock = threading.Lock()


def get_worker() -> BackgroundSearchWorker:
    """Retourne l'instance globale du worker"""
    global _worker
    if _worker is None:
        with _worker_lock:
            if _worker is None:
                _worker = BackgroundSearchWorker()
    return _worker


def init_worker(max_workers: int = 2):
    """Initialise le worker (appelé au démarrage de l'app)"""
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = BackgroundSearchWorker(max_workers=max_workers)
    return _worker


def shutdown_worker():
    """Arrête le worker (appelé à l'arrêt de l'app)"""
    global _worker
    if _worker:
        _worker.shutdown()
        _worker = None
