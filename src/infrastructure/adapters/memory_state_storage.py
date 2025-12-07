"""
MemoryStateStorage - Implementation en memoire du StateStorage.

Responsabilite unique:
----------------------
Stocker les etats temporaires en memoire (pour dev/tests).

Note:
-----
En production, utiliser RedisStateStorage pour la persistence et le partage
entre instances.
"""

from typing import Optional
from datetime import datetime, timedelta
from threading import Lock

from src.domain.ports.state_storage import StateStorage


class MemoryStateStorage(StateStorage):
    """
    StateStorage en memoire avec TTL.

    Thread-safe via Lock. Les entries expirees sont nettoyees
    automatiquement lors des acces.

    Example:
        >>> storage = MemoryStateStorage()
        >>> storage.set("oauth_state_123", "google", ttl_seconds=300)
        >>> storage.get("oauth_state_123")
        'google'
    """

    def __init__(self):
        """Initialise le storage."""
        self._data: dict[str, tuple[str, datetime]] = {}
        self._lock = Lock()

    def set(self, key: str, value: str, ttl_seconds: int = 600) -> None:
        """
        Stocke une valeur avec TTL.

        Args:
            key: Cle unique.
            value: Valeur a stocker.
            ttl_seconds: Duree de vie en secondes.
        """
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        with self._lock:
            self._data[key] = (value, expires_at)

    def get(self, key: str) -> Optional[str]:
        """
        Recupere une valeur.

        Args:
            key: Cle a recuperer.

        Returns:
            Valeur si existe et non expiree, None sinon.
        """
        with self._lock:
            entry = self._data.get(key)

            if not entry:
                return None

            value, expires_at = entry

            if datetime.now() > expires_at:
                del self._data[key]
                return None

            return value

    def delete(self, key: str) -> bool:
        """
        Supprime une valeur.

        Args:
            key: Cle a supprimer.

        Returns:
            True si supprime, False si inexistant.
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """
        Verifie si une cle existe et n'est pas expiree.

        Args:
            key: Cle a verifier.

        Returns:
            True si existe et valide, False sinon.
        """
        return self.get(key) is not None

    def cleanup_expired(self) -> int:
        """
        Nettoie les entries expirees.

        Returns:
            Nombre d'entries supprimees.
        """
        now = datetime.now()
        deleted = 0

        with self._lock:
            expired_keys = [
                k for k, (_, exp) in self._data.items()
                if now > exp
            ]
            for key in expired_keys:
                del self._data[key]
                deleted += 1

        return deleted
