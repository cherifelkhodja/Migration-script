"""
StreamlitTenantContext - Adapter Streamlit pour le TenantContext.

Responsabilite unique:
----------------------
Lire les informations utilisateur depuis st.session_state
et les exposer via l'interface TenantContext.

Usage:
------
    from src.infrastructure.adapters import StreamlitTenantContext

    ctx = StreamlitTenantContext()
    if ctx.should_filter:
        query = query.filter(Model.owner_id == ctx.user_uuid)
"""

from typing import Optional
from uuid import UUID

import streamlit as st

from src.domain.value_objects.user_id import UserId, SYSTEM_USER
from src.domain.ports.tenant_context import TenantContext


class StreamlitTenantContext(TenantContext):
    """
    Adapter TenantContext pour Streamlit.

    Lit le user depuis st.session_state["user"].
    Retourne SYSTEM_USER si pas d'utilisateur connecte.

    Attributes:
        current_user_id: UserId de l'utilisateur.
        is_admin: True si role admin.
        should_filter: True si filtrage necessaire.
    """

    @property
    def current_user_id(self) -> UserId:
        """
        Retourne le UserId courant.

        Returns:
            UserId ou SYSTEM_USER si non connecte.
        """
        user = self._get_user()
        if user and user.get("id"):
            return UserId.from_string(user["id"])
        return SYSTEM_USER

    @property
    def is_admin(self) -> bool:
        """
        True si l'utilisateur est admin.

        Les admins voient toutes les donnees.
        """
        user = self._get_user()
        return user is not None and user.get("is_admin", False)

    @property
    def should_filter(self) -> bool:
        """
        True si les requetes doivent etre filtrees.

        Les admins ne sont pas filtres.
        """
        return not self.is_admin

    @property
    def user_uuid(self) -> Optional[UUID]:
        """
        UUID brut pour les requetes SQLAlchemy.

        Returns:
            UUID ou None si SYSTEM_USER.
        """
        user_id = self.current_user_id
        if user_id.is_system:
            return None
        return user_id.value

    def _get_user(self) -> Optional[dict]:
        """Recupere le user depuis session_state."""
        return st.session_state.get("user")
