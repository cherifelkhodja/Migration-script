"""
Modeles SQLAlchemy pour l'authentification et l'audit.

Tables:
-------
- users: Utilisateurs avec roles
- audit_log: Journal des actions utilisateur

Roles disponibles:
------------------
- admin: Acces complet
- analyst: Recherche et modification
- viewer: Lecture seule

Securite:
---------
- Mots de passe hashes avec bcrypt
- Verrouillage apres 5 tentatives echouees
- Audit trail de toutes les actions sensibles
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from src.infrastructure.persistence.models.base import Base


class UserModel(Base):
    """
    Table users - Utilisateurs de l'application.

    Stocke les informations d'authentification et le role.
    Le mot de passe est stocke sous forme de hash bcrypt.

    Colonnes:
        id: UUID unique
        username: Identifiant de connexion (unique)
        email: Adresse email (unique)
        password_hash: Hash bcrypt du mot de passe
        role: admin, analyst, ou viewer
        is_active: Compte actif ou desactive
        created_at: Date de creation
        updated_at: Derniere modification
        last_login: Derniere connexion
        failed_attempts: Tentatives echouees consecutives
        locked_until: Date de fin de verrouillage
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_users_active', 'is_active'),
        Index('idx_users_role', 'role'),
    )


class AuditLog(Base):
    """
    Table audit_log - Journal des actions utilisateur.

    Enregistre toutes les actions sensibles pour tracabilite:
    - Connexions/deconnexions
    - Modifications de donnees
    - Actions d'administration
    - Exports de donnees

    Colonnes:
        id: Identifiant auto-incremente
        user_id: UUID de l'utilisateur (nullable si action systeme)
        username: Nom d'utilisateur (denormalise pour historique)
        action: Type d'action (login, search, export, etc.)
        resource_type: Type de ressource concernee (page, user, etc.)
        resource_id: Identifiant de la ressource
        details: Details JSON de l'action
        ip_address: Adresse IP du client
        user_agent: User-Agent du navigateur
        created_at: Timestamp de l'action
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    username = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_created', 'created_at'),
    )


# Actions d'audit standard
class AuditAction:
    """Constantes pour les types d'actions d'audit."""

    # Authentification
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"

    # Recherche
    SEARCH_STARTED = "search_started"
    SEARCH_COMPLETED = "search_completed"

    # Pages
    PAGE_VIEWED = "page_viewed"
    PAGE_UPDATED = "page_updated"
    PAGE_BLACKLISTED = "page_blacklisted"
    PAGE_FAVORITED = "page_favorited"

    # Export
    EXPORT_CSV = "export_csv"
    EXPORT_DATA = "export_data"

    # Administration
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    SETTINGS_CHANGED = "settings_changed"

    # Maintenance
    CLEANUP_DUPLICATES = "cleanup_duplicates"
    ARCHIVE_DATA = "archive_data"
