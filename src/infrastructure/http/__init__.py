"""
Module HTTP Client resilient.

Fournit un client HTTP avec:
- Connection pooling
- Circuit breaker
- Exponential backoff
"""

from src.infrastructure.http.resilient_client import (
    CircuitBreaker,
    CircuitState,
    ResilientHTTPClient,
    exponential_backoff,
    retry_with_backoff,
    get_circuit_breaker,
    get_http_client,
    close_http_client,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "ResilientHTTPClient",
    "exponential_backoff",
    "retry_with_backoff",
    "get_circuit_breaker",
    "get_http_client",
    "close_http_client",
]
