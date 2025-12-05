"""
Module de cache en mémoire avec TTL (Time To Live).
Cache léger pour les données fréquemment accédées.
"""
import time
from typing import Any, Optional, Dict, Callable
from threading import Lock
from functools import wraps
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Entrée de cache avec timestamp d'expiration"""
    value: Any
    expires_at: float  # Timestamp d'expiration


class TTLCache:
    """
    Cache en mémoire avec Time-To-Live (TTL).

    Features:
    - TTL configurable par entrée
    - Thread-safe
    - Nettoyage automatique des entrées expirées
    - Statistiques d'utilisation
    """

    def __init__(self, default_ttl: int = 60, max_size: int = 1000):
        """
        Args:
            default_ttl: TTL par défaut en secondes
            max_size: Nombre maximum d'entrées (évite les memory leaks)
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur du cache.

        Args:
            key: Clé de cache

        Returns:
            Valeur ou None si expirée/absente
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Vérifier expiration
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = None):
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de cache
            value: Valeur à stocker
            ttl: TTL en secondes (utilise default_ttl si non spécifié)
        """
        ttl = ttl if ttl is not None else self.default_ttl

        with self._lock:
            # Vérifier la taille max
            if len(self._cache) >= self.max_size:
                self._cleanup_expired()

                # Si toujours trop grand, supprimer les plus vieilles entrées
                if len(self._cache) >= self.max_size:
                    oldest_keys = sorted(
                        self._cache.keys(),
                        key=lambda k: self._cache[k].expires_at
                    )[:len(self._cache) // 4]  # Supprimer 25%
                    for k in oldest_keys:
                        del self._cache[k]

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl
            )

    def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache.

        Returns:
            True si supprimé, False si non trouvé
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """Vide tout le cache"""
        with self._lock:
            self._cache.clear()

    def invalidate_pattern(self, pattern: str):
        """
        Invalide toutes les clés qui commencent par le pattern.

        Args:
            pattern: Préfixe des clés à invalider
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]

    def _cleanup_expired(self):
        """Supprime les entrées expirées (appelé avec le lock)"""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
        for key in expired_keys:
            del self._cache[key]

    def get_stats(self) -> Dict:
        """Retourne les statistiques du cache"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "default_ttl": self.default_ttl
            }


# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCE GLOBALE
# ═══════════════════════════════════════════════════════════════════════════════

# Cache pour les statistiques (TTL court)
_stats_cache = TTLCache(default_ttl=30, max_size=100)

# Cache pour les données de référence (TTL moyen)
_data_cache = TTLCache(default_ttl=120, max_size=500)


def get_stats_cache() -> TTLCache:
    """Cache pour les statistiques (TTL 30s)"""
    return _stats_cache


def get_data_cache() -> TTLCache:
    """Cache pour les données de référence (TTL 120s)"""
    return _data_cache


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCORATEUR DE CACHE
# ═══════════════════════════════════════════════════════════════════════════════

def cached(
    cache: TTLCache = None,
    ttl: int = None,
    key_prefix: str = "",
    key_builder: Callable = None
):
    """
    Décorateur pour mettre en cache le résultat d'une fonction.

    Args:
        cache: Instance de cache à utiliser (défaut: stats_cache)
        ttl: TTL personnalisé
        key_prefix: Préfixe pour la clé de cache
        key_builder: Fonction pour construire la clé (args, kwargs) -> str

    Usage:
        @cached(ttl=60, key_prefix="stats_")
        def get_expensive_stats(param1, param2):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Utiliser le cache par défaut si non spécifié
            _cache = cache or _stats_cache

            # Construire la clé
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Clé par défaut basée sur le nom de la fonction et les arguments
                args_str = "_".join(str(a) for a in args[1:])  # Skip self/db
                kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}{func.__name__}_{args_str}_{kwargs_str}"

            # Vérifier le cache
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Calculer et mettre en cache
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl)

            return result

        # Ajouter une méthode pour invalider le cache de cette fonction
        wrapper.invalidate = lambda: _stats_cache.invalidate_pattern(
            f"{key_prefix}{func.__name__}_"
        )

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER POUR INVALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def invalidate_stats_cache():
    """Invalide tout le cache de statistiques"""
    _stats_cache.clear()


def invalidate_data_cache():
    """Invalide tout le cache de données"""
    _data_cache.clear()


def invalidate_all_caches():
    """Invalide tous les caches"""
    _stats_cache.clear()
    _data_cache.clear()


def get_all_cache_stats() -> Dict:
    """Retourne les statistiques de tous les caches"""
    return {
        "stats_cache": _stats_cache.get_stats(),
        "data_cache": _data_cache.get_stats()
    }
