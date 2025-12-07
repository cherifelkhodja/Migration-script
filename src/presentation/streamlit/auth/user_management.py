"""
Page de gestion des utilisateurs (admin only).

Permet aux administrateurs de:
- Creer de nouveaux utilisateurs
- Modifier les roles
- Activer/desactiver des comptes
- Voir les logs d'audit

Accessible depuis Settings > Utilisateurs.
"""

import streamlit as st
from datetime import datetime

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.auth.auth_guard import require_admin, get_current_user
from src.infrastructure.persistence.user_repository import (
    create_user, get_all_users, update_user, update_password,
    unlock_user, get_audit_logs, get_users_count, get_user_activity
)


def render_user_management() -> None:
    """
    Affiche la page de gestion des utilisateurs.

    Reservee aux administrateurs.
    """
    if not require_admin():
        st.error("Cette page est reservee aux administrateurs")
        return

    db = get_database()
    if not db:
        st.error("Erreur de connexion a la base de donnees")
        return

    st.header("👥 Gestion des utilisateurs")

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "📋 Utilisateurs",
        "➕ Nouveau",
        "📊 Audit"
    ])

    with tab1:
        _render_users_list(db)

    with tab2:
        _render_create_user(db)

    with tab3:
        _render_audit_logs(db)


def _render_users_list(db) -> None:
    """Affiche la liste des utilisateurs."""

    # Stats
    counts = get_users_count(db)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", counts["total"])
    with col2:
        st.metric("👑 Admins", counts["admin"])
    with col3:
        st.metric("📊 Analysts", counts["analyst"])
    with col4:
        st.metric("👁️ Viewers", counts["viewer"])

    st.markdown("---")

    # Options de filtre
    show_inactive = st.checkbox("Afficher les comptes inactifs", value=False)

    # Liste des utilisateurs
    users = get_all_users(db, active_only=not show_inactive)

    if not users:
        st.info("Aucun utilisateur trouve")
        return

    current_user = get_current_user()

    for user in users:
        with st.expander(
            f"{'👑' if user.is_admin else '📊' if user.role.is_analyst else '👁️'} "
            f"{user.username} ({user.email})"
            f"{' 🔒' if user.is_locked else ''}"
            f"{' ❌' if not user.is_active else ''}"
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**Role:** {user.role.display_name}")
                st.write(f"**Email:** {user.email}")
                st.write(f"**Cree le:** {user.created_at.strftime('%d/%m/%Y %H:%M')}")
                if user.last_login:
                    st.write(f"**Derniere connexion:** {user.last_login.strftime('%d/%m/%Y %H:%M')}")
                else:
                    st.write("**Derniere connexion:** Jamais")

                if user.is_locked:
                    st.warning(f"Compte verrouille jusqu'a {user.locked_until}")

            with col2:
                # Ne pas permettre de se modifier soi-meme (sauf mot de passe)
                is_self = str(user.id) == current_user.get("id")

                if not is_self:
                    # Changer le role
                    new_role = st.selectbox(
                        "Role",
                        ["admin", "analyst", "viewer"],
                        index=["admin", "analyst", "viewer"].index(str(user.role)),
                        key=f"role_{user.id}"
                    )
                    if new_role != str(user.role):
                        if st.button("Changer role", key=f"change_role_{user.id}"):
                            update_user(db, user.id, role=new_role)
                            st.success("Role mis a jour")
                            st.rerun()

                    # Activer/Desactiver
                    if user.is_active:
                        if st.button("Desactiver", key=f"deactivate_{user.id}"):
                            update_user(db, user.id, is_active=False)
                            st.success("Compte desactive")
                            st.rerun()
                    else:
                        if st.button("Activer", key=f"activate_{user.id}"):
                            update_user(db, user.id, is_active=True)
                            st.success("Compte active")
                            st.rerun()

                    # Deverrouiller
                    if user.is_locked:
                        if st.button("Deverrouiller", key=f"unlock_{user.id}"):
                            unlock_user(db, user.id)
                            st.success("Compte deverrouille")
                            st.rerun()

                # Reset mot de passe (aussi pour soi-meme)
                with st.popover("🔑 Reset mot de passe"):
                    new_pwd = st.text_input(
                        "Nouveau mot de passe",
                        type="password",
                        key=f"pwd_{user.id}"
                    )
                    confirm_pwd = st.text_input(
                        "Confirmer",
                        type="password",
                        key=f"pwd_confirm_{user.id}"
                    )
                    if st.button("Changer", key=f"change_pwd_{user.id}"):
                        if new_pwd != confirm_pwd:
                            st.error("Les mots de passe ne correspondent pas")
                        elif len(new_pwd) < 6:
                            st.error("Mot de passe trop court (min 6 caracteres)")
                        else:
                            update_password(db, user.id, new_pwd)
                            st.success("Mot de passe mis a jour")


def _render_create_user(db) -> None:
    """Formulaire de creation d'utilisateur."""

    st.subheader("Creer un nouvel utilisateur")

    with st.form("create_user_form"):
        username = st.text_input(
            "Nom d'utilisateur",
            placeholder="john.doe",
            help="Unique, sera converti en minuscules"
        )

        email = st.text_input(
            "Email",
            placeholder="john.doe@example.com"
        )

        password = st.text_input(
            "Mot de passe",
            type="password",
            help="Minimum 6 caracteres"
        )

        confirm_password = st.text_input(
            "Confirmer le mot de passe",
            type="password"
        )

        role = st.selectbox(
            "Role",
            ["viewer", "analyst", "admin"],
            format_func=lambda x: {
                "admin": "👑 Administrateur",
                "analyst": "📊 Analyste",
                "viewer": "👁️ Lecteur"
            }.get(x, x)
        )

        submitted = st.form_submit_button("Creer l'utilisateur", type="primary")

        if submitted:
            # Validations
            errors = []

            if not username or len(username) < 3:
                errors.append("Nom d'utilisateur trop court (min 3 caracteres)")

            if not email or "@" not in email:
                errors.append("Email invalide")

            if not password or len(password) < 6:
                errors.append("Mot de passe trop court (min 6 caracteres)")

            if password != confirm_password:
                errors.append("Les mots de passe ne correspondent pas")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                user = create_user(db, username, email, password, role)
                if user:
                    st.success(f"Utilisateur '{username}' cree avec succes!")
                    st.balloons()
                else:
                    st.error("Erreur: nom d'utilisateur ou email deja utilise")


def _render_audit_logs(db) -> None:
    """Affiche les logs d'audit."""

    st.subheader("Journal d'audit")

    # Filtres
    col1, col2, col3 = st.columns(3)

    with col1:
        days = st.selectbox(
            "Periode",
            [1, 7, 14, 30, 90],
            index=1,
            format_func=lambda x: f"{x} jour(s)"
        )

    with col2:
        action_filter = st.selectbox(
            "Type d'action",
            ["Toutes", "Connexions", "Recherches", "Modifications", "Admin"],
        )

    with col3:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    # Mapper les filtres
    action = None
    if action_filter == "Connexions":
        action = "login"
    elif action_filter == "Recherches":
        action = "search"
    elif action_filter == "Admin":
        action = "user"

    # Recuperer les logs
    logs = get_audit_logs(db, action=action, days=days, limit=limit)

    if not logs:
        st.info("Aucun log trouve pour cette periode")
        return

    # Afficher en tableau
    st.write(f"**{len(logs)}** entrees trouvees")

    for log in logs:
        icon = _get_action_icon(log["action"])
        time_str = log["created_at"].strftime("%d/%m %H:%M")

        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])

            with col1:
                st.caption(time_str)

            with col2:
                user_str = log["username"] or "Systeme"
                st.write(f"{icon} **{user_str}** - {log['action']}")

                if log.get("resource_type"):
                    st.caption(f"{log['resource_type']}: {log.get('resource_id', '-')}")

            with col3:
                if log.get("ip_address"):
                    st.caption(log["ip_address"])


def _get_action_icon(action: str) -> str:
    """Retourne l'icone pour un type d'action."""
    icons = {
        "login_success": "🔓",
        "login_failed": "🔒",
        "logout": "🚪",
        "password_change": "🔑",
        "search_started": "🔍",
        "search_completed": "✅",
        "page_viewed": "👁️",
        "page_updated": "✏️",
        "page_blacklisted": "🚫",
        "page_favorited": "⭐",
        "export_csv": "📥",
        "user_created": "👤",
        "user_updated": "👤",
        "user_deleted": "❌",
        "settings_changed": "⚙️",
    }
    return icons.get(action, "📋")
