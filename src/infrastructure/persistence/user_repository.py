"""
Repository pour la gestion des utilisateurs et de l'audit.

Fonctionnalites:
----------------
- CRUD utilisateurs
- Authentification (login/logout)
- Gestion des roles
- Audit trail des actions

Securite:
---------
- Mots de passe hashes avec bcrypt
- Verrouillage apres tentatives echouees
- Logging de toutes les connexions

Multi-tenancy:
--------------
Chaque utilisateur a son propre espace de donnees.
Les fonctions de filtrage par user_id sont fournies.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
import json

from sqlalchemy import func, desc

from src.infrastructure.persistence.models import UserModel, AuditLog, AuditAction
from src.infrastructure.persistence.database import DatabaseManager
from src.domain.entities.user import User
from src.domain.value_objects.role import Role


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

def create_user(
    db: DatabaseManager,
    username: str,
    email: str,
    password: str,
    role: str = "viewer"
) -> Optional[User]:
    """
    Cree un nouvel utilisateur.

    Args:
        db: DatabaseManager instance.
        username: Nom d'utilisateur unique.
        email: Adresse email unique.
        password: Mot de passe en clair (sera hashe).
        role: Role (admin, analyst, viewer).

    Returns:
        User cree ou None si erreur (username/email deja pris).

    Example:
        >>> user = create_user(db, "john", "john@ex.com", "pass123", "analyst")
        >>> user.username
        'john'
    """
    with db.get_session() as session:
        # Verifier unicite
        existing = session.query(UserModel).filter(
            (UserModel.username == username.lower()) |
            (UserModel.email == email.lower())
        ).first()

        if existing:
            return None

        # Creer l'entite domaine (hash le password)
        user = User.create(username, email, password, role)

        # Persister
        user_model = UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            role=str(user.role),
            is_active=user.is_active,
            created_at=user.created_at,
        )
        session.add(user_model)
        session.commit()

        return user


def get_user_by_id(db: DatabaseManager, user_id: UUID) -> Optional[User]:
    """
    Recupere un utilisateur par son ID.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.

    Returns:
        User ou None si non trouve.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(UserModel.id == user_id).first()
        if model:
            return _model_to_entity(model)
        return None


def get_user_by_username(db: DatabaseManager, username: str) -> Optional[User]:
    """
    Recupere un utilisateur par son nom d'utilisateur.

    Args:
        db: DatabaseManager instance.
        username: Nom d'utilisateur.

    Returns:
        User ou None si non trouve.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(
            UserModel.username == username.lower()
        ).first()
        if model:
            return _model_to_entity(model)
        return None


def get_user_by_email(db: DatabaseManager, email: str) -> Optional[User]:
    """
    Recupere un utilisateur par son email.

    Args:
        db: DatabaseManager instance.
        email: Adresse email.

    Returns:
        User ou None si non trouve.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(
            UserModel.email == email.lower()
        ).first()
        if model:
            return _model_to_entity(model)
        return None


def get_all_users(db: DatabaseManager, active_only: bool = True) -> List[User]:
    """
    Liste tous les utilisateurs.

    Args:
        db: DatabaseManager instance.
        active_only: Si True, ne retourne que les comptes actifs.

    Returns:
        Liste des utilisateurs.
    """
    with db.get_session() as session:
        query = session.query(UserModel)
        if active_only:
            query = query.filter(UserModel.is_active == True)
        query = query.order_by(UserModel.created_at.desc())

        return [_model_to_entity(m) for m in query.all()]


