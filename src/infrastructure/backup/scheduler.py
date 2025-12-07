"""
BackupScheduler - Planificateur de sauvegardes.

Responsabilite unique:
----------------------
Planifier et executer les sauvegardes automatiques.

Usage:
------
    scheduler = BackupScheduler(settings)
    scheduler.start()  # Demarre en arriere-plan
    scheduler.stop()   # Arrete le scheduler
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.infrastructure.backup.config import BackupSettings
from src.infrastructure.backup.service import BackupService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class BackupScheduler:
    """
    Planificateur de sauvegardes automatiques.

    Execute les backups selon le schedule configure.
    """

    def __init__(self, settings: BackupSettings):
        """
        Initialise le scheduler.

        Args:
            settings: Configuration des sauvegardes.
        """
        self._settings = settings
        self._service = BackupService(settings)
        self._scheduler = BackgroundScheduler()
        self._running = False

    def start(self) -> None:
        """
        Demarre le scheduler.

        Le scheduler execute les backups selon le cron configure.
        """
        if self._running:
            logger.warning("scheduler_already_running")
            return

        # Ajouter le job de backup
        self._scheduler.add_job(
            self._run_backup,
            trigger=CronTrigger(
                hour=self._settings.backup_schedule_hour,
                minute=self._settings.backup_schedule_minute,
            ),
            id="daily_backup",
            name="Backup quotidien",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True

        logger.info(
            "scheduler_started",
            schedule=f"{self._settings.backup_schedule_hour:02d}:{self._settings.backup_schedule_minute:02d}",
        )

    def stop(self) -> None:
        """Arrete le scheduler."""
        if not self._running:
            return

        self._scheduler.shutdown(wait=True)
        self._running = False

        logger.info("scheduler_stopped")

    def run_now(self) -> dict:
        """
        Execute un backup immediatement.

        Returns:
            Resultat du backup.
        """
        result = self._service.create_backup(name_suffix="manual")
        return {
            "success": result.success,
            "filename": result.filename,
            "size_bytes": result.size_bytes,
            "error": result.error,
        }

    def list_backups(self) -> list:
        """Liste les backups disponibles."""
        return self._service.list_backups()

    def _run_backup(self) -> None:
        """Execute le backup planifie."""
        logger.info("scheduled_backup_started")
        result = self._service.create_backup(name_suffix="scheduled")

        if result.success:
            logger.info(
                "scheduled_backup_completed",
                filename=result.filename,
                size_bytes=result.size_bytes,
            )
        else:
            logger.error("scheduled_backup_failed", error=result.error)

    @property
    def is_running(self) -> bool:
        """Retourne True si le scheduler est actif."""
        return self._running

    @property
    def next_run(self):
        """Retourne la prochaine execution planifiee."""
        if not self._running:
            return None

        job = self._scheduler.get_job("daily_backup")
        if job:
            return job.next_run_time
        return None
