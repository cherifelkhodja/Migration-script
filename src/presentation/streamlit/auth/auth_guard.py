"""
Guard d'authentification pour Streamlit.

Fournit les fonctions pour verifier l'authentification
et les permissions avant d'afficher une page.

Persistance:
------------
La session est persistee via un cookie contenant un token JWT.
Cela permet de garder l'utilisateur connecte apres un refresh
ou lors de l'ouverture d'un nouvel onglet.

Usage:
------
    # Verifier que l'utilisateur est connecte
    if not require_auth():
        st.stop()

    # Verifier une permission specifique
    if not require_permission("search"):
        st.error("Permission refusee")
        st.stop()

    # Recuperer l'utilisateur courant
    user = get_current_user()
"""

import streamlit as st
from typing import Optional, List
from uuid import UUID
import jwt
import os
from datetime import datetime, timedelta

from src.domain.value_objects.role import Role, PAGE_PERMISSIONS

# Configuration JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production-streamlit-session")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "meta_ads_session"
COOKIE_EXPIRY_DAYS = 7


def _get_cookie_manager():
    """Obtient le CookieManager (singleton via session_state)."""
    try:
        import extra_streamlit_components as stx

        # Utiliser session_state pour eviter les clés dupliquées
        if "cookie_manager" not in st.session_state:
            st.session_state.cookie_manager = stx.CookieManager(key="auth_cookies")
        return st.session_state.cookie_manager
    except ImportError:
        return None


