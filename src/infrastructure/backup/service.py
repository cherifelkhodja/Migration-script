"""
BackupService - Service de sauvegarde PostgreSQL.

Responsabilite unique:
----------------------
Executer et gerer les sauvegardes de base de donnees.

Usage:
------
    service = BackupService(settings)
    result = service.create_backup()
    service.restore_backup("backup_2024-01-15.sql.gz")
"""

import subprocess
import gzip
import os
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse

from src.infrastructure.backup.config import BackupSettings
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BackupResult:
    """
    Resultat d'une operation de backup.

    Attributes:
        success: True si operation reussie.
        filename: Nom du fichier de backup.
        size_bytes: Taille du fichier.
        duration_seconds: Duree de l'operation.
        error: Message d'erreur si echec.
    """

    success: bool
    filename: Optional[str] = None
    size_bytes: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


class BackupService:
    """
    Service de sauvegarde PostgreSQL.

    Cree, liste et restaure les backups.
    """

    def __init__(self, settings: BackupSettings):
        """
        Initialise le service de backup.

        Args:
            settings: Configuration des sauvegardes.
        """
        self._settings = settings
        self._backup_dir = settings.backup_path

        # Creer le repertoire si necessaire
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        # Parser l'URL de la base
        self._db_config = self._parse_database_url(settings.database_url)

    def create_backup(self, name_suffix: str = "") -> BackupResult:
        """
        Cree un backup de la base de donnees.

        Args:
            name_suffix: Suffixe optionnel pour le nom.

        Returns:
            BackupResult avec le resultat.
        """
        start_time = datetime.now()

        # Generer le nom du fichier
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        suffix = f"_{name_suffix}" if name_suffix else ""
        filename = f"backup_{timestamp}{suffix}.sql.gz"
        filepath = self._backup_dir / filename

        logger.info("backup_started", filename=filename)

        try:
            # Construire la commande pg_dump
            env = os.environ.copy()
            if self._db_config.get("password"):
                env["PGPASSWORD"] = self._db_config["password"]

            cmd = [
                "pg_dump",
                "-h", self._db_config.get("host", "localhost"),
                "-p", str(self._db_config.get("port", 5432)),
                "-U", self._db_config.get("user", "postgres"),
                "-d", self._db_config.get("database", "postgres"),
                "--format=plain",
                "--no-owner",
                "--no-acl",
            ]

            # Executer pg_dump et compresser
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            with gzip.open(filepath, "wb") as f:
                while True:
                    chunk = process.stdout.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            process.wait()

            if process.returncode != 0:
                error = process.stderr.read().decode()
                raise Exception(f"pg_dump failed: {error}")

            duration = (datetime.now() - start_time).total_seconds()
            size = filepath.stat().st_size

            logger.info(
                "backup_completed",
                filename=filename,
                size_bytes=size,
                duration_seconds=duration,
            )

            # Nettoyer les anciens backups
            self._cleanup_old_backups()

            return BackupResult(
                success=True,
                filename=filename,
                size_bytes=size,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error("backup_failed", error=str(e))
            return BackupResult(success=False, error=str(e))

    def restore_backup(self, filename: str) -> BackupResult:
        """
        Restaure un backup.

        Args:
            filename: Nom du fichier a restaurer.

        Returns:
            BackupResult avec le resultat.

        Warning:
            Cette operation ecrase les donnees existantes!
        """
        start_time = datetime.now()
        filepath = self._backup_dir / filename

        if not filepath.exists():
            return BackupResult(success=False, error=f"Fichier non trouve: {filename}")

        logger.warning("restore_started", filename=filename)

        try:
            env = os.environ.copy()
            if self._db_config.get("password"):
                env["PGPASSWORD"] = self._db_config["password"]

            # Decompresser et restaurer
            cmd = [
                "psql",
                "-h", self._db_config.get("host", "localhost"),
                "-p", str(self._db_config.get("port", 5432)),
                "-U", self._db_config.get("user", "postgres"),
                "-d", self._db_config.get("database", "postgres"),
            ]

            with gzip.open(filepath, "rb") as f:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
                process.communicate(input=f.read())

            if process.returncode != 0:
                raise Exception("psql restore failed")

            duration = (datetime.now() - start_time).total_seconds()

            logger.info(
                "restore_completed",
                filename=filename,
                duration_seconds=duration,
            )

            return BackupResult(
                success=True,
                filename=filename,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error("restore_failed", error=str(e))
            return BackupResult(success=False, error=str(e))

    def list_backups(self) -> List[dict]:
        """
        Liste les backups disponibles.

        Returns:
            Liste de dicts avec filename, size, created_at.
        """
        backups = []

        for filepath in sorted(self._backup_dir.glob("backup_*.sql.gz"), reverse=True):
            stat = filepath.stat()
            backups.append({
                "filename": filepath.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime),
            })

        return backups

    def _cleanup_old_backups(self) -> int:
        """
        Supprime les backups plus vieux que la retention.

        Returns:
            Nombre de fichiers supprimes.
        """
        cutoff = datetime.now() - timedelta(days=self._settings.backup_retention_days)
        deleted = 0

        for filepath in self._backup_dir.glob("backup_*.sql.gz"):
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            if mtime < cutoff:
                filepath.unlink()
                deleted += 1
                logger.info("backup_deleted", filename=filepath.name)

        return deleted

    def _parse_database_url(self, url: str) -> dict:
        """Parse une URL de base de donnees."""
        if not url:
            return {}

        parsed = urlparse(url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") or "postgres",
        }
