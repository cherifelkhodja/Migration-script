"""
Backup Config - Configuration des sauvegardes.

Responsabilite unique:
----------------------
Configurer les parametres de backup.

Variables:
----------
- BACKUP_DIR: Repertoire de stockage local
- BACKUP_RETENTION_DAYS: Nombre de jours de retention
- BACKUP_S3_BUCKET: Bucket S3 (optionnel)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


class BackupSettings(BaseSettings):
    """
    Configuration des sauvegardes.

    Chargee depuis les variables d'environnement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Base de donnees
    database_url: str = ""

    # Stockage local
    backup_dir: str = "/tmp/backups"
    backup_retention_days: int = 7

    # S3 (optionnel)
    backup_s3_bucket: str = ""
    backup_s3_prefix: str = "backups/"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-west-1"

    # Schedule (cron)
    backup_schedule_hour: int = 3  # 3h du matin
    backup_schedule_minute: int = 0

    @property
    def backup_path(self) -> Path:
        """Retourne le chemin de backup."""
        return Path(self.backup_dir)

    @property
    def s3_enabled(self) -> bool:
        """Retourne True si S3 est configure."""
        return bool(
            self.backup_s3_bucket
            and self.aws_access_key_id
            and self.aws_secret_access_key
        )


@lru_cache
def get_backup_settings() -> BackupSettings:
    """Retourne la configuration backup (cached)."""
    return BackupSettings()
