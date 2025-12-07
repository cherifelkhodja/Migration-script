"""
Logging Config - Configuration structlog.

Responsabilite unique:
----------------------
Configurer structlog pour JSON logging en production.

Modes:
------
- Development: Pretty print, couleurs
- Production: JSON, timestamp ISO

Usage:
------
    from src.infrastructure.logging import configure_logging, get_logger

    configure_logging(json_logs=True)
    logger = get_logger("myapp")
    logger.info("started", version="1.0")
"""

import logging
import sys
from typing import Optional

import structlog


def configure_logging(
    json_logs: bool = False,
    log_level: str = "INFO",
) -> None:
    """
    Configure le logging global.

    Args:
        json_logs: True pour JSON (production), False pour pretty.
        log_level: Niveau minimum (DEBUG, INFO, WARNING, ERROR).
    """
    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        # Production: JSON
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty print
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Retourne un logger structure.

    Args:
        name: Nom du logger (module name).

    Returns:
        Logger structlog.

    Example:
        logger = get_logger(__name__)
        logger.info("event", key="value")
    """
    return structlog.get_logger(name)


class RequestLogger:
    """
    Middleware de logging pour FastAPI.

    Log chaque requete avec duration, status, etc.
    """

    def __init__(self, logger: Optional[structlog.stdlib.BoundLogger] = None):
        """
        Initialise le middleware.

        Args:
            logger: Logger a utiliser (defaut: cree un nouveau).
        """
        self._logger = logger or get_logger("api.requests")

    async def __call__(self, request, call_next):
        """Log la requete et la reponse."""
        import time

        start_time = time.perf_counter()

        # Bind request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request.headers.get("x-request-id", "-"),
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise
