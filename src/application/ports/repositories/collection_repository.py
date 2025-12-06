"""
Interface du repository de Collections.
"""

from abc import ABC, abstractmethod

from src.domain.entities.collection import Collection
from src.domain.value_objects import PageId


class CollectionRepository(ABC):
    """
    Interface pour la persistance des Collections.
    """

    @abstractmethod
    def get_by_id(self, collection_id: int) -> Collection | None:
        """Recupere une collection par son ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Collection | None:
        """Recupere une collection par son nom."""
        pass

    @abstractmethod
    def find_all(self) -> list[Collection]:
        """Recupere toutes les collections."""
        pass

    @abstractmethod
    def find_containing_page(self, page_id: PageId) -> list[Collection]:
        """Recupere les collections contenant une page."""
        pass

    @abstractmethod
    def save(self, collection: Collection) -> Collection:
        """Sauvegarde une collection."""
        pass

    @abstractmethod
    def delete(self, collection_id: int) -> bool:
        """Supprime une collection."""
        pass

    @abstractmethod
    def add_page_to_collection(
        self,
        collection_id: int,
        page_id: PageId
    ) -> bool:
        """Ajoute une page a une collection."""
        pass

    @abstractmethod
    def remove_page_from_collection(
        self,
        collection_id: int,
        page_id: PageId
    ) -> bool:
        """Retire une page d'une collection."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Compte le nombre de collections."""
        pass