def update_user(
    db: DatabaseManager,
    user_id: UUID,
    email: str = None,
    role: str = None,
    is_active: bool = None
) -> bool:
    """
    Met a jour un utilisateur.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.
        email: Nouvelle adresse email (optionnel).
        role: Nouveau role (optionnel).
        is_active: Nouveau statut actif (optionnel).

    Returns:
        True si mise a jour reussie.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not model:
            return False

        if email is not None:
            model.email = email.lower()
        if role is not None:
            model.role = role.lower()
        if is_active is not None:
            model.is_active = is_active

        model.updated_at = datetime.utcnow()
        session.commit()
        return True


def update_password(db: DatabaseManager, user_id: UUID, new_password: str) -> bool:
    """
    Met a jour le mot de passe d'un utilisateur.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.
        new_password: Nouveau mot de passe en clair.

    Returns:
        True si mise a jour reussie.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not model:
            return False

        # Utiliser l'entite domaine pour hasher
        user = _model_to_entity(model)
        user.update_password(new_password)

        model.password_hash = user.password_hash
        model.updated_at = datetime.utcnow()
        session.commit()
        return True


def delete_user(db: DatabaseManager, user_id: UUID) -> bool:
    """
    Supprime un utilisateur (soft delete = desactive).

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.

    Returns:
        True si suppression reussie.
    """
    return update_user(db, user_id, is_active=False)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

def authenticate(
    db: DatabaseManager,
    username: str,
    password: str,
    ip_address: str = None,
    user_agent: str = None
) -> tuple[Optional[User], str]:
    """
    Authentifie un utilisateur.

    Args:
        db: DatabaseManager instance.
        username: Nom d'utilisateur ou email.
        password: Mot de passe en clair.
        ip_address: Adresse IP du client (pour audit).
        user_agent: User-Agent du navigateur (pour audit).

    Returns:
        Tuple (User, message):
            - (User, "success") si authentification reussie
            - (None, "invalid_credentials") si identifiants incorrects
            - (None, "account_locked") si compte verrouille
            - (None, "account_inactive") si compte desactive
    """
    with db.get_session() as session:
        # Chercher par username ou email
        model = session.query(UserModel).filter(
            (UserModel.username == username.lower()) |
            (UserModel.email == username.lower())
        ).first()

        if not model:
            log_audit(
                db, None, None, AuditAction.LOGIN_FAILED,
                details={"username": username, "reason": "user_not_found"},
                ip_address=ip_address, user_agent=user_agent
            )
            return None, "invalid_credentials"

        user = _model_to_entity(model)

        # Verifier si compte actif
        if not user.is_active:
            log_audit(
                db, user.id, user.username, AuditAction.LOGIN_FAILED,
                details={"reason": "account_inactive"},
                ip_address=ip_address, user_agent=user_agent
            )
            return None, "account_inactive"

        # Verifier si verrouille
        if user.is_locked:
            log_audit(
                db, user.id, user.username, AuditAction.LOGIN_FAILED,
                details={"reason": "account_locked", "locked_until": str(user.locked_until)},
                ip_address=ip_address, user_agent=user_agent
            )
            return None, "account_locked"

        # Verifier mot de passe
        if not user.verify_password(password):
            # Incrementer les tentatives echouees
            model.failed_attempts += 1
            if model.failed_attempts >= User.MAX_FAILED_ATTEMPTS:
                model.locked_until = datetime.utcnow() + timedelta(
                    minutes=User.LOCK_DURATION_MINUTES
                )
            session.commit()

            log_audit(
                db, user.id, user.username, AuditAction.LOGIN_FAILED,
                details={"reason": "wrong_password", "attempts": model.failed_attempts},
                ip_address=ip_address, user_agent=user_agent
            )
            return None, "invalid_credentials"

        # Connexion reussie
        model.last_login = datetime.utcnow()
        model.failed_attempts = 0
        model.locked_until = None
        session.commit()

        log_audit(
            db, user.id, user.username, AuditAction.LOGIN_SUCCESS,
            ip_address=ip_address, user_agent=user_agent
        )

        # Retourner l'entite mise a jour
        user.record_login()
        return user, "success"


def unlock_user(db: DatabaseManager, user_id: UUID) -> bool:
    """
    Deverrouille un compte utilisateur.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.

    Returns:
        True si deverrouillage reussi.
    """
    with db.get_session() as session:
        model = session.query(UserModel).filter(UserModel.id == user_id).first()
        if not model:
            return False

        model.failed_attempts = 0
        model.locked_until = None
        model.updated_at = datetime.utcnow()
        session.commit()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

