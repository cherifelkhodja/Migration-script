"""
Module de gestion des recherches en arriere-plan.

Utilise un ThreadPoolExecutor pour executer les recherches sans bloquer l'UI.
"""
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class SearchTask:
    """Represente une tache de recherche"""
    search_id: int
    future: Optional[Future] = None
    started_at: Optional[datetime] = None
    cancelled: bool = False


class BackgroundSearchWorker:
    """
    Worker pour executer les recherches en arriere-plan.

    Singleton pattern pour avoir une seule instance partagee.
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
            max_workers: Nombre maximum de recherches simultanees
        """
        if self._initialized:
            return

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="search_worker")
        self.active_tasks: Dict[int, SearchTask] = {}
        self._task_lock = threading.Lock()
        self._running = True
        self._initialized = True

        # Demarrer le thread de surveillance
        self._monitor_thread = threading.Thread(
            target=self._monitor_queue,
            daemon=True,
            name="search_queue_monitor"
        )
        self._monitor_thread.start()

        print("[BackgroundWorker] Initialise avec {} workers".format(max_workers))

    def _monitor_queue(self):
        """
        Thread de surveillance qui poll la DB pour les nouvelles taches.
        S'execute en continu en arriere-plan.
        """
        # Import local pour eviter les imports circulaires
        from src.infrastructure.persistence.database import (
            DatabaseManager, get_pending_searches,
            update_search_queue_status, recover_interrupted_searches
        )

        # Au demarrage, recuperer les recherches interrompues
        try:
            db = DatabaseManager()
            interrupted = recover_interrupted_searches(db)
            if interrupted > 0:
                print(f"[BackgroundWorker] {interrupted} recherche(s) marquee(s) comme interrompue(s)")
        except Exception as e:
            print(f"[BackgroundWorker] Erreur recuperation: {e}")

        while self._running:
            try:
                # Verifier s'il y a de la place pour de nouvelles taches
                with self._task_lock:
                    active_count = len([t for t in self.active_tasks.values() if not t.future.done()])

                if active_count < self.max_workers:
                    db = DatabaseManager()
                    pending = get_pending_searches(db, limit=self.max_workers - active_count)

                    for search in pending:
                        if search.id not in self.active_tasks:
                            self._start_search(search.id)

                # Nettoyer les taches terminees
                self._cleanup_completed_tasks()

            except Exception as e:
                print(f"[BackgroundWorker] Erreur monitor: {e}")

            # Poll toutes les 3 secondes
            time.sleep(3)

    def _start_search(self, search_id: int):
        """Demarre l'execution d'une recherche"""
        with self._task_lock:
            if search_id in self.active_tasks:
                return

            task = SearchTask(
                search_id=search_id,
                started_at=datetime.utcnow()
            )

            # Soumettre la tache au pool
            task.future = self.executor.submit(self._execute_search, search_id)
            self.active_tasks[search_id] = task

            print(f"[BackgroundWorker] Recherche #{search_id} demarree")

    def _execute_search(self, search_id: int):
        """
        Execute une recherche complete.
        Cette methode s'execute dans un thread separe.
        """
        # Import local pour eviter les imports circulaires
        from src.infrastructure.persistence.database import (
            DatabaseManager, SearchQueue,
            update_search_queue_status, update_search_queue_progress
        )

        db = DatabaseManager()

        try:
            # Recuperer les parametres de la recherche
            with db.get_session() as session:
                search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
                if not search or search.status != "pending":
                    return

                keywords = json.loads(search.keywords) if search.keywords else []
                cms_filter = json.loads(search.cms_filter) if search.cms_filter else []
                ads_min = search.ads_min
                countries = search.countries
                languages = search.languages
                user_id = search.user_id  # Multi-tenancy

            # Marquer comme en cours
            update_search_queue_status(db, search_id, "running")

            # Importer et executer la recherche
            from src.application.use_cases.search_executor import execute_background_search

            result = execute_background_search(
                db=db,
                search_id=search_id,
                keywords=keywords,
                cms_filter=cms_filter,
                ads_min=ads_min,
                countries=countries,
                languages=languages,
                user_id=user_id
            )

            # Marquer comme termine
            update_search_queue_status(
                db,
                search_id,
                "completed",
                search_log_id=result.get("search_log_id")
            )

            print(f"[BackgroundWorker] Recherche #{search_id} terminee avec succes")

        except Exception as e:
            print(f"[BackgroundWorker] Recherche #{search_id} echouee: {e}")
            update_search_queue_status(db, search_id, "failed", error=str(e)[:500])
            raise

    def _cleanup_completed_tasks(self):
        """Supprime les references aux taches terminees"""
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
        priority: int = 0,
        user_id=None
    ) -> int:
        """
        Soumet une nouvelle recherche.

        Args:
            keywords: Liste des mots-cles
            cms_filter: Liste des CMS a inclure
            ads_min: Nombre minimum d'ads
            countries: Pays
            languages: Langues
            user_session: ID de session utilisateur
            priority: Priorite (0 = normale)
            user_id: UUID de l'utilisateur pour multi-tenancy

        Returns:
            ID de la recherche creee
        """
        from src.infrastructure.persistence.database import DatabaseManager, create_search_queue

        db = DatabaseManager()
        search_id = create_search_queue(
            db=db,
            keywords=keywords,
            cms_filter=cms_filter,
            ads_min=ads_min,
            countries=countries,
            languages=languages,
            user_session=user_session,
            priority=priority,
            user_id=user_id
        )

        print(f"[BackgroundWorker] Recherche #{search_id} ajoutee a la queue")
        return search_id

    def cancel_search(self, search_id: int) -> bool:
        """
        Annule une recherche.

        Note: Si la recherche est en cours, elle continuera jusqu'a la fin
        de la phase actuelle. Seules les recherches 'pending' sont vraiment annulables.

        Args:
            search_id: ID de la recherche

        Returns:
            True si annulee, False sinon
        """
        from src.infrastructure.persistence.database import DatabaseManager, cancel_search_queue

        db = DatabaseManager()
        return cancel_search_queue(db, search_id)

    def get_search_status(self, search_id: int) -> Optional[Dict]:
        """
        Recupere le statut d'une recherche.

        Args:
            search_id: ID de la recherche

        Returns:
            Dict avec le statut ou None
        """
        from src.infrastructure.persistence.database import DatabaseManager, SearchQueue

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
        Recupere les recherches actives.

        Args:
            user_session: Filtrer par session (optionnel)

        Returns:
            Liste des recherches actives
        """
        from src.infrastructure.persistence.database import DatabaseManager, SearchQueue

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
                    "phases_data": json.loads(s.phases_data) if s.phases_data else [],
                    "created_at": s.created_at,
                    "started_at": s.started_at,
                }
                for s in searches
            ]

    def get_stats(self) -> Dict:
        """Retourne les statistiques du worker"""
        from src.infrastructure.persistence.database import DatabaseManager, get_queue_stats

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
        """Arrete proprement le worker"""
        print("[BackgroundWorker] Arret en cours...")
        self._running = False
        self.executor.shutdown(wait=True)
        print("[BackgroundWorker] Arrete")


# ===========================================================================
# FONCTIONS HELPER GLOBALES
# ===========================================================================

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
    """Initialise le worker (appele au demarrage de l'app)"""
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = BackgroundSearchWorker(max_workers=max_workers)
    return _worker


def shutdown_worker():
    """Arrete le worker (appele a l'arret de l'app)"""
    global _worker
    if _worker:
        _worker.shutdown()
        _worker = None
