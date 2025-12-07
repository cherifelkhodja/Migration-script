"""
SqlAlchemyUserRepository - Adapter SQLAlchemy pour les utilisateurs.

Implemente le port UserRepository avec SQLAlchemy.
Responsabilite unique: CRUD des utilisateurs.

L'authentification (verification mot de passe) est geree
par le use case LoginUseCase, pas ici.
"""

from typing import Optional, List
from uuid import UUID

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.domain.value_objects.role import Role
from src.infrastructure.persistence.models import UserModel
from src.infrastructure.persistence.database import DatabaseManager


class SqlAlchemyUserRepository(UserRepository):
    """
    Repository SQLAlchemy pour les utilisateurs.

    Attributes:
        db: DatabaseManager pour les sessions.
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialise le repository.

        Args:
            db: Instance DatabaseManager.
        """
        self._db = db

    def save(self, user: User) -> User:
        """
        Persiste un utilisateur.

        Cree ou met a jour selon l'existence.

        Args:
            user: Entite User a persister.

        Returns:
            User persiste.
        """
        with self._db.get_session() as session:
            # Chercher existant
            existing = session.query(UserModel).filter(
                UserModel.id == user.id
            ).first()

            if existing:
                # Update
                existing.email = user.email
                existing.password_hash = user.password_hash
                existing.role = str(user.role)
                existing.is_active = user.is_active
                existing.failed_attempts = user.failed_attempts
                existing.locked_until = user.locked_until
                existing.last_login = user.last_login
            else:
                # Create
                model = UserModel(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    password_hash=user.password_hash,
                    role=str(user.role),
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
                session.add(model)

            session.commit()
            return user

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Recupere par ID."""
        with self._db.get_session() as session:
            model = session.query(UserModel).filter(
                UserModel.id == user_id
            ).first()
            return self._to_entity(model) if model else None

    def get_by_username(self, username: str) -> Optional[User]:
        """Recupere par username."""
        with self._db.get_session() as session:
            model = session.query(UserModel).filter(
                UserModel.username == username.lower()
            ).first()
            return self._to_entity(model) if model else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Recupere par email."""
        with self._db.get_session() as session:
            model = session.query(UserModel).filter(
                UserModel.email == email.lower()
            ).first()
            return self._to_entity(model) if model else None

    def find_all(self, active_only: bool = True) -> List[User]:
        """Liste tous les utilisateurs."""
        with self._db.get_session() as session:
            query = session.query(UserModel)
            if active_only:
                query = query.filter(UserModel.is_active == True)
            return [self._to_entity(m) for m in query.all()]

    def delete(self, user_id: UUID) -> bool:
        """Soft delete (desactive le compte)."""
        with self._db.get_session() as session:
            model = session.query(UserModel).filter(
                UserModel.id == user_id
            ).first()
            if model:
                model.is_active = False
                session.commit()
                return True
            return False

    def exists(self, username: str) -> bool:
        """Verifie l'existence d'un username."""
        return self.get_by_username(username) is not None

    def _to_entity(self, model: UserModel) -> User:
        """Convertit un model en entite."""
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            password_hash=model.password_hash,
            role=Role.from_string(model.role),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login,
            failed_attempts=model.failed_attempts,
            locked_until=model.locked_until,
        )
