"""
Ports du domaine (Hexagonal Architecture).

Les Ports sont des interfaces qui definissent les contrats
entre le domaine et le monde exterieur.

Ports disponibles:
------------------
- TenantContext: Gestion du contexte multi-tenant
- TenantAwareMixin: Mixin pour les entites tenant-aware

Pattern:
--------
Les Ports sont des abstractions (Protocol/ABC) implementees
par des Adapters dans la couche Infrastructure.

Example:
    # Port (domain)
    class TenantContext(Protocol):
        @property
        def current_user_id(self) -> UserId: ...

    # Adapter (infrastructure)
    class StreamlitTenantContext(TenantContext):
        @property
        def current_user_id(self) -> UserId:
            return UserId.from_any(st.session_state.get("user", {}).get("id"))
"""

from src.domain.ports.tenant_context import TenantContext, TenantAwareMixin

__all__ = [
    "TenantContext",
    "TenantAwareMixin",
]
