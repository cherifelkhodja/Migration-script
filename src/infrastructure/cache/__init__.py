"""
Module de cache en memoire avec TTL.

Fournit un cache leger pour les donnees frequemment accedees
avec support du Time-To-Live (TTL).
"""

from src.infrastructure.cache.ttl_cache import (
    TTLCache,
    CacheEntry,
    cached,
    get_stats_cache,
    get_data_cache,
    invalidate_stats_cache,
    invalidate_data_cache,
    invalidate_all_caches,
    get_all_cache_stats,
)

__all__ = [
    "TTLCache",
    "CacheEntry",
    "cached",
    "get_stats_cache",
    "get_data_cache",
    "invalidate_stats_cache",
    "invalidate_data_cache",
    "invalidate_all_caches",
    "get_all_cache_stats",
]
