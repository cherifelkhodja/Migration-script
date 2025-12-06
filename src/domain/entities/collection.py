"""
Entite Collection - Groupe de pages creee par l'utilisateur.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.value_objects import PageId


@dataclass
class Collection:
    """
    Collection de pages creee par l'utilisateur.

    Une Collection permet de regrouper des pages Facebook
    pour les organiser et les suivre.

    Attributes:
        id: Identifiant unique de la collection.
        name: Nom de la collection.
        description: Description optionnelle.
        page_ids: IDs des pages dans la collection.
        created_at: Date de creation.
        updated_at: Date de derniere modification.

    Example:
        >>> collection = Collection.create("Mes favoris", "Pages a surveiller")
        >>> collection.add_page(PageId("123456789"))
        >>> len(collection)
        1
    """

    id: int | None
    name: str
    description: str = ""
    page_ids: set[PageId] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Champs internes
    _is_new: bool = field(default=True, repr=False)
    _is_dirty: bool = field(default=False, repr=False)

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        page_ids: list[str] | None = None,
    ) -> "Collection":
        """
        Factory pour creer une nouvelle Collection.

        Args:
            name: Nom de la collection.
            description: Description optionnelle.
            page_ids: IDs des pages initiales.

        Returns:
            Nouvelle instance de Collection.
        """
        pages = set()
        if page_ids:
            for pid in page_ids:
                try:
                    pages.add(PageId.from_any(pid))
                except Exception:
                    pass

        return cls(
            id=None,
            name=name.strip(),
            description=description.strip(),
            page_ids=pages,
        )

    def add_page(self, page_id: PageId) -> bool:
        """
        Ajoute une page a la collection.

        Args:
            page_id: ID de la page a ajouter.

        Returns:
            True si la page a ete ajoutee, False si deja presente.
        """
        if isinstance(page_id, str):
            page_id = PageId.from_any(page_id)

        if page_id in self.page_ids:
            return False

        self.page_ids.add(page_id)
        self._mark_dirty()
        return True

    def remove_page(self, page_id: PageId) -> bool:
        """
        Retire une page de la collection.

        Args:
            page_id: ID de la page a retirer.

        Returns:
            True si la page a ete retiree, False si non presente.
        """
        if isinstance(page_id, str):
            page_id = PageId.from_any(page_id)

        if page_id not in self.page_ids:
            return False

        self.page_ids.remove(page_id)
        self._mark_dirty()
        return True

    def contains(self, page_id: PageId) -> bool:
        """
        Verifie si une page est dans la collection.

        Args:
            page_id: ID de la page.

        Returns:
            True si la page est dans la collection.
        """
        if isinstance(page_id, str):
            page_id = PageId.from_any(page_id)
        return page_id in self.page_ids

    def clear(self) -> int:
        """
        Vide la collection.

        Returns:
            Nombre de pages retirees.
        """
        count = len(self.page_ids)
        if count > 0:
            self.page_ids.clear()
            self._mark_dirty()
        return count

    def rename(self, new_name: str) -> None:
        """
        Renomme la collection.

        Args:
            new_name: Nouveau nom.
        """
        new_name = new_name.strip()
        if new_name and new_name != self.name:
            self.name = new_name
            self._mark_dirty()

    def update_description(self, description: str) -> None:
        """
        Met a jour la description.

        Args:
            description: Nouvelle description.
        """
        description = description.strip()
        if description != self.description:
            self.description = description
            self._mark_dirty()

    def _mark_dirty(self) -> None:
        """Marque la collection comme modifiee."""
        self._is_dirty = True
        self.updated_at = datetime.now()

    @property
    def is_empty(self) -> bool:
        """Retourne True si la collection est vide."""
        return len(self.page_ids) == 0

    @property
    def size(self) -> int:
        """Retourne le nombre de pages dans la collection."""
        return len(self.page_ids)

    @property
    def page_ids_list(self) -> list[str]:
        """Retourne les IDs des pages sous forme de liste de strings."""
        return [str(pid) for pid in self.page_ids]

    def __len__(self) -> int:
        """Retourne le nombre de pages."""
        return len(self.page_ids)

    def __contains__(self, page_id: PageId) -> bool:
        """Permet d'utiliser 'in' operator."""
        return self.contains(page_id)

    def __iter__(self):
        """Permet d'iterer sur les page_ids."""
        return iter(self.page_ids)

    def __eq__(self, other: object) -> bool:
        """Compare deux collections par leur ID."""
        if isinstance(other, Collection):
            if self.id is not None and other.id is not None:
                return self.id == other.id
            return self.name == other.name
        return False

    def __hash__(self) -> int:
        """Hash base sur l'ID ou le nom."""
        if self.id is not None:
            return hash(self.id)
        return hash(self.name)

    def __str__(self) -> str:
        """Representation string."""
        return f"{self.name} ({len(self)} pages)"

    def __repr__(self) -> str:
        """Representation debug."""
        return (
            f"Collection(id={self.id}, name='{self.name}', "
            f"pages={len(self)})"
        )
