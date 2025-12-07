"""
RequestPasswordResetUseCase - Demande de reset de mot de passe.

Responsabilite unique:
----------------------
Generer un token de reset et envoyer l'email.

Flow:
-----
1. Verifier que l'email existe
2. Generer un token securise (UUID)
3. Stocker le token avec TTL (1 heure)
4. Envoyer l'email avec le lien de reset
"""

import secrets
from dataclasses import dataclass
from typing import Optional

from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository
from src.domain.ports.state_storage import StateStorage


@dataclass
class RequestPasswordResetRequest:
    """
    Requete de demande de reset.

    Attributes:
        email: Email de l'utilisateur.
        reset_url_base: URL de base pour le lien (ex: https://app.com/reset).
    """

    email: str
    reset_url_base: str


@dataclass
class RequestPasswordResetResponse:
    """
    Reponse de demande de reset.

    Note: Toujours success=True pour ne pas reveler si l'email existe.

    Attributes:
        success: Toujours True (securite).
        message: Message utilisateur.
        _token: Token genere (usage interne/tests uniquement).
    """

    success: bool
    message: str
    _token: Optional[str] = None  # Pour tests uniquement


class RequestPasswordResetUseCase:
    """
    Use case de demande de reset de mot de passe.

    Genere un token et envoie l'email si l'utilisateur existe.
    Pour des raisons de securite, retourne toujours succes.

    Example:
        >>> use_case = RequestPasswordResetUseCase(user_repo, state_storage, email_service, audit_repo)
        >>> response = use_case.execute(RequestPasswordResetRequest(
        ...     email="user@example.com",
        ...     reset_url_base="https://app.com/reset"
        ... ))
    """

    TOKEN_TTL_SECONDS = 3600  # 1 heure

    def __init__(
        self,
        user_repo: UserRepository,
        state_storage: StateStorage,
        email_service,  # EmailService (pas de type pour eviter import circulaire)
        audit_repo: AuditRepository,
    ):
        """
        Initialise le use case.

        Args:
            user_repo: Repository utilisateurs.
            state_storage: Stockage des tokens temporaires.
            email_service: Service d'envoi d'emails.
            audit_repo: Repository audit.
        """
        self._user_repo = user_repo
        self._state_storage = state_storage
        self._email_service = email_service
        self._audit_repo = audit_repo

    def execute(self, request: RequestPasswordResetRequest) -> RequestPasswordResetResponse:
        """
        Execute la demande de reset.

        Args:
            request: Requete avec email.

        Returns:
            RequestPasswordResetResponse (toujours succes pour securite).
        """
        # Message generique (ne pas reveler si email existe)
        generic_message = "Si cet email existe, un lien de reinitialisation a ete envoye."

        # Chercher l'utilisateur
        user = self._user_repo.get_by_email(request.email)

        if not user:
            # Log tentative sur email inexistant (securite)
            self._audit_repo.log(
                user_id=None,
                username=request.email,
                action="password_reset_requested_unknown_email",
                details={"email": request.email},
            )
            return RequestPasswordResetResponse(success=True, message=generic_message)

        if not user.is_active:
            # Compte desactive, ne pas envoyer
            return RequestPasswordResetResponse(success=True, message=generic_message)

        # Generer token securise
        token = secrets.token_urlsafe(32)

        # Stocker: token -> user_id (TTL 1 heure)
        self._state_storage.set(
            f"password_reset:{token}",
            str(user.id),
            ttl_seconds=self.TOKEN_TTL_SECONDS,
        )

        # Construire URL de reset
        reset_url = f"{request.reset_url_base}?token={token}"

        # Envoyer email
        self._send_reset_email(user, reset_url)

        # Log
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="password_reset_requested",
            details={},
        )

        return RequestPasswordResetResponse(
            success=True,
            message=generic_message,
            _token=token,  # Pour tests
        )

    def _send_reset_email(self, user, reset_url: str) -> None:
        """Envoie l'email de reset."""
        from src.infrastructure.email.templates import EmailTemplate

        template = EmailTemplate.password_reset(
            username=user.username,
            reset_url=reset_url,
        )

        self._email_service.send(
            to=user.email,
            subject=template.subject,
            html=template.html,
            text=template.text,
        )
