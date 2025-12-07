"""
Backup Infrastructure - Sauvegarde automatisee.

Responsabilite:
---------------
Gerer les sauvegardes PostgreSQL automatisees.

Features:
---------
- Backup quotidien automatique
- Retention configurable
- Restauration point-in-time
- Upload vers S3 (optionnel)
"""

from src.infrastructure.backup.service import BackupService
from src.infrastructure.backup.scheduler import BackupScheduler

__all__ = ["BackupService", "BackupScheduler"]
