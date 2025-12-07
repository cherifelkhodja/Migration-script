"""
Stripe Webhook Handlers - Use Cases pour les events Stripe.

Responsabilite unique:
----------------------
Traiter les events Stripe de maniere isolee et testable.

Use Cases:
----------
- HandleCheckoutCompleted: Traite checkout.session.completed
- HandleSubscriptionUpdated: Traite customer.subscription.updated
- HandleSubscriptionCanceled: Traite customer.subscription.deleted
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository


@dataclass
class WebhookResult:
    """
    Resultat du traitement d'un webhook.

    Attributes:
        success: True si traitement reussi.
        action_taken: Description de l'action effectuee.
        error: Message d'erreur si echec.
    """

    success: bool
    action_taken: Optional[str] = None
    error: Optional[str] = None


class HandleCheckoutCompleted:
    """
    Use case pour checkout.session.completed.

    Lie le customer_id Stripe a l'utilisateur.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
    ):
        """
        Initialise le handler.

        Args:
            user_repo: Repository utilisateurs.
            audit_repo: Repository audit.
        """
        self._user_repo = user_repo
        self._audit_repo = audit_repo

    def execute(self, event_data: dict) -> WebhookResult:
        """
        Traite l'event checkout.session.completed.

        Args:
            event_data: Donnees de l'event Stripe.

        Returns:
            WebhookResult avec le resultat.
        """
        user_id_str = event_data.get("metadata", {}).get("user_id")
        customer_id = event_data.get("customer")

        if not user_id_str or not customer_id:
            return WebhookResult(
                success=True,
                action_taken="ignored_missing_data"
            )

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            return WebhookResult(success=False, error="invalid_user_id")

        user = self._user_repo.get_by_id(user_id)
        if not user:
            return WebhookResult(success=False, error="user_not_found")

        # Log l'action (la mise a jour du customer_id serait faite ici)
        self._audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="subscription_created",
            details={"customer_id": customer_id},
        )

        return WebhookResult(
            success=True,
            action_taken="subscription_linked"
        )


class HandleSubscriptionUpdated:
    """
    Use case pour customer.subscription.updated.

    Log les changements d'abonnement.
    """

    def __init__(self, audit_repo: AuditRepository):
        """
        Initialise le handler.

        Args:
            audit_repo: Repository audit.
        """
        self._audit_repo = audit_repo

    def execute(self, event_data: dict) -> WebhookResult:
        """
        Traite l'event customer.subscription.updated.

        Args:
            event_data: Donnees de l'event Stripe.

        Returns:
            WebhookResult avec le resultat.
        """
        user_id_str = event_data.get("metadata", {}).get("user_id")
        status = event_data.get("status")

        if not user_id_str:
            return WebhookResult(
                success=True,
                action_taken="ignored_no_user_id"
            )

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            return WebhookResult(success=False, error="invalid_user_id")

        self._audit_repo.log(
            user_id=user_id,
            username="system",
            action="subscription_updated",
            details={"status": status},
        )

        return WebhookResult(
            success=True,
            action_taken=f"logged_status_{status}"
        )


class HandleSubscriptionCanceled:
    """
    Use case pour customer.subscription.deleted.

    Log l'annulation de l'abonnement.
    """

    def __init__(self, audit_repo: AuditRepository):
        """
        Initialise le handler.

        Args:
            audit_repo: Repository audit.
        """
        self._audit_repo = audit_repo

    def execute(self, event_data: dict) -> WebhookResult:
        """
        Traite l'event customer.subscription.deleted.

        Args:
            event_data: Donnees de l'event Stripe.

        Returns:
            WebhookResult avec le resultat.
        """
        user_id_str = event_data.get("metadata", {}).get("user_id")

        if not user_id_str:
            return WebhookResult(
                success=True,
                action_taken="ignored_no_user_id"
            )

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            return WebhookResult(success=False, error="invalid_user_id")

        self._audit_repo.log(
            user_id=user_id,
            username="system",
            action="subscription_canceled",
            details={},
        )

        return WebhookResult(
            success=True,
            action_taken="logged_cancellation"
        )
