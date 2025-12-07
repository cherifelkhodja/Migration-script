"""
Jobs Router - Endpoints de gestion des background jobs.

Responsabilite unique:
----------------------
Exposer les endpoints de creation et suivi des jobs.
Delegue l'execution a la queue de jobs.

Endpoints:
----------
- GET /jobs: Lister ses jobs
- GET /jobs/{id}: Statut d'un job
- POST /jobs/search: Creer un job de recherche
- POST /jobs/analyze: Creer un job d'analyse
- POST /jobs/export: Creer un job d'export
- DELETE /jobs/{id}: Annuler un job
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID
from typing import Optional

from src.presentation.api.jobs.schemas import (
    JobResponse,
    JobListResponse,
    CreateSearchJobRequest,
    CreateAnalyzeJobRequest,
    CreateExportJobRequest,
    JobStatusCountsResponse,
)
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.entities.job import Job, JobStatus, JobType
from src.domain.ports.job_queue import JobQueue
from src.infrastructure.adapters.memory_job_queue import MemoryJobQueue
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Singleton de la queue (en production, injecter via DI avec Redis)
_job_queue = MemoryJobQueue(auto_start=True)


def get_job_queue() -> JobQueue:
    """Retourne la JobQueue."""
    return _job_queue


def _job_to_response(job: Job) -> JobResponse:
    """Convertit un Job en JobResponse."""
    return JobResponse(
        id=job.id,
        type=job.type.value,
        status=job.status.value,
        params=job.params,
        result=job.result,
        error=job.error,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="Lister ses jobs",
    description="Retourne les jobs de l'utilisateur.",
)
def list_jobs(
    status_filter: Optional[str] = Query(None, description="Filtrer par statut"),
    limit: int = Query(50, ge=1, le=100, description="Nombre max"),
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Liste les jobs de l'utilisateur connecte.
    """
    job_status = None
    if status_filter:
        try:
            job_status = JobStatus(status_filter)
        except ValueError:
            pass

    jobs = queue.find_by_user(
        user_id=user.id,
        status=job_status,
        limit=limit,
    )

    counts = queue.count_by_status(user.id)

    return JobListResponse(
        items=[_job_to_response(j) for j in jobs],
        total=len(jobs),
        counts=counts,
    )


@router.get(
    "/counts",
    response_model=JobStatusCountsResponse,
    summary="Compteurs de jobs",
    description="Retourne le nombre de jobs par statut.",
)
def get_job_counts(
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Retourne les compteurs de jobs par statut.
    """
    counts = queue.count_by_status(user.id)
    return JobStatusCountsResponse(**counts)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Statut d'un job",
    description="Retourne le statut detaille d'un job.",
)
def get_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Recupere le statut d'un job specifique.
    """
    job = queue.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job non trouve",
        )

    if job.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    return _job_to_response(job)


@router.post(
    "/search",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Creer un job de recherche",
    description="Lance une recherche d'ads en arriere-plan.",
)
def create_search_job(
    data: CreateSearchJobRequest,
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Cree un job de recherche d'annonces.
    Le job s'execute en arriere-plan.
    """
    job = Job.create_search_ads(
        user_id=user.id,
        keywords=data.keywords,
        countries=data.countries,
    )

    # Ajouter les langues aux params
    job.params["languages"] = data.languages

    queue.enqueue(job)

    logger.info(
        "search_job_created",
        user_id=str(user.id),
        job_id=str(job.id),
        keywords=data.keywords,
    )

    return _job_to_response(job)


@router.post(
    "/analyze",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Creer un job d'analyse",
    description="Lance une analyse de sites en arriere-plan.",
)
def create_analyze_job(
    data: CreateAnalyzeJobRequest,
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Cree un job d'analyse de sites web.
    Le job s'execute en arriere-plan.
    """
    job = Job.create_analyze_websites(
        user_id=user.id,
        urls=data.urls,
    )

    job.params["country_code"] = data.country_code

    queue.enqueue(job)

    logger.info(
        "analyze_job_created",
        user_id=str(user.id),
        job_id=str(job.id),
        url_count=len(data.urls),
    )

    return _job_to_response(job)


@router.post(
    "/export",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Creer un job d'export",
    description="Lance un export de donnees en arriere-plan.",
)
def create_export_job(
    data: CreateExportJobRequest,
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Cree un job d'export de donnees.
    Le job s'execute en arriere-plan.
    """
    if data.export_type not in ("csv", "excel", "json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type d'export invalide (csv, excel, json)",
        )

    job = Job.create_export(
        user_id=user.id,
        export_type=data.export_type,
        filters=data.filters,
    )

    queue.enqueue(job)

    logger.info(
        "export_job_created",
        user_id=str(user.id),
        job_id=str(job.id),
        export_type=data.export_type,
    )

    return _job_to_response(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Annuler un job",
    description="Annule un job en attente ou en cours.",
)
def cancel_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """
    Annule un job.
    Seuls les jobs PENDING ou RUNNING peuvent etre annules.
    """
    job = queue.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job non trouve",
        )

    if job.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    if job.is_finished:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le job est deja termine",
        )

    queue.cancel(job_id)

    logger.info(
        "job_cancelled",
        user_id=str(user.id),
        job_id=str(job_id),
    )
