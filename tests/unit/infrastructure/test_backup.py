"""
Tests unitaires pour le service de backup.

Teste la configuration et le service de sauvegarde.
"""

import pytest
from pathlib import Path

from src.infrastructure.backup.config import BackupSettings, get_backup_settings
from src.infrastructure.backup.service import BackupService, BackupResult


class TestBackupSettings:
    """Tests pour la configuration backup."""

    def test_default_values(self):
        """BackupSettings a des valeurs par defaut."""
        settings = BackupSettings()

        assert settings.backup_dir == "/tmp/backups"
        assert settings.backup_retention_days == 7
        assert settings.backup_schedule_hour == 3

    def test_backup_path_returns_path(self):
        """backup_path retourne un Path."""
        settings = BackupSettings(backup_dir="/custom/path")

        assert isinstance(settings.backup_path, Path)
        assert str(settings.backup_path) == "/custom/path"

    def test_s3_disabled_without_credentials(self):
        """s3_enabled est False sans credentials."""
        settings = BackupSettings()

        assert settings.s3_enabled is False

    def test_s3_enabled_with_credentials(self):
        """s3_enabled est True avec credentials."""
        settings = BackupSettings(
            backup_s3_bucket="my-bucket",
            aws_access_key_id="AKIATEST",
            aws_secret_access_key="secret"
        )

        assert settings.s3_enabled is True


class TestBackupService:
    """Tests pour le service de backup."""

    def test_parse_database_url_full(self):
        """_parse_database_url parse une URL complete."""
        settings = BackupSettings(
            database_url="postgresql://user:pass@host:5433/mydb"
        )
        service = BackupService(settings)

        config = service._db_config

        assert config["host"] == "host"
        assert config["port"] == 5433
        assert config["user"] == "user"
        assert config["password"] == "pass"
        assert config["database"] == "mydb"

    def test_parse_database_url_minimal(self):
        """_parse_database_url gere URL minimale."""
        settings = BackupSettings(
            database_url="postgresql://localhost/testdb"
        )
        service = BackupService(settings)

        config = service._db_config

        assert config["host"] == "localhost"
        assert config["database"] == "testdb"

    def test_parse_database_url_empty(self):
        """_parse_database_url gere URL vide."""
        settings = BackupSettings(database_url="")
        service = BackupService(settings)

        assert service._db_config == {}

    def test_list_backups_empty_dir(self, tmp_path):
        """list_backups retourne liste vide si pas de backups."""
        settings = BackupSettings(backup_dir=str(tmp_path))
        service = BackupService(settings)

        backups = service.list_backups()

        assert backups == []

    def test_list_backups_finds_files(self, tmp_path):
        """list_backups trouve les fichiers de backup."""
        settings = BackupSettings(backup_dir=str(tmp_path))
        service = BackupService(settings)

        # Creer des fichiers de test
        (tmp_path / "backup_20240101_120000.sql.gz").touch()
        (tmp_path / "backup_20240102_120000.sql.gz").touch()
        (tmp_path / "other_file.txt").touch()

        backups = service.list_backups()

        assert len(backups) == 2
        assert all("backup_" in b["filename"] for b in backups)

    def test_backup_result_dataclass(self):
        """BackupResult est un dataclass valide."""
        result = BackupResult(
            success=True,
            filename="test.sql.gz",
            size_bytes=1024,
            duration_seconds=5.5
        )

        assert result.success is True
        assert result.filename == "test.sql.gz"
        assert result.size_bytes == 1024
        assert result.duration_seconds == 5.5
        assert result.error is None

    def test_backup_result_failure(self):
        """BackupResult peut representer un echec."""
        result = BackupResult(
            success=False,
            error="Connection refused"
        )

        assert result.success is False
        assert result.error == "Connection refused"
        assert result.filename is None
