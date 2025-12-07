"""
Port TenantContext - Interface pour le multi-tenancy.

Ce port definit le contrat pour la gestion du contexte utilisateur
dans une architecture multi-tenant. Il permet:

1. D'obtenir l'utilisateur courant
2. De savoir si l'utilisateur est admin (voit tout)
3. De determiner si le filtrage est necessaire

Architecture:
-------------
    [Domain]                    [Infrastructure]
    TenantContext  <------>  StreamlitTenantContext
    (Port/Interface)            (Adapter)

Le TenantContext est injecte dans les repositories et use cases
pour filtrer les donnees selon l'utilisateur courant.

Usage:
------
    # Dans un repository
    class PageRepository:
        def __init__(self, tenant_ctx: TenantContext):
            self.tenant_ctx = tenant_ctx

        def find_all(self) -> List[Page]:
            query = session.query(PageModel)
            if self.tenant_ctx.should_filter:
                query = query.filter(
                    PageModel.owner_id == self.tenant_ctx.current_user_id.value
                )
            return query.all()

Mixin TenantAware:
------------------
Le TenantAwareMixin ajoute la notion de proprietaire (owner_id)
aux entites du domaine. Chaque entite tenant-aware peut verifier
si elle appartient a un utilisateur donne.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, Optional

from src.domain.value_objects.user_id import UserId, SYSTEM_USER


@runtime_checkable
class TenantContext(Protocol):
    """
    Interface pour le contexte multi-tenant.

    Definit le contrat que doivent implementer les adapters
    pour fournir les informations de tenant.

    Properties:
        current_user_id: UserId de l'utilisateur connecte.
        is_admin: True si l'utilisateur est administrateur.
        should_filter: True si les donnees doivent etre filtrees.
    """

    @property
    def current_user_id(self) -> UserId:
        """Retourne le UserId de l'utilisateur courant."""
        ...

    @property
    def is_admin(self) -> bool:
        """True si l'utilisateur est administrateur."""
        ...

    @property
    def should_filter(self) -> bool:
        """
        True si les requetes doivent etre filtrees par user_id.

        Les admins ne sont pas filtres (voient tout).
        """
        return not self.is_admin


class TenantAwareMixin:
    """
    Mixin pour les entites tenant-aware.

    Ajoute la notion de proprietaire (owner_id) aux entites
    et fournit des methodes de verification d'appartenance.

    Attributes:
        owner_id: UserId du proprietaire de l'entite.

    Example:
        @dataclass
        class Page(TenantAwareMixin):
            id: PageId
            name: str
            owner_id: UserId = SYSTEM_USER

        page = Page(id=..., name="Test", owner_id=user_id)
        if page.belongs_to(current_user_id):
            print("Page appartient a l'utilisateur")
    """

    owner_id: Optional[UserId] = None

    def belongs_to(self, user_id: UserId) -> bool:
        """
        Verifie si l'entite appartient a un utilisateur.

        Args:
            user_id: UserId a verifier.

        Returns:
            True si l'entite appartient a cet utilisateur.
        """
        if self.owner_id is None:
            return True  # Pas de owner = accessible a tous
        return self.owner_id == user_id

    @property
    def is_public(self) -> bool:
        """
        True si l'entite est publique (SYSTEM_USER ou None).

        Les entites publiques sont accessibles a tous les utilisateurs.
        """
        return self.owner_id is None or self.owner_id.is_system

    def can_access(self, tenant_ctx: TenantContext) -> bool:
        """
        Verifie si l'utilisateur courant peut acceder a l'entite.

        Args:
            tenant_ctx: Contexte tenant courant.

        Returns:
            True si l'acces est autorise.
        """
        # Admins voient tout
        if tenant_ctx.is_admin:
            return True

        # Entites publiques accessibles a tous
        if self.is_public:
            return True

        # Sinon, verifier l'appartenance
        return self.belongs_to(tenant_ctx.current_user_id)


class NullTenantContext:
    """
    Implementation nulle du TenantContext.

    Utilisee quand aucun contexte n'est disponible.
    Retourne SYSTEM_USER et is_admin=True (pas de filtrage).

    Usage:
        ctx = NullTenantContext()
        # Toutes les donnees sont accessibles
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
