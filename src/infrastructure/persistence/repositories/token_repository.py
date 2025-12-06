"""
Repository pour les tokens Meta API.
"""
import time
from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy import func, desc

from src.infrastructure.persistence.models import MetaToken, TokenUsageLog


def add_meta_token(db, token: str, name: str = None, proxy_url: str = None) -> int:
    """Ajoute un nouveau token Meta API."""
    with db.get_session() as session:
        existing = session.query(MetaToken).filter(MetaToken.token == token).first()
        if existing:
            return existing.id

        if not name:
            count = session.query(MetaToken).count()
            name = f"Token #{count + 1}"

        meta_token = MetaToken(
            token=token,
            name=name,
            proxy_url=proxy_url,
            is_active=True
        )
        session.add(meta_token)
        session.flush()
        return meta_token.id


def get_all_meta_tokens(db, active_only: bool = False) -> List[Dict]:
    """Recupere tous les tokens Meta API."""
    with db.get_session() as session:
        query = session.query(MetaToken).order_by(MetaToken.id)

        if active_only:
            query = query.filter(MetaToken.is_active == True)

        tokens = query.all()
        now = datetime.utcnow()

        return [{
            "id": t.id,
            "name": t.name,
            "token_masked": f"{t.token[:8]}...{t.token[-4:]}" if len(t.token) > 12 else "***",
            "token": t.token,
            "proxy_url": t.proxy_url,
            "is_active": t.is_active,
            "total_calls": t.total_calls or 0,
            "total_errors": t.total_errors or 0,
            "rate_limit_hits": t.rate_limit_hits or 0,
            "last_used_at": t.last_used_at,
            "last_error_at": t.last_error_at,
            "last_error_message": t.last_error_message,
            "rate_limited_until": t.rate_limited_until,
            "is_rate_limited": t.rate_limited_until and t.rate_limited_until > now,
            "created_at": t.created_at
        } for t in tokens]


def get_active_meta_tokens(db) -> List[str]:
    """Recupere uniquement les tokens actifs (pour le TokenRotator)."""
    with db.get_session() as session:
        now = datetime.utcnow()
        tokens = session.query(MetaToken).filter(
            MetaToken.is_active == True
        ).order_by(MetaToken.id).all()

        return [t.token for t in tokens
                if not t.rate_limited_until or t.rate_limited_until <= now]


def get_active_meta_tokens_with_proxies(db) -> List[Dict]:
    """Recupere les tokens actifs avec leurs proxies associes."""
    with db.get_session() as session:
        now = datetime.utcnow()
        tokens = session.query(MetaToken).filter(
            MetaToken.is_active == True
        ).order_by(MetaToken.id).all()

        result = []
        for t in tokens:
            if not t.rate_limited_until or t.rate_limited_until <= now:
                result.append({
                    "id": t.id,
                    "token": t.token,
                    "proxy": t.proxy_url,
                    "name": t.name or f"Token #{t.id}"
                })
        return result


def update_meta_token(
    db,
    token_id: int,
    name: str = None,
    is_active: bool = None,
    proxy_url: str = None,
    token_value: str = None
) -> bool:
    """Met a jour un token."""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False

        if name is not None:
            token.name = name
        if is_active is not None:
            token.is_active = is_active
        if proxy_url is not None:
            token.proxy_url = proxy_url if proxy_url.strip() else None
        if token_value is not None and token_value.strip():
            token.token = token_value.strip()

        return True


def delete_meta_token(db, token_id: int) -> bool:
    """Supprime un token."""
    with db.get_session() as session:
        deleted = session.query(MetaToken).filter(MetaToken.id == token_id).delete()
        return deleted > 0


def record_token_usage(
    db,
    token: str,
    success: bool = True,
    error_message: str = None,
    is_rate_limit: bool = False,
    rate_limit_seconds: int = 60
):
    """Enregistre une utilisation de token."""
    with db.get_session() as session:
        meta_token = session.query(MetaToken).filter(MetaToken.token == token).first()
        if not meta_token:
            return

        meta_token.total_calls = (meta_token.total_calls or 0) + 1
        meta_token.last_used_at = datetime.utcnow()

        if not success:
            meta_token.total_errors = (meta_token.total_errors or 0) + 1
            meta_token.last_error_at = datetime.utcnow()
            meta_token.last_error_message = error_message[:500] if error_message else None

            if is_rate_limit:
                meta_token.rate_limit_hits = (meta_token.rate_limit_hits or 0) + 1
                meta_token.rate_limited_until = datetime.utcnow() + timedelta(seconds=rate_limit_seconds)


def clear_rate_limit(db, token_id: int) -> bool:
    """Efface le rate limit d'un token."""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False
        token.rate_limited_until = None
        return True


def reset_token_stats(db, token_id: int) -> bool:
    """Reinitialise les statistiques d'un token."""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False

        token.total_calls = 0
        token.total_errors = 0
        token.rate_limit_hits = 0
        token.last_used_at = None
        token.last_error_at = None
        token.last_error_message = None
        token.rate_limited_until = None
        return True


# ============================================================================
# LOGS DETAILLES DES TOKENS
# ============================================================================

