"""
Module d'authentification Streamlit.

Ce module fournit les composants pour l'authentification
et le controle d'acces dans l'application Streamlit.

Composants:
-----------
- login_page: Page de connexion
- auth_guard: Decorateur/wrapper pour proteger les pages
- session: Gestion de la session utilisateur

Usage:
------
Dans dashboard.py:

    from src.presentation.streamlit.auth import (
        render_login_page, require_auth, get_current_user
    )

    # Au debut de main():
    if not require_auth():
        render_login_page()
        return

    user = get_current_user()
    if not user.can_access_page(page_name):
        st.error("Acces refuse")
        return
"""

from src.presentation.streamlit.auth.login_page import render_login_page
from src.presentation.streamlit.auth.auth_guard import (
    require_auth,
    require_permission,
    get_current_user,
    logout,
    is_authenticated,
    can_access_page,
)
from src.presentation.streamlit.auth.user_management import render_user_management

__all__ = [
    "render_login_page",
    "require_auth",
    "require_permission",
    "get_current_user",
    "logout",
    "is_authenticated",
    "can_access_page",
    "render_user_management",
]
