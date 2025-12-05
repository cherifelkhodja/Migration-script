"""
Module HTTP Client avec résilience intégrée.
- Connection pooling via requests.Session
- Exponential backoff pour les retries
- Circuit breaker pour éviter les appels inutiles
"""
import time
import random
import requests
from typing import Optional, Dict, Any, Callable
from threading import Lock
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps

from app.config import (
    USER_AGENTS, TIMEOUT_WEB, SCRAPER_API_KEY, SCRAPER_API_URL
)


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CircuitState:
    """État d'un circuit breaker"""
    failures: int = 0
    last_failure: Optional[datetime] = None
    state: str = "closed"  # closed, open, half-open
    success_count: int = 0


class CircuitBreaker:
    """
    Pattern Circuit Breaker pour protéger contre les services défaillants.

    États:
    - CLOSED: Fonctionnement normal, les requêtes passent
    - OPEN: Service en échec, les requêtes sont bloquées
    - HALF-OPEN: Test de récupération, quelques requêtes passent
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_requests: int = 3
    ):
        """
        Args:
            failure_threshold: Nombre d'échecs avant ouverture du circuit
            recovery_timeout: Secondes avant de tenter une récupération
            half_open_requests: Requêtes réussies nécessaires pour fermer le circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self._circuits: Dict[str, CircuitState] = {}
        self._lock = Lock()

    def _get_circuit(self, name: str) -> CircuitState:
        """Récupère ou crée un circuit pour un service"""
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitState()
            return self._circuits[name]

    def is_allowed(self, name: str) -> bool:
        """Vérifie si une requête est autorisée pour ce service"""
        circuit = self._get_circuit(name)

        with self._lock:
            if circuit.state == "closed":
                return True

            if circuit.state == "open":
                # Vérifier si le timeout de récupération est passé
                if circuit.last_failure and \
                   datetime.utcnow() - circuit.last_failure > timedelta(seconds=self.recovery_timeout):
                    circuit.state = "half-open"
                    circuit.success_count = 0
                    return True
                return False

            # half-open: autoriser quelques requêtes de test
            return True

    def record_success(self, name: str):
        """Enregistre un succès pour ce service"""
        circuit = self._get_circuit(name)

        with self._lock:
            if circuit.state == "half-open":
                circuit.success_count += 1
                if circuit.success_count >= self.half_open_requests:
                    circuit.state = "closed"
                    circuit.failures = 0
            elif circuit.state == "closed":
                circuit.failures = 0  # Reset des échecs après succès

    def record_failure(self, name: str):
        """Enregistre un échec pour ce service"""
        circuit = self._get_circuit(name)

        with self._lock:
            circuit.failures += 1
            circuit.last_failure = datetime.utcnow()

            if circuit.state == "half-open":
                # Retour en état ouvert
                circuit.state = "open"
            elif circuit.failures >= self.failure_threshold:
                circuit.state = "open"

    def get_status(self) -> Dict[str, Dict]:
        """Retourne le statut de tous les circuits"""
        with self._lock:
            return {
                name: {
                    "state": c.state,
                    "failures": c.failures,
                    "last_failure": c.last_failure.isoformat() if c.last_failure else None
                }
                for name, c in self._circuits.items()
            }

    def reset(self, name: str = None):
        """Réinitialise un circuit ou tous les circuits"""
        with self._lock:
            if name:
                if name in self._circuits:
                    self._circuits[name] = CircuitState()
            else:
                self._circuits.clear()


# Instance globale du circuit breaker
_circuit_breaker = CircuitBreaker()


def get_circuit_breaker() -> CircuitBreaker:
    """Retourne l'instance globale du circuit breaker"""
    return _circuit_breaker


# ═══════════════════════════════════════════════════════════════════════════════
# EXPONENTIAL BACKOFF
# ═══════════════════════════════════════════════════════════════════════════════

def exponential_backoff(
    max_retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (requests.RequestException,),
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)
):
    """
    Décorateur pour retry avec exponential backoff.

    Args:
        max_retries: Nombre maximum de tentatives
        base_delay: Délai initial en secondes
        max_delay: Délai maximum en secondes
        exponential_base: Base de l'exponentielle (2 = doubler à chaque retry)
        jitter: Ajouter un délai aléatoire pour éviter les thundering herds
        retryable_exceptions: Exceptions qui déclenchent un retry
        retryable_status_codes: Codes HTTP qui déclenchent un retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Vérifier le code de statut si c'est une Response
                    if isinstance(result, requests.Response):
                        if result.status_code in retryable_status_codes:
                            if attempt < max_retries:
                                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                                if jitter:
                                    delay *= (0.5 + random.random())
                                time.sleep(delay)
                                continue

                    return result

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        if jitter:
                            delay *= (0.5 + random.random())
                        time.sleep(delay)
                    else:
                        raise

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 4,
    base_delay: float = 1.0,
    **kwargs
) -> Any:
    """
    Fonction utilitaire pour appeler une fonction avec retry.

    Usage:
        result = retry_with_backoff(my_function, arg1, arg2, max_retries=3)
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except (requests.RequestException, ConnectionError, TimeoutError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), 30.0)
                delay *= (0.5 + random.random())  # Jitter
                time.sleep(delay)
            else:
                raise

    if last_exception:
        raise last_exception


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP SESSION POOL
# ═══════════════════════════════════════════════════════════════════════════════

