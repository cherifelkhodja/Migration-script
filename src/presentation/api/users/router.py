"""
Users Router - Endpoints CRUD pour les utilisateurs.

Responsabilite unique:
----------------------
Exposer les endpoints de gestion des utilisateurs.
Reserve aux administrateurs.

Endpoints:
----------
- GET /users: Lister les utilisateurs (admin)
- GET /users/{id}: Recuperer un utilisateur (admin)
- POST /users: Creer un utilisateur (admin)
- PUT /users/{id}: Mettre a jour un utilisateur (admin)
- DELETE /users/{id}: Supprimer un utilisateur (admin)
- PUT /users/{id}/password: Changer le mot de passe
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from src.presentation.api.users.schemas import (
    UserResponse,
    UserListResponse,
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
)
from src.presentation.api.dependencies import (
    get_current_user,
    get_current_admin,
    get_user_repository,
    get_audit_repository,
)
from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository
from src.application.use_cases.auth.create_user import (
    CreateUserUseCase,
    CreateUserRequest as UseCaseCreateRequest,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def _user_to_response(user: User) -> UserResponse:
    """Convertit un User en UserResponse."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


# ============ Endpoints ============

@router.get(
    "",
    response_model=UserListResponse,
    summary="Lister les utilisateurs",
    description="Retourne les utilisateurs avec pagination (admin seulement).",
)
def list_users(
    page: int = Query(1, ge=1, description="Numero de page"),
    page_size: int = Query(20, ge=1, le=100, description="Taille de page"),
    is_active: bool = Query(None, description="Filtrer par statut actif"),
    role: str = Query(None, description="Filtrer par role"),
    admin: User = Depends(get_current_admin),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Liste les utilisateurs avec pagination.
    """
    offset = (page - 1) * page_size
    users = user_repo.find_all(limit=page_size, offset=offset)
    total = user_repo.count()

    # Appliquer les filtres en memoire (simple pour l'instant)
    if is_active is not None:
        users = [u for u in users if u.is_active == is_active]
    if role:
        users = [u for u in users if u.role.name == role]

    items = [_user_to_response(u) for u in users]
    total_pages = (total + page_size - 1) // page_size

    return UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Recuperer un utilisateur",
    description="Retourne un utilisateur par son ID (admin seulement).",
)
def get_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Recupere un utilisateur par son ID.
    """
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve",
        )

    return _user_to_response(user)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Creer un utilisateur",
    description="Cree un nouvel utilisateur (admin seulement).",
)
def create_user(
    data: CreateUserRequest,
    admin: User = Depends(get_current_admin),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Cree un nouvel utilisateur.
    """
    use_case = CreateUserUseCase(user_repo, audit_repo)

    response = use_case.execute(UseCaseCreateRequest(
        username=data.username,
        email=data.email,
        password=data.password,
        role=data.role,
        created_by_id=str(admin.id),
    ))

    if not response.success:
        error_messages = {
            "username_taken": "Ce nom d'utilisateur existe deja",
            "email_taken": "Cet email existe deja",
            "username_too_short": "Nom d'utilisateur trop court (min 3 caracteres)",
            "password_too_short": "Mot de passe trop court (min 6 caracteres)",
            "invalid_email": "Email invalide",
            "invalid_role": "Role invalide (admin, analyst, viewer)",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_messages.get(response.error, response.error),
        )

    logger.info(
        "user_created",
        admin_id=str(admin.id),
        new_user_id=str(response.user.id),
        username=data.username,
    )

    return _user_to_response(response.user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Mettre a jour un utilisateur",
    description="Met a jour un utilisateur (admin seulement).",
)
def update_user(
    user_id: UUID,
    data: UpdateUserRequest,
    admin: User = Depends(get_current_admin),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Met a jour un utilisateur.
    """
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve",
        )

    # Empecher l'admin de se desactiver lui-meme
    if user_id == admin.id and data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de vous desactiver vous-meme",
        )

    if data.email is not None:
        # Verifier unicite
        existing = user_repo.get_by_email(data.email)
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet email existe deja",
            )
        user.email = data.email

    if data.role is not None:
        from src.domain.value_objects.role import Role

        if data.role == "admin":
            user.role = Role.admin()
        elif data.role == "analyst":
            user.role = Role.analyst()
        else:
            user.role = Role.viewer()

    if data.is_active is not None:
        user.is_active = data.is_active

    user_repo.save(user)

    audit_repo.log(
        user_id=admin.id,
        username=admin.username,
        action="user_updated",
        resource_type="user",
        resource_id=str(user_id),
        details=data.model_dump(exclude_none=True),
    )

    logger.info(
        "user_updated",
        admin_id=str(admin.id),
        user_id=str(user_id),
    )

    return _user_to_response(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un utilisateur",
    description="Supprime un utilisateur (admin seulement).",
)
def delete_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Supprime un utilisateur.
    """
    # Empecher l'admin de se supprimer lui-meme
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de vous supprimer vous-meme",
        )

    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve",
        )

    user_repo.delete(user_id)

    audit_repo.log(
        user_id=admin.id,
        username=admin.username,
        action="user_deleted",
        resource_type="user",
        resource_id=str(user_id),
        details={"username": user.username},
    )

    logger.info(
        "user_deleted",
        admin_id=str(admin.id),
        deleted_user_id=str(user_id),
    )


@router.put(
    "/{user_id}/password",
    response_model=UserResponse,
    summary="Changer le mot de passe",
    description="Change le mot de passe d'un utilisateur.",
)
def change_password(
    user_id: UUID,
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """
    Change le mot de passe d'un utilisateur.

    Seul l'utilisateur lui-meme ou un admin peut changer le mot de passe.
    """
    # Verifier les droits
    is_self = current_user.id == user_id
    is_admin = current_user.role.name == "admin"

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve",
        )

    # Verifier le mot de passe actuel (sauf pour admin)
    if is_self and not user.check_password(data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect",
        )

    # Changer le mot de passe
    user.update_password(data.new_password)
    user_repo.save(user)

    audit_repo.log(
        user_id=current_user.id,
        username=current_user.username,
        action="password_changed",
        resource_type="user",
        resource_id=str(user_id),
        details={},
    )

    logger.info(
        "password_changed",
        by_user_id=str(current_user.id),
        for_user_id=str(user_id),
    )

    return _user_to_response(user)
