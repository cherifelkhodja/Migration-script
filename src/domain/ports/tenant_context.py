"""
Port TenantContext - Interface pour le contexte multi-tenant.

Responsabilite unique:
----------------------
Definir le contrat pour obtenir l'utilisateur courant.
Implementee par StreamlitTenantContext.

Architecture Hexagonale:
------------------------
    [Domain]                    [Infrastructure]
    TenantContext  <------>  StreamlitTenantContext
    (Port)                      (Adapter)
"""

from typing import Protocol, runtime_checkable

from src.domain.value_objects.user_id import UserId


@runtime_checkable
class TenantContext(Protocol):
    """
    Interface pour le contexte multi-tenant.

    Contrat que doivent implementer les adapters.

    Properties:
        current_user_id: UserId de l'utilisateur.
        is_admin: True si admin.
        should_filter: True si filtrage necessaire.
    """

    @property
    def current_user_id(self) -> UserId:
        """UserId de l'utilisateur courant."""
        ...

    @property
    def is_admin(self) -> bool:
        """True si administrateur."""
        ...

    @property
    def should_filter(self) -> bool:
        """True si les requetes doivent etre filtrees."""
        return not self.is_admin
