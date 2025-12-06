"""
Repository pour le cache API.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func

from src.infrastructure.persistence.models import APICache


def generate_cache_key(cache_type: str, **params) -> str:
    """
    Genere une cle de cache unique basee sur les parametres.

    Args:
        cache_type: Type de cache (search_ads, page_info, etc.)
        **params: Parametres de la requete

    Returns:
        Cle de cache unique
    """
    sorted_params = sorted(params.items())
    param_str = json.dumps(sorted_params, sort_keys=True)
    hash_str = hashlib.md5(param_str.encode()).hexdigest()[:16]
    return f"{cache_type}:{hash_str}"


def get_cached_response(db, cache_key: str) -> Optional[Dict]:
    """
    Recupere une reponse du cache si elle existe et n'est pas expiree.

    Args:
        db: DatabaseManager
        cache_key: Cle de cache

    Returns:
        Donnees cachees ou None si cache miss
    """
    with db.get_session() as session:
        cache_entry = session.query(APICache).filter(
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.utcnow()
        ).first()

        if cache_entry:
            cache_entry.hit_count = (cache_entry.hit_count or 0) + 1
            session.commit()
            try:
                return json.loads(cache_entry.response_data)
            except Exception:
                return None

    return None


def set_cached_response(
    db,
    cache_key: str,
    cache_type: str,
    response_data: Dict,
    ttl_hours: int = 6
) -> bool:
    """
    Stocke une reponse dans le cache.

    Args:
        db: DatabaseManager
        cache_key: Cle de cache
        cache_type: Type de cache
        response_data: Donnees a cacher
        ttl_hours: Duree de vie en heures (defaut: 6h)

    Returns:
        True si succes
    """
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    with db.get_session() as session:
        existing = session.query(APICache).filter(
            APICache.cache_key == cache_key
        ).first()

        if existing:
            existing.response_data = json.dumps(response_data)
            existing.expires_at = expires_at
            existing.created_at = datetime.utcnow()
        else:
            cache_entry = APICache(
                cache_key=cache_key,
                cache_type=cache_type,
                response_data=json.dumps(response_data),
                expires_at=expires_at
            )
            session.add(cache_entry)

        session.commit()

    return True


def get_cache_stats(db) -> Dict:
    """Recupere les statistiques du cache."""
    with db.get_session() as session:
        total_entries = session.query(func.count(APICache.id)).scalar() or 0

        valid_entries = session.query(func.count(APICache.id)).filter(
            APICache.expires_at > datetime.utcnow()
        ).scalar() or 0

        expired_entries = total_entries - valid_entries

        total_hits = session.query(func.sum(APICache.hit_count)).scalar() or 0

        by_type = session.query(
            APICache.cache_type,
            func.count(APICache.id),
            func.sum(APICache.hit_count)
        ).group_by(APICache.cache_type).all()

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "total_hits": total_hits,
            "by_type": [
                {"type": t[0], "count": t[1], "hits": t[2] or 0}
                for t in by_type
            ]
        }


def clear_expired_cache(db) -> int:
    """Supprime les entrees de cache expirees."""
    with db.get_session() as session:
        deleted = session.query(APICache).filter(
            APICache.expires_at < datetime.utcnow()
        ).delete()
        session.commit()
    return deleted


def clear_all_cache(db) -> int:
    """Supprime tout le cache."""
    with db.get_session() as session:
        deleted = session.query(APICache).delete()
        session.commit()
    return deleted
