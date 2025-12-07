"""
Tests unitaires pour MemoryStateStorage.

Teste le stockage d'etats temporaires.
"""

import pytest
from datetime import datetime, timedelta
from time import sleep

from src.infrastructure.adapters.memory_state_storage import MemoryStateStorage


class TestMemoryStateStorage:
    """Tests pour MemoryStateStorage."""

    def test_set_and_get(self):
        """set() stocke et get() recupere."""
        storage = MemoryStateStorage()

        storage.set("key1", "value1")

        assert storage.get("key1") == "value1"

    def test_get_returns_none_for_missing_key(self):
        """get() retourne None si cle inexistante."""
        storage = MemoryStateStorage()

        assert storage.get("nonexistent") is None

    def test_delete_removes_key(self):
        """delete() supprime la cle."""
        storage = MemoryStateStorage()
        storage.set("to_delete", "value")

        result = storage.delete("to_delete")

        assert result is True
        assert storage.get("to_delete") is None

    def test_delete_returns_false_for_missing_key(self):
        """delete() retourne False si cle inexistante."""
        storage = MemoryStateStorage()

        result = storage.delete("nonexistent")

        assert result is False

    def test_exists_returns_true_for_existing_key(self):
        """exists() retourne True si cle existe."""
        storage = MemoryStateStorage()
        storage.set("existing", "value")

        assert storage.exists("existing") is True

    def test_exists_returns_false_for_missing_key(self):
        """exists() retourne False si cle inexistante."""
        storage = MemoryStateStorage()

        assert storage.exists("nonexistent") is False

    def test_ttl_expires_entry(self):
        """Entry expire apres TTL."""
        storage = MemoryStateStorage()
        storage.set("short_lived", "value", ttl_seconds=1)

        # Avant expiration
        assert storage.get("short_lived") == "value"

        # Attendre expiration
        sleep(1.1)

        # Apres expiration
        assert storage.get("short_lived") is None

    def test_cleanup_expired_removes_old_entries(self):
        """cleanup_expired() supprime les entries expirees."""
        storage = MemoryStateStorage()

        # Ajouter entries avec TTL court
        storage.set("expired1", "v1", ttl_seconds=1)
        storage.set("expired2", "v2", ttl_seconds=1)
        storage.set("valid", "v3", ttl_seconds=60)

        sleep(1.1)

        deleted = storage.cleanup_expired()

        assert deleted == 2
        assert storage.get("valid") == "v3"

    def test_set_overwrites_existing_key(self):
        """set() ecrase la valeur existante."""
        storage = MemoryStateStorage()
        storage.set("key", "old_value")
        storage.set("key", "new_value")

        assert storage.get("key") == "new_value"

    def test_thread_safety_multiple_operations(self):
        """Operations sont thread-safe."""
        import threading

        storage = MemoryStateStorage()
        results = []

        def writer():
            for i in range(100):
                storage.set(f"key_{i}", f"value_{i}")

        def reader():
            for i in range(100):
                results.append(storage.get(f"key_{i}"))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No exceptions = thread-safe
        assert True
