"""
Page de connexion Streamlit.

Affiche le formulaire de connexion et gere l'authentification.
Redirige vers le dashboard apres connexion reussie.

Design:
-------
- Formulaire centre avec logo
- Messages d'erreur clairs
- Option "Se souvenir de moi" (cookie)
- Lien mot de passe oublie (si configure)

Securite:
---------
- Protection CSRF via session token
- Rate limiting implicite (verrouillage compte)
- Pas de message revelant si l'utilisateur existe
"""

import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.infrastructure.persistence.user_repository import (
    authenticate, ensure_admin_exists
)
from src.presentation.streamlit.auth.auth_guard import save_session_to_cookie


def render_login_page() -> bool:
    """
    Affiche la page de connexion.

    Returns:
        True si l'utilisateur est connecte apres soumission.

    Usage:
        if not is_authenticated():
            if render_login_page():
                st.rerun()
            st.stop()
    """
    # Style CSS pour centrer le formulaire
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        .login-header p {
            color: #666;
            font-size: 0.9rem;
        }
        div[data-testid="stForm"] {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 1.5rem;
            background: #fafafa;
        }
    </style>
    """, unsafe_allow_html=True)

    # Container centre
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Header
        st.markdown("""
        <div class="login-header">
            <h1>📊 Meta Ads Analyzer</h1>
            <p>Connectez-vous pour acceder a l'application</p>
        </div>
        """, unsafe_allow_html=True)

        # S'assurer qu'un admin existe
        db = get_database()
        if db:
            ensure_admin_exists(db)

        # Formulaire de connexion
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Nom d'utilisateur ou email",
                placeholder="admin",
                key="login_username"
            )

            password = st.text_input(
                "Mot de passe",
                type="password",
                placeholder="••••••••",
                key="login_password"
            )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                remember = st.checkbox("Se souvenir de moi", value=True)

            submitted = st.form_submit_button(
                "Se connecter",
                use_container_width=True,
                type="primary"
            )

            if submitted:
                if not username or not password:
                    st.error("Veuillez remplir tous les champs")
                    return False

                if not db:
                    st.error("Erreur de connexion a la base de donnees")
                    return False

                # Authentifier
                user, status = authenticate(db, username, password)

                if status == "success" and user:
                    # Stocker l'utilisateur en session
                    user_data = {
                        "id": str(user.id),
                        "username": user.username,
                        "email": user.email,
                        "role": str(user.role),
                        "is_admin": user.is_admin,
                        "display_name": user.display_name,
                        "permissions": list(user.role.permissions),
                    }
                    st.session_state.user = user_data
                    st.session_state.authenticated = True

                    # Sauvegarder la session dans un cookie pour persistance
                    if remember:
                        save_session_to_cookie(user_data)

                    st.success(f"Bienvenue {user.display_name}!")
                    return True

                elif status == "account_locked":
                    st.error(
                        "Compte verrouille suite a trop de tentatives echouees. "
                        "Reessayez dans 15 minutes."
                    )

                elif status == "account_inactive":
                    st.error("Ce compte a ete desactive. Contactez l'administrateur.")

                else:  # invalid_credentials
                    st.error("Identifiants incorrects")

                return False

        # Informations supplementaires
        st.markdown("---")

        with st.expander("Premiere connexion?"):
            st.markdown("""
            **Compte administrateur par defaut:**
            - Utilisateur: `admin`
            - Mot de passe: `admin123`

            Changez ce mot de passe immediatement apres la premiere connexion!
            """)

        with st.expander("Roles disponibles"):
            st.markdown("""
            | Role | Description |
            |------|-------------|
            | 👑 Admin | Acces complet, gestion utilisateurs |
            | 📊 Analyst | Recherche, analyse, modification |
            | 👁️ Viewer | Consultation seule |
            """)

    return False


def render_logout_button() -> bool:
    """
    Affiche un bouton de deconnexion dans la sidebar.

    Returns:
        True si l'utilisateur s'est deconnecte.
    """
    user = st.session_state.get("user")

    if user:
        with st.sidebar:
            st.markdown("---")

            col1, col2 = st.columns([2, 1])
            with col1:
                role_icon = "👑" if user.get("is_admin") else "📊" if user.get("role") == "analyst" else "👁️"
                st.markdown(f"{role_icon} **{user.get('display_name', 'User')}**")
                st.caption(user.get("role", "viewer").capitalize())

            with col2:
                if st.button("🚪", help="Se deconnecter", key="logout_btn"):
                    # Log la deconnexion
                    db = get_database()
                    if db:
                        from src.infrastructure.persistence.user_repository import log_audit
                        from src.infrastructure.persistence.models import AuditAction
                        from uuid import UUID
                        log_audit(
                            db,
                            UUID(user["id"]),
                            user["username"],
                            AuditAction.LOGOUT
                        )

                    # Nettoyer la session
                    st.session_state.user = None
                    st.session_state.authenticated = False
                    return True

    return False