def _create_session_token(user: dict) -> str:
    """Cree un token JWT pour la session."""
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_admin": user.get("is_admin", False),
        "exp": datetime.utcnow() + timedelta(days=COOKIE_EXPIRY_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_session_token(token: str) -> Optional[dict]:
    """Verifie et decode un token JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def restore_session_from_cookie() -> bool:
    """
    Restaure la session depuis le cookie si disponible.

    A appeler au debut de l'application.
    Le CookieManager de Streamlit necessite parfois un cycle de rendu
    pour charger les cookies. Cette fonction gere ce cas avec un rerun automatique.

    Returns:
        True si la session a ete restauree.
    """
    # Deja authentifie en session
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return True

    cookie_manager = _get_cookie_manager()
    if not cookie_manager:
        return False

    # Le CookieManager peut ne pas etre pret au premier rendu
    # On utilise un compteur pour limiter les tentatives de rerun
    restore_attempts_key = "_cookie_restore_attempts"
    max_attempts = 2

    # Lire le cookie de session
    token = cookie_manager.get(COOKIE_NAME)

    # Si pas de token et on n'a pas encore tente de rerun
    if not token:
        current_attempts = st.session_state.get(restore_attempts_key, 0)
        if current_attempts < max_attempts:
            # Marquer qu'on a tente une restauration
            st.session_state[restore_attempts_key] = current_attempts + 1
            # Petit delai pour laisser le CookieManager charger
            import time
            time.sleep(0.1)
            # Forcer un rerun pour recharger les cookies
            st.rerun()
        return False

    # Token trouve - reinitialiser le compteur
    if restore_attempts_key in st.session_state:
        del st.session_state[restore_attempts_key]

    # Verifier le token
    payload = _verify_session_token(token)
    if not payload:
        # Token invalide ou expire, supprimer le cookie
        cookie_manager.delete(COOKIE_NAME)
        return False

    # Restaurer la session depuis la base de donnees
    try:
        from src.presentation.streamlit.shared import get_database
        from src.infrastructure.persistence.user_repository import get_user_by_id

        db = get_database()
        if db:
            user = get_user_by_id(db, UUID(payload["user_id"]))
            if user and user.is_active:
                st.session_state.user = {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "role": str(user.role),
                    "is_admin": user.is_admin,
                    "display_name": user.display_name,
                    "permissions": list(user.role.permissions),
                }
                st.session_state.authenticated = True
                return True
    except Exception:
        pass

    return False


def save_session_to_cookie(user: dict) -> None:
    """
    Sauvegarde la session dans un cookie.

    A appeler apres une authentification reussie.
    """
    cookie_manager = _get_cookie_manager()
    if not cookie_manager:
        return

    token = _create_session_token(user)
    cookie_manager.set(
        COOKIE_NAME,
        token,
        expires_at=datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS)
    )


def clear_session_cookie() -> None:
    """Supprime le cookie de session."""
    cookie_manager = _get_cookie_manager()
    if cookie_manager:
        cookie_manager.delete(COOKIE_NAME)


def is_authenticated() -> bool:
    """
    Verifie si l'utilisateur est authentifie.

    Returns:
        True si un utilisateur est en session.
    """
    return (
        st.session_state.get("authenticated", False) and
        st.session_state.get("user") is not None
    )


def get_current_user() -> Optional[dict]:
    """
    Recupere l'utilisateur courant depuis la session.

    Returns:
        Dict avec les infos utilisateur ou None.

    Example:
        >>> user = get_current_user()
        >>> if user:
        ...     print(f"Connecte: {user['username']}")
    """
    if is_authenticated():
        return st.session_state.get("user")
    return None


def get_current_user_id() -> Optional[UUID]:
    """
    Recupere l'UUID de l'utilisateur courant.

    Returns:
        UUID ou None si non connecte.
    """
    user = get_current_user()
    if user and user.get("id"):
        return UUID(user["id"])
    return None


def get_current_role() -> Optional[Role]:
    """
    Recupere le Role de l'utilisateur courant.

    Returns:
        Instance Role ou None.
    """
    user = get_current_user()
    if user and user.get("role"):
        return Role.from_string(user["role"])
    return None


def require_auth() -> bool:
    """
    Exige que l'utilisateur soit authentifie.

    A utiliser au debut de chaque page protegee.
    Si non authentifie, retourne False et la page
    doit afficher le login.

    Returns:
        True si authentifie.

    Example:
        if not require_auth():
            render_login_page()
            st.stop()
    """
    return is_authenticated()


def require_permission(permission: str) -> bool:
    """
    Verifie que l'utilisateur a une permission.

    Args:
        permission: Nom de la permission requise.

    Returns:
        True si l'utilisateur a la permission.

    Example:
        if not require_permission("search"):
            st.error("Vous n'avez pas la permission de rechercher")
            st.stop()
    """
    user = get_current_user()
    if not user:
        return False

    permissions = user.get("permissions", [])
    return permission in permissions


def require_any_permission(permissions: List[str]) -> bool:
    """
    Verifie que l'utilisateur a au moins une permission.

    Args:
        permissions: Liste de permissions (OR).

    Returns:
        True si au moins une permission est presente.
    """
    user = get_current_user()
    if not user:
        return False

    user_permissions = set(user.get("permissions", []))
    return bool(user_permissions & set(permissions))


def require_all_permissions(permissions: List[str]) -> bool:
    """
    Verifie que l'utilisateur a toutes les permissions.

    Args:
        permissions: Liste de permissions (AND).

    Returns:
        True si toutes les permissions sont presentes.
    """
    user = get_current_user()
    if not user:
        return False

    user_permissions = set(user.get("permissions", []))
    return set(permissions).issubset(user_permissions)


def can_access_page(page_name: str) -> bool:
    """
    Verifie si l'utilisateur peut acceder a une page.

    Args:
        page_name: Nom de la page (ex: "Search Ads").

    Returns:
        True si l'acces est autorise.
    """
    role = get_current_role()
    if not role:
        return False
    return role.can_access_page(page_name)


def require_page_access(page_name: str) -> bool:
    """
    Exige l'acces a une page, affiche erreur sinon.

    Args:
        page_name: Nom de la page.

    Returns:
        True si acces autorise.

    Example:
        if not require_page_access("Settings"):
            st.stop()
    """
    if not is_authenticated():
        return False

    if can_access_page(page_name):
        return True

    st.error(f"Vous n'avez pas acces a cette page ({page_name})")
    st.info("Contactez un administrateur pour obtenir les permissions necessaires.")
    return False


def require_admin() -> bool:
    """
    Exige que l'utilisateur soit administrateur.

    Returns:
        True si admin.
    """
    user = get_current_user()
    return user is not None and user.get("is_admin", False)


def logout() -> None:
    """
    Deconnecte l'utilisateur courant.

    Nettoie la session, supprime le cookie et force un rerun.
    """
    # Log la deconnexion si possible
    user = get_current_user()
    if user:
        try:
            from src.presentation.streamlit.shared import get_database
            from src.infrastructure.persistence.user_repository import log_audit
            from src.infrastructure.persistence.models import AuditAction

            db = get_database()
            if db:
                log_audit(
                    db,
                    UUID(user["id"]),
                    user["username"],
                    AuditAction.LOGOUT
                )
        except Exception:
            pass  # Ne pas bloquer la deconnexion

    # Supprimer le cookie de session
    clear_session_cookie()

    # Nettoyer la session
    st.session_state.user = None
    st.session_state.authenticated = False

    # Nettoyer d'autres donnees sensibles
    keys_to_clear = [
        "search_results", "pages_final", "web_results",
        "page_ads", "winning_ads_data"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def get_accessible_pages() -> List[str]:
    """
    Liste les pages accessibles par l'utilisateur courant.

    Returns:
        Liste des noms de pages accessibles.
    """
    role = get_current_role()
    if not role:
        return []

    return [
        page_name
        for page_name in PAGE_PERMISSIONS.keys()
        if role.can_access_page(page_name)
    ]


def render_access_denied(page_name: str = None) -> None:
    """
    Affiche un message d'acces refuse.

    Args:
        page_name: Nom de la page (optionnel).
    """
    st.error("Acces refuse")

    if page_name:
        st.warning(f"Vous n'avez pas les permissions pour acceder a '{page_name}'")

    user = get_current_user()
    if user:
        role = user.get("role", "viewer")
        st.info(f"Votre role actuel: **{role.capitalize()}**")

        # Afficher les permissions de ce role
        current_role = get_current_role()
        if current_role:
            with st.expander("Vos permissions"):
                for perm in sorted(current_role.permissions):
                    st.write(f"- {perm}")

    st.markdown("---")
    st.write("Contactez un administrateur pour demander des permissions supplementaires.")
