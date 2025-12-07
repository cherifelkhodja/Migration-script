"""
MemoryJobQueue - Implementation in-memory de la queue de jobs.

Responsabilite unique:
----------------------
Gerer une queue de jobs en memoire avec worker thread.
Pour production, utiliser RedisJobQueue avec Celery.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, Callable, Any
from threading import Thread, Lock, Event
from queue import Queue
import time

from src.domain.entities.job import Job, JobStatus, JobType
from src.domain.ports.job_queue import JobQueue
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MemoryJobQueue(JobQueue):
    """
    Implementation in-memory de la queue de jobs.

    Inclut un worker thread qui execute les jobs en arriere-plan.
    Thread-safe avec verrous.
    """

    def __init__(self, auto_start: bool = True):
        """
        Initialise la queue.

        Args:
            auto_start: Demarre le worker automatiquement.
        """
        self._jobs: dict[UUID, Job] = {}
        self._pending_queue: Queue[UUID] = Queue()
        self._lock = Lock()
        self._stop_event = Event()
        self._handlers: dict[JobType, Callable] = {}
        self._worker_thread: Optional[Thread] = None

        if auto_start:
            self.start_worker()

    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[[Job], dict[str, Any]],
    ) -> None:
        """
        Enregistre un handler pour un type de job.

        Args:
            job_type: Type de job.
            handler: Fonction qui execute le job et retourne le resultat.
        """
        self._handlers[job_type] = handler

    def enqueue(self, job: Job) -> Job:
        """Ajoute un job a la queue."""
        with self._lock:
            self._jobs[job.id] = job
            self._pending_queue.put(job.id)

        logger.info(
            "job_enqueued",
            job_id=str(job.id),
            job_type=job.type.value,
            user_id=str(job.user_id),
        )

        return job

    def get_by_id(self, job_id: UUID) -> Optional[Job]:
        """Recupere un job par son ID."""
        return self._jobs.get(job_id)

    def find_by_user(
        self,
        user_id: UUID,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> list[Job]:
        """Recupere les jobs d'un utilisateur."""
        with self._lock:
            user_jobs = [
                j for j in self._jobs.values()
                if j.user_id == user_id
            ]

            if status:
                user_jobs = [j for j in user_jobs if j.status == status]

            # Trier par date decroissante
            user_jobs.sort(key=lambda j: j.created_at, reverse=True)

            return user_jobs[:limit]

    def update(self, job: Job) -> Job:
        """Met a jour un job."""
        with self._lock:
            self._jobs[job.id] = job
        return job

    def cancel(self, job_id: UUID) -> bool:
        """Annule un job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and not job.is_finished:
                job.cancel()
                logger.info("job_cancelled", job_id=str(job_id))
                return True
            return False

    def get_next_pending(self) -> Optional[Job]:
        """Recupere le prochain job en attente."""
        try:
            job_id = self._pending_queue.get_nowait()
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                return job
            return None
        except Exception:
            return None

    def count_by_status(self, user_id: Optional[UUID] = None) -> dict[str, int]:
        """Compte les jobs par statut."""
        with self._lock:
            jobs = self._jobs.values()
            if user_id:
                jobs = [j for j in jobs if j.user_id == user_id]

            counts = {}
            for status in JobStatus:
                counts[status.value] = sum(1 for j in jobs if j.status == status)

            return counts

    def start_worker(self) -> None:
        """Demarre le worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._worker_thread = Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("job_worker_started")

    def stop_worker(self) -> None:
        """Arrete le worker thread."""
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("job_worker_stopped")

    def _worker_loop(self) -> None:
        """Boucle principale du worker."""
        while not self._stop_event.is_set():
            job = self.get_next_pending()

            if job:
                self._execute_job(job)
            else:
                time.sleep(0.5)  # Attendre avant de re-verifier

    def _execute_job(self, job: Job) -> None:
        """Execute un job."""
        logger.info(
            "job_started",
            job_id=str(job.id),
            job_type=job.type.value,
        )

        job.start()
        self.update(job)

        handler = self._handlers.get(job.type)

        if not handler:
            job.fail(f"No handler for job type: {job.type.value}")
            self.update(job)
            logger.error("job_no_handler", job_type=job.type.value)
            return

        try:
            result = handler(job)
            job.complete(result)
            logger.info(
                "job_completed",
                job_id=str(job.id),
                duration_s=job.duration_seconds,
            )
        except Exception as e:
            job.fail(str(e))
            logger.error(
                "job_failed",
                job_id=str(job.id),
                error=str(e),
            )

        self.update(job)

    def clear(self) -> None:
        """Vide la queue (pour tests)."""
        with self._lock:
            self._jobs.clear()
            while not self._pending_queue.empty():
                self._pending_queue.get_nowait()
