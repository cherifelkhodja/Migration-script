"""
TenantAwareMixin - Mixin pour les entites avec proprietaire.

Responsabilite unique:
----------------------
Ajouter la notion de propriete (owner_id) aux entites
et fournir les methodes de verification d'acces.

Usage:
------
    @dataclass
    class Collection(TenantAwareMixin):
        id: int
        name: str
        owner_id: UserId = None

    collection = Collection(id=1, name="Test", owner_id=user_id)
    if collection.belongs_to(current_user_id):
        print("Acces autorise")
"""

from typing import Optional

from src.domain.value_objects.user_id import UserId


class TenantAwareMixin:
    """
    Mixin pour les entites tenant-aware.

    Ajoute owner_id et methodes de verification.

    Attributes:
        owner_id: UserId du proprietaire (None = public).
    """

    owner_id: Optional[UserId] = None

    def belongs_to(self, user_id: UserId) -> bool:
        """
        Verifie l'appartenance a un utilisateur.

        Args:
            user_id: UserId a verifier.

        Returns:
            True si l'entite lui appartient.
        """
        if self.owner_id is None:
            return True
        return self.owner_id == user_id

    @property
    def is_public(self) -> bool:
        """
        True si l'entite est publique.

        Public = owner_id None ou SYSTEM_USER.
        """
        if self.owner_id is None:
            return True
        return self.owner_id.is_system
