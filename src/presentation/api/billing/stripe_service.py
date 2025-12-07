"""
StripeService - Integration Stripe.

Responsabilite unique:
----------------------
Gerer les interactions avec l'API Stripe.

Usage:
------
    service = StripeService(settings)
    url = service.create_checkout_session(user_id, "pro", success_url, cancel_url)
"""

from typing import Optional
from uuid import UUID

import stripe

from src.presentation.api.config import APISettings
from src.presentation.api.billing.schemas import PlanType, SubscriptionStatus


class StripeService:
    """
    Service d'integration Stripe.

    Gere checkout, subscriptions, et webhooks.
    """

    def __init__(self, settings: APISettings):
        """
        Initialise le service Stripe.

        Args:
            settings: Configuration avec les cles Stripe.
        """
        self._settings = settings
        stripe.api_key = settings.stripe_secret_key

        # Mapping plan -> price_id
        self._prices = {
            PlanType.STARTER: settings.stripe_price_starter,
            PlanType.PRO: settings.stripe_price_pro,
            PlanType.ENTERPRISE: settings.stripe_price_enterprise,
        }

    def create_checkout_session(
        self,
        user_id: UUID,
        email: str,
        plan: PlanType,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str]:
        """
        Cree une session de checkout Stripe.

        Args:
            user_id: ID de l'utilisateur.
            email: Email pour la facture.
            plan: Plan choisi.
            success_url: URL apres paiement reussi.
            cancel_url: URL si annulation.

        Returns:
            Tuple (checkout_url, session_id).

        Raises:
            ValueError: Si le plan n'a pas de price_id configure.
        """
        price_id = self._prices.get(plan)
        if not price_id:
            raise ValueError(f"Plan {plan} non configure")

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user_id)},
            subscription_data={
                "metadata": {"user_id": str(user_id)},
            },
        )

        return session.url, session.id

    def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """
        Cree une session du portail client.

        Args:
            customer_id: ID client Stripe.
            return_url: URL de retour.

        Returns:
            URL du portail.
        """
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    def get_subscription(
        self,
        customer_id: str
    ) -> Optional[dict]:
        """
        Recupere l'abonnement actif d'un client.

        Args:
            customer_id: ID client Stripe.

        Returns:
            Dict avec status, plan, period_end, ou None.
        """
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="all",
            limit=1,
        )

        if not subscriptions.data:
            return None

        sub = subscriptions.data[0]
        return {
            "status": self._map_status(sub.status),
            "plan": self._get_plan_from_price(sub.items.data[0].price.id),
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """
        Verifie et decode un webhook Stripe.

        Args:
            payload: Corps de la requete.
            signature: Header Stripe-Signature.

        Returns:
            Event Stripe decode.

        Raises:
            ValueError: Si signature invalide.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self._settings.stripe_webhook_secret,
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Signature invalide: {e}")

    def _map_status(self, stripe_status: str) -> SubscriptionStatus:
        """Mappe le statut Stripe vers notre enum."""
        mapping = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.PAST_DUE,
        }
        return mapping.get(stripe_status, SubscriptionStatus.NONE)

    def _get_plan_from_price(self, price_id: str) -> Optional[PlanType]:
        """Retrouve le plan depuis le price_id."""
        for plan, pid in self._prices.items():
            if pid == price_id:
                return plan
        return None
