"""
JobQueue Port - Interface de la queue de jobs.

Responsabilite unique:
----------------------
Definir le contrat pour la gestion des jobs asynchrones.
"""

from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional, Callable

from src.domain.entities.job import Job, JobStatus


class JobQueue(ABC):
    """
    Interface pour la queue de jobs.

    Les implementations possibles:
    - MemoryJobQueue: Pour dev/tests
    - RedisJobQueue: Pour production (avec Celery)
    - PostgresJobQueue: Alternative SQL
    """

    @abstractmethod
    def enqueue(self, job: Job) -> Job:
        """
        Ajoute un job a la queue.

        Args:
            job: Job a executer.

        Returns:
            Job enqueue avec ID.
        """
        pass

    @abstractmethod
    def get_by_id(self, job_id: UUID) -> Optional[Job]:
        """
        Recupere un job par son ID.

        Args:
            job_id: ID du job.

        Returns:
            Job si trouve, None sinon.
        """
        pass

    @abstractmethod
    def find_by_user(
        self,
        user_id: UUID,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> list[Job]:
        """
        Recupere les jobs d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur.
            status: Filtrer par statut optionnel.
            limit: Nombre maximum.

        Returns:
            Liste des jobs.
        """
        pass

    @abstractmethod
    def update(self, job: Job) -> Job:
        """
        Met a jour un job.

        Args:
            job: Job a mettre a jour.

        Returns:
            Job mis a jour.
        """
        pass

    @abstractmethod
    def cancel(self, job_id: UUID) -> bool:
        """
        Annule un job.

        Args:
            job_id: ID du job.

        Returns:
            True si annule.
        """
        pass

    @abstractmethod
    def get_next_pending(self) -> Optional[Job]:
        """
        Recupere le prochain job en attente.

        Returns:
            Prochain job PENDING ou None.
        """
        pass

    @abstractmethod
    def count_by_status(self, user_id: Optional[UUID] = None) -> dict[str, int]:
        """
        Compte les jobs par statut.

        Args:
            user_id: Optionnel, filtrer par utilisateur.

        Returns:
            {status: count}.
        """
        pass