def log_token_usage(
    db,
    token_id: int,
    token_name: str,
    action_type: str,
    keyword: str = None,
    countries: str = None,
    page_id: str = None,
    success: bool = True,
    ads_count: int = 0,
    error_message: str = None,
    response_time_ms: int = None
) -> int:
    """Enregistre une utilisation de token dans les logs."""
    with db.get_session() as session:
        log_entry = TokenUsageLog(
            token_id=token_id,
            token_name=token_name,
            action_type=action_type,
            keyword=keyword[:255] if keyword else None,
            countries=countries[:100] if countries else None,
            page_id=page_id,
            success=success,
            ads_count=ads_count,
            error_message=error_message,
            response_time_ms=response_time_ms
        )
        session.add(log_entry)
        session.flush()
        return log_entry.id


def get_token_usage_logs(
    db,
    token_id: int = None,
    days: int = 7,
    limit: int = 100,
    action_type: str = None
) -> List[Dict]:
    """Recupere les logs d'utilisation des tokens."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(TokenUsageLog).filter(
            TokenUsageLog.created_at >= cutoff
        )

        if token_id:
            query = query.filter(TokenUsageLog.token_id == token_id)

        if action_type:
            query = query.filter(TokenUsageLog.action_type == action_type)

        logs = query.order_by(desc(TokenUsageLog.created_at)).limit(limit).all()

        return [
            {
                "id": log.id,
                "token_id": log.token_id,
                "token_name": log.token_name,
                "action_type": log.action_type,
                "keyword": log.keyword,
                "countries": log.countries,
                "page_id": log.page_id,
                "success": log.success,
                "ads_count": log.ads_count,
                "error_message": log.error_message,
                "response_time_ms": log.response_time_ms,
                "created_at": log.created_at
            }
            for log in logs
        ]


def get_token_stats_detailed(db, token_id: int, days: int = 30) -> Dict:
    """Recupere les statistiques detaillees d'un token."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        total_calls = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        successful = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff,
            TokenUsageLog.success == True
        ).scalar() or 0

        total_ads = session.query(func.sum(TokenUsageLog.ads_count)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        avg_response = session.query(func.avg(TokenUsageLog.response_time_ms)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff,
            TokenUsageLog.response_time_ms != None
        ).scalar() or 0

        by_action = session.query(
            TokenUsageLog.action_type,
            func.count(TokenUsageLog.id),
            func.sum(TokenUsageLog.ads_count)
        ).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).group_by(TokenUsageLog.action_type).all()

        recent_keywords = session.query(
            TokenUsageLog.keyword,
            TokenUsageLog.created_at,
            TokenUsageLog.ads_count,
            TokenUsageLog.success
        ).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.keyword != None,
            TokenUsageLog.created_at >= cutoff
        ).order_by(TokenUsageLog.created_at.desc()).limit(20).all()

        rate_limits = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.action_type == "rate_limit",
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        return {
            "total_calls": total_calls,
            "successful": successful,
            "failed": total_calls - successful,
            "success_rate": (successful / total_calls * 100) if total_calls > 0 else 0,
            "total_ads_found": total_ads,
            "avg_response_ms": round(avg_response, 0),
            "rate_limits": rate_limits,
            "by_action": [
                {"action": a[0], "count": a[1], "ads": a[2] or 0}
                for a in by_action
            ],
            "recent_keywords": [
                {
                    "keyword": k[0],
                    "date": k[1],
                    "ads": k[2],
                    "success": k[3]
                }
                for k in recent_keywords
            ]
        }


def verify_meta_token(db, token_id: int) -> Dict:
    """Verifie si un token Meta est toujours valide en faisant un appel test."""
    import requests

    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return {"valid": False, "error": "Token non trouve"}

        token_value = token.token
        token_name = token.name
        proxy_url = token.proxy_url

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    test_url = "https://graph.facebook.com/v21.0/ads_archive"
    params = {
        "access_token": token_value,
        "search_terms": "test",
        "ad_reached_countries": '["FR"]',
        "ad_active_status": "ACTIVE",
        "limit": 1,
        "fields": "id"
    }

    start_time = time.time()
    result = {
        "valid": False,
        "token_id": token_id,
        "token_name": token_name,
        "response_time_ms": 0,
        "error": None
    }

    try:
        response = requests.get(
            test_url,
            params=params,
            proxies=proxies,
            timeout=30,
            verify=False
        )
        response_time = int((time.time() - start_time) * 1000)
        result["response_time_ms"] = response_time

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                result["valid"] = True
                result["message"] = "Token valide et fonctionnel"
                log_token_usage(
                    db, token_id, token_name, "verification",
                    success=True, response_time_ms=response_time
                )
            else:
                result["error"] = data.get("error", {}).get("message", "Reponse invalide")
                log_token_usage(
                    db, token_id, token_name, "verification",
                    success=False, error_message=result["error"], response_time_ms=response_time
                )
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
            result["error"] = error_msg

            if "OAuth" in error_msg or "token" in error_msg.lower():
                result["error_type"] = "token_expired"
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                result["error_type"] = "rate_limited"
            else:
                result["error_type"] = "unknown"

            log_token_usage(
                db, token_id, token_name, "verification",
                success=False, error_message=error_msg, response_time_ms=response_time
            )

    except requests.exceptions.Timeout:
        result["error"] = "Timeout - pas de reponse"
        result["error_type"] = "timeout"
    except requests.exceptions.ProxyError:
        result["error"] = "Erreur proxy - verifiez la configuration"
        result["error_type"] = "proxy_error"
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = "exception"

    return result


def verify_all_tokens(db) -> List[Dict]:
    """Verifie tous les tokens actifs."""
    tokens = get_all_meta_tokens(db, active_only=True)
    results = []
    for token in tokens:
        result = verify_meta_token(db, token["id"])
        results.append(result)
    return results