def log_audit(
    db: DatabaseManager,
    user_id: UUID,
    username: str,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    details: Dict[str, Any] = None,
    ip_address: str = None,
    user_agent: str = None
) -> None:
    """
    Enregistre une action dans le journal d'audit.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur (None si action systeme).
        username: Nom d'utilisateur.
        action: Type d'action (voir AuditAction).
        resource_type: Type de ressource (page, user, etc.).
        resource_id: Identifiant de la ressource.
        details: Details supplementaires (dict -> JSON).
        ip_address: Adresse IP du client.
        user_agent: User-Agent du navigateur.
    """
    with db.get_session() as session:
        log_entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(log_entry)
        session.commit()


def get_audit_logs(
    db: DatabaseManager,
    user_id: UUID = None,
    action: str = None,
    resource_type: str = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Recupere les logs d'audit.

    Args:
        db: DatabaseManager instance.
        user_id: Filtrer par utilisateur (optionnel).
        action: Filtrer par type d'action (optionnel).
        resource_type: Filtrer par type de ressource (optionnel).
        days: Nombre de jours d'historique.
        limit: Nombre max de resultats.

    Returns:
        Liste de dictionnaires avec les logs d'audit.
    """
    with db.get_session() as session:
        query = session.query(AuditLog)

        # Filtres
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.created_at >= since)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)

        query = query.order_by(desc(AuditLog.created_at)).limit(limit)

        results = []
        for log in query.all():
            results.append({
                "id": log.id,
                "user_id": str(log.user_id) if log.user_id else None,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": json.loads(log.details) if log.details else None,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
            })

        return results


def get_user_activity(db: DatabaseManager, user_id: UUID, days: int = 7) -> Dict[str, Any]:
    """
    Recupere un resume de l'activite d'un utilisateur.

    Args:
        db: DatabaseManager instance.
        user_id: UUID de l'utilisateur.
        days: Nombre de jours d'historique.

    Returns:
        Dict avec statistiques d'activite.
    """
    with db.get_session() as session:
        since = datetime.utcnow() - timedelta(days=days)

        # Compter par type d'action
        counts = session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= since
        ).group_by(AuditLog.action).all()

        action_counts = {action: count for action, count in counts}

        # Derniere activite
        last_activity = session.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(desc(AuditLog.created_at)).first()

        return {
            "user_id": str(user_id),
            "period_days": days,
            "total_actions": sum(action_counts.values()),
            "actions": action_counts,
            "last_activity": last_activity.created_at if last_activity else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _model_to_entity(model: UserModel) -> User:
    """
    Convertit un modele SQLAlchemy en entite domaine.

    Args:
        model: Instance UserModel.

    Returns:
        Instance User.
    """
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


def ensure_admin_exists(db: DatabaseManager) -> bool:
    """
    S'assure qu'au moins un admin existe.

    Cree un admin par defaut si aucun n'existe.
    Credentials par defaut: admin / admin123 (a changer!)

    Args:
        db: DatabaseManager instance.

    Returns:
        True si un admin existe ou a ete cree.
    """
    with db.get_session() as session:
        admin_exists = session.query(UserModel).filter(
            UserModel.role == "admin",
            UserModel.is_active == True
        ).first()

        if admin_exists:
            return True

        # Creer admin par defaut
        user = create_user(
            db,
            username="admin",
            email="admin@localhost",
            password="admin123",
            role="admin"
        )

        return user is not None


def get_users_count(db: DatabaseManager) -> Dict[str, int]:
    """
    Compte les utilisateurs par role.

    Args:
        db: DatabaseManager instance.

    Returns:
        Dict avec comptes par role.
    """
    with db.get_session() as session:
        counts = session.query(
            UserModel.role,
            func.count(UserModel.id).label('count')
        ).filter(
            UserModel.is_active == True
        ).group_by(UserModel.role).all()

        result = {"admin": 0, "analyst": 0, "viewer": 0, "total": 0}
        for role, count in counts:
            result[role] = count
            result["total"] += count

        return result