class ResilientHTTPClient:
    """
    Client HTTP résilient avec:
    - Connection pooling via requests.Session
    - Rotation des User-Agents
    - Circuit breaker intégré
    - Retry avec exponential backoff
    """

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._session_lock = Lock()
        self._circuit_breaker = get_circuit_breaker()
        self._request_count = 0

    @property
    def session(self) -> requests.Session:
        """Retourne la session HTTP avec lazy initialization"""
        if self._session is None:
            with self._session_lock:
                if self._session is None:
                    self._session = requests.Session()
                    # Configurer le pool de connexions
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=10,    # Nombre de pools
                        pool_maxsize=20,        # Connexions par pool
                        max_retries=0           # On gère les retries nous-mêmes
                    )
                    self._session.mount('http://', adapter)
                    self._session.mount('https://', adapter)
        return self._session

    def _get_headers(self, extra_headers: Dict = None) -> Dict:
        """Génère les headers avec User-Agent rotatif"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _get_circuit_name(self, url: str) -> str:
        """Extrait le nom du circuit depuis l'URL (basé sur le domaine)"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    def get(
        self,
        url: str,
        timeout: int = None,
        headers: Dict = None,
        use_circuit_breaker: bool = True,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Effectue une requête GET résiliente.

        Args:
            url: URL à appeler
            timeout: Timeout en secondes
            headers: Headers additionnels
            use_circuit_breaker: Utiliser le circuit breaker
            max_retries: Nombre de retries avec backoff
            **kwargs: Arguments additionnels pour requests

        Returns:
            Response ou None si circuit ouvert
        """
        circuit_name = self._get_circuit_name(url)

        # Vérifier le circuit breaker
        if use_circuit_breaker and not self._circuit_breaker.is_allowed(circuit_name):
            return None

        timeout = timeout or TIMEOUT_WEB
        final_headers = self._get_headers(headers)

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    headers=final_headers,
                    timeout=timeout,
                    **kwargs
                )

                self._request_count += 1

                # Succès
                if response.status_code < 400:
                    if use_circuit_breaker:
                        self._circuit_breaker.record_success(circuit_name)
                    return response

                # Erreur retryable
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries:
                        delay = min(1.0 * (2 ** attempt), 30.0)
                        delay *= (0.5 + random.random())
                        time.sleep(delay)
                        continue

                # Erreur non retryable mais pas un échec du circuit
                if response.status_code < 500:
                    return response

                # Erreur serveur
                if use_circuit_breaker:
                    self._circuit_breaker.record_failure(circuit_name)
                return response

            except requests.RequestException as e:
                last_exception = e

                if attempt < max_retries:
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    delay *= (0.5 + random.random())
                    time.sleep(delay)
                else:
                    if use_circuit_breaker:
                        self._circuit_breaker.record_failure(circuit_name)
                    raise

        if last_exception:
            raise last_exception

    def get_with_scraper_api(
        self,
        url: str,
        timeout: int = None,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Effectue une requête via ScraperAPI (si configuré) avec fallback direct.

        Args:
            url: URL cible à scraper
            timeout: Timeout en secondes
            max_retries: Nombre de retries

        Returns:
            Response ou None
        """
        if SCRAPER_API_KEY:
            # Utiliser ScraperAPI
            from urllib.parse import urlencode
            params = {
                "api_key": SCRAPER_API_KEY,
                "url": url,
                "render": "false",
            }
            proxy_url = f"{SCRAPER_API_URL}?{urlencode(params)}"

            try:
                return self.get(
                    proxy_url,
                    timeout=timeout or 30,
                    max_retries=max_retries,
                    use_circuit_breaker=True,
                    **kwargs
                )
            except requests.RequestException:
                # Fallback en requête directe
                pass

        # Requête directe
        return self.get(
            url,
            timeout=timeout,
            max_retries=max_retries,
            use_circuit_breaker=True,
            **kwargs
        )

    def get_stats(self) -> Dict:
        """Retourne les statistiques du client"""
        return {
            "total_requests": self._request_count,
            "circuit_breaker_status": self._circuit_breaker.get_status()
        }

    def close(self):
        """Ferme la session HTTP"""
        if self._session:
            self._session.close()
            self._session = None


# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCE GLOBALE
# ═══════════════════════════════════════════════════════════════════════════════

_http_client: Optional[ResilientHTTPClient] = None
_client_lock = Lock()


def get_http_client() -> ResilientHTTPClient:
    """Retourne l'instance globale du client HTTP résilient"""
    global _http_client
    if _http_client is None:
        with _client_lock:
            if _http_client is None:
                _http_client = ResilientHTTPClient()
    return _http_client


def close_http_client():
    """Ferme le client HTTP global"""
    global _http_client
    if _http_client:
        _http_client.close()
        _http_client = None
