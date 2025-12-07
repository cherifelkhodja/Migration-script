"""
TenantFilter - Filtrage SQLAlchemy pour le multi-tenancy.

Responsabilite unique:
----------------------
Appliquer le filtrage owner_id sur les requetes SQLAlchemy.

Usage:
------
    from src.infrastructure.tenant_filter import TenantFilter
    from src.infrastructure.adapters import StreamlitTenantContext

    ctx = StreamlitTenantContext()
    query = session.query(Collection)
    query = TenantFilter.apply(query, Collection, ctx)

Regles de filtrage:
-------------------
- Admins: Pas de filtre (voient tout)
- Autres: owner_id = user_id OR owner_id IS NULL
- NULL = donnees publiques/systeme
"""

from sqlalchemy import or_

from src.domain.ports.tenant_context import TenantContext


class TenantFilter:
    """
    Filtre SQLAlchemy pour l'isolation multi-tenant.

    Methodes statiques pour filtrer les requetes
    selon le contexte utilisateur.
    """

    @staticmethod
    def apply(query, model_class, ctx: TenantContext):
        """
        Filtre une requete par owner_id.

        Inclut les donnees publiques (owner_id=NULL).

        Args:
            query: Requete SQLAlchemy.
            model_class: Classe du modele avec owner_id.
            ctx: Contexte tenant.

        Returns:
            Requete filtree.
        """
        # Admins voient tout
        if not ctx.should_filter:
            return query

        # Modele sans owner_id = pas de filtrage
        if not hasattr(model_class, 'owner_id'):
            return query

        # Filtre: mes donnees OU donnees publiques
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
        Filtre strict (sans donnees publiques).

        Args:
            query: Requete SQLAlchemy.
            model_class: Classe du modele.
            ctx: Contexte tenant.

        Returns:
            Requete avec seulement les donnees du user.
        """
        if not ctx.should_filter:
            return query

        if not hasattr(model_class, 'owner_id'):
            return query

        return query.filter(
            model_class.owner_id == ctx.current_user_id.value
        )

    @staticmethod
    def set_owner(instance, ctx: TenantContext) -> None:
        """
        Definit le owner_id sur une instance.

        Args:
            instance: Instance du modele.
            ctx: Contexte tenant.
        """
        if hasattr(instance, 'owner_id'):
            if not ctx.current_user_id.is_system:
                instance.owner_id = ctx.current_user_id.value
