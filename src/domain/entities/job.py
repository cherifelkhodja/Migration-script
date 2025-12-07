"""
Job Entity - Entite de job asynchrone.

Responsabilite unique:
----------------------
Representer un job en arriere-plan.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4
from enum import Enum


class JobStatus(Enum):
    """Statuts possibles d'un job."""

    PENDING = "pending"      # En attente d'execution
    RUNNING = "running"      # En cours d'execution
    COMPLETED = "completed"  # Termine avec succes
    FAILED = "failed"        # Termine avec erreur
    CANCELLED = "cancelled"  # Annule


class JobType(Enum):
    """Types de jobs disponibles."""

    SEARCH_ADS = "search_ads"
    ANALYZE_WEBSITES = "analyze_websites"
    DETECT_WINNING = "detect_winning"
    EXPORT_DATA = "export_data"
    CLEANUP = "cleanup"
    SEND_EMAIL = "send_email"


@dataclass
class Job:
    """
    Entite Job.

    Represente une tache asynchrone a executer.

    Attributes:
        id: Identifiant unique du job.
        user_id: ID de l'utilisateur proprietaire.
        type: Type de job.
        status: Statut actuel.
        params: Parametres du job (JSON).
        result: Resultat du job (JSON).
        error: Message d'erreur si echec.
        progress: Progression 0-100.
        created_at: Date de creation.
        started_at: Date de debut d'execution.
        completed_at: Date de fin.
    """

    user_id: UUID
    type: JobType
    params: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def start(self) -> None:
        """Demarre le job."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now()

    def update_progress(self, progress: int) -> None:
        """Met a jour la progression."""
        self.progress = max(0, min(100, progress))

    def complete(self, result: dict[str, Any]) -> None:
        """Termine le job avec succes."""
        self.status = JobStatus.COMPLETED
        self.result = result
        self.progress = 100
        self.completed_at = datetime.now()

    def fail(self, error: str) -> None:
        """Termine le job avec erreur."""
        self.status = JobStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def cancel(self) -> None:
        """Annule le job."""
        if self.status in (JobStatus.PENDING, JobStatus.RUNNING):
            self.status = JobStatus.CANCELLED
            self.completed_at = datetime.now()

    @property
    def is_finished(self) -> bool:
        """True si le job est termine (succes, echec ou annule)."""
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Duree d'execution en secondes."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @classmethod
    def create_search_ads(
        cls,
        user_id: UUID,
        keywords: list[str],
        countries: list[str] = None,
    ) -> "Job":
        """Factory pour job de recherche ads."""
        return cls(
            user_id=user_id,
            type=JobType.SEARCH_ADS,
            params={
                "keywords": keywords,
                "countries": countries or ["FR"],
            },
        )

    @classmethod
    def create_analyze_websites(
        cls,
        user_id: UUID,
        urls: list[str],
    ) -> "Job":
        """Factory pour job d'analyse de sites."""
        return cls(
            user_id=user_id,
            type=JobType.ANALYZE_WEBSITES,
            params={"urls": urls},
        )

    @classmethod
    def create_export(
        cls,
        user_id: UUID,
        export_type: str,
        filters: dict = None,
    ) -> "Job":
        """Factory pour job d'export."""
        return cls(
            user_id=user_id,
            type=JobType.EXPORT_DATA,
            params={
                "export_type": export_type,
                "filters": filters or {},
            },
        )
