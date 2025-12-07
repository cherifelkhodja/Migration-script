"""
Port UserRepository - Interface pour la persistance des utilisateurs.

Ce port definit le contrat que doivent implementer les adapters
de persistance pour les utilisateurs. Il suit le pattern Repository
de Domain-Driven Design.

Responsabilite unique:
----------------------
Definir les operations CRUD pour l'entite User.
L'authentification et l'audit sont dans des ports separes.

Usage:
------
    # Dans un use case
    class CreateUserUseCase:
        def __init__(self, user_repo: UserRepository):
            self.user_repo = user_repo

        def execute(self, request: CreateUserRequest) -> User:
            user = User.create(...)
            return self.user_repo.save(user)
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from src.domain.entities.user import User


class UserRepository(ABC):
    """
    Interface Repository pour les utilisateurs.

    Contrat pour la persistance des entites User.
    Implementee par SqlAlchemyUserRepository.
    """

    @abstractmethod
    def save(self, user: User) -> User:
        """Persiste un utilisateur (create ou update)."""
        ...

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Recupere un utilisateur par son ID."""
        ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """Recupere un utilisateur par son username."""
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Recupere un utilisateur par son email."""
        ...

    @abstractmethod
    def find_all(self, active_only: bool = True) -> List[User]:
        """Liste tous les utilisateurs."""
        ...

    @abstractmethod
    def delete(self, user_id: UUID) -> bool:
        """Supprime un utilisateur (soft delete)."""
        ...

    @abstractmethod
    def exists(self, username: str) -> bool:
        """Verifie si un username existe."""
        ...
