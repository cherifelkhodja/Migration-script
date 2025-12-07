"""
TenantFilter - Filtrage des requetes SQLAlchemy par utilisateur.

Ce module fournit les outils pour filtrer automatiquement les requetes
selon l'utilisateur connecte (multi-tenancy).

Architecture:
-------------
    [Streamlit]                [Infrastructure]
    session_state  ---->  StreamlitTenantContext
                                    |
                                    v
                            TenantFilter.apply()
                                    |
                                    v
                            Query.filter(owner_id=...)

Usage:
------
    from src.infrastructure.tenant_filter import (
        StreamlitTenantContext,
        TenantFilter
    )

    # Dans un repository
    ctx = StreamlitTenantContext()
    query = session.query(Collection)
    query = TenantFilter.apply(query, Collection, ctx)
    # Retourne seulement les collections de l'utilisateur courant

Compatibilite:
--------------
Les enregistrements sans owner_id (NULL) sont consideres comme publics
et sont retournes pour tous les utilisateurs.
"""

from typing import TypeVar, Optional
from uuid import UUID

import streamlit as st

from src.domain.value_objects.user_id import UserId, SYSTEM_USER
from src.domain.ports.tenant_context import TenantContext, NullTenantContext


T = TypeVar('T')


class StreamlitTenantContext(TenantContext):
    """
    Adapter TenantContext pour Streamlit.

    Lit les informations utilisateur depuis st.session_state
    et fournit le contexte pour le filtrage multi-tenant.

    Usage:
        ctx = StreamlitTenantContext()
        if ctx.should_filter:
            query = query.filter(Model.owner_id == ctx.current_user_id.value)
    """

    @property
    def current_user_id(self) -> UserId:
        """
        Retourne le UserId de l'utilisateur connecte.

        Si pas d'utilisateur connecte, retourne SYSTEM_USER.
        """
        user = st.session_state.get("user")
        if user and user.get("id"):
            return UserId.from_string(user["id"])
        return SYSTEM_USER

    @property
    def is_admin(self) -> bool:
        """True si l'utilisateur est administrateur."""
        user = st.session_state.get("user")
        return user is not None and user.get("is_admin", False)

    @property
    def should_filter(self) -> bool:
        """True si les requetes doivent etre filtrees."""
        return not self.is_admin

    @property
    def current_user_uuid(self) -> Optional[UUID]:
        """
        Retourne le UUID brut pour les requetes SQLAlchemy.

        Retourne None pour SYSTEM_USER (pas de filtrage).
        """
        user_id = self.current_user_id
        if user_id.is_system:
            return None
        return user_id.value


class TenantFilter:
    """
    Filtre SQLAlchemy pour le multi-tenancy.

    Applique automatiquement le filtrage par owner_id
    sur les requetes SQLAlchemy.

    Example:
        query = session.query(Collection)
        query = TenantFilter.apply(query, Collection, ctx)
    """

    @staticmethod
    def apply(query, model_class, ctx: TenantContext):
        """
        Applique le filtre tenant a une requete.

        Args:
            query: Requete SQLAlchemy.
            model_class: Classe du modele (doit avoir owner_id).
            ctx: Contexte tenant.

        Returns:
            Requete filtree.

        Note:
            - Les admins voient tout (pas de filtre)
            - Les enregistrements avec owner_id=NULL sont publics
        """
        # Admins voient tout
        if not ctx.should_filter:
            return query

        # Verifier que le modele a owner_id
        if not hasattr(model_class, 'owner_id'):
            return query

        # Filtrer: owner_id = user OU owner_id IS NULL (public)
        from sqlalchemy import or_

        user_uuid = ctx.current_user_id.value
        return query.filter(
            or_(
                model_class.owner_id == user_uuid,
                model_class.owner_id.is_(None)
            )
        )

    @staticmethod
    def apply_strict(query, model_class, ctx: TenantContext):
        """
        Applique le filtre tenant strict (sans donnees publiques).

        Args:
            query: Requete SQLAlchemy.
            model_class: Classe du modele.
            ctx: Contexte tenant.

        Returns:
            Requete filtree (seulement les donnees de l'utilisateur).
        """
        if not ctx.should_filter:
            return query

        if not hasattr(model_class, 'owner_id'):
            return query

        user_uuid = ctx.current_user_id.value
        return query.filter(model_class.owner_id == user_uuid)

    @staticmethod
    def set_owner(model_instance, ctx: TenantContext) -> None:
        """
        Definit le owner_id sur une instance de modele.

        Args:
            model_instance: Instance du modele a modifier.
            ctx: Contexte tenant.
        """
        if hasattr(model_instance, 'owner_id'):
            if not ctx.current_user_id.is_system:
                model_instance.owner_id = ctx.current_user_id.value


def get_tenant_context() -> TenantContext:
    """
    Retourne le TenantContext courant.

    Factory qui retourne le contexte approprie selon l'environnement:
    - StreamlitTenantContext si Streamlit disponible
    - NullTenantContext sinon (tests, CLI)

    Returns:
        Instance TenantContext.
    """
    try:
        # Verifier si on est dans Streamlit
        if hasattr(st, 'session_state'):
            return StreamlitTenantContext()
    except Exception:
        pass

    return NullTenantContext()
