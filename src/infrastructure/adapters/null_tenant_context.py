"""
NullTenantContext - Contexte tenant sans restriction.

Responsabilite unique:
----------------------
Fournir un contexte tenant pour les environnements
sans authentification (tests, CLI, scripts).

Usage:
------
    ctx = NullTenantContext()
    # Toutes les donnees sont accessibles (is_admin=True)
"""

from src.domain.value_objects.user_id import UserId, SYSTEM_USER
from src.domain.ports.tenant_context import TenantContext


class NullTenantContext(TenantContext):
    """
    Contexte tenant sans restriction.

    Retourne SYSTEM_USER et is_admin=True.
    Utilise pour les tests et scripts.
    """

    @property
    def current_user_id(self) -> UserId:
        """Retourne SYSTEM_USER."""
        return SYSTEM_USER

    @property
    def is_admin(self) -> bool:
        """Retourne True (pas de restriction)."""
        return True

    @property
    def should_filter(self) -> bool:
        """Retourne False (pas de filtrage)."""
        return False
