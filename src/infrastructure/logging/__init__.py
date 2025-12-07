"""
Logging Infrastructure - Logging structure avec structlog.

Responsabilite:
---------------
Fournir un logging JSON structure pour production.

Usage:
------
    from src.infrastructure.logging import get_logger

    logger = get_logger(__name__)
    logger.info("user_logged_in", user_id="123", ip="1.2.3.4")
"""

from src.infrastructure.logging.config import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
