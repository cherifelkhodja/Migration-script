"""
Billing Router - Endpoints de facturation.

Responsabilite unique:
----------------------
Exposer les endpoints checkout, webhook, subscription, portal.

Endpoints:
----------
- POST /billing/checkout: Creer une session checkout
- POST /billing/webhook: Recevoir les events Stripe
- GET /billing/subscription: Statut abonnement
- POST /billing/portal: Lien vers le portail client
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request

from src.presentation.api.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    SubscriptionStatus,
    WebhookResponse,
)
from src.presentation.api.billing.stripe_service import StripeService
from src.presentation.api.config import get_settings, APISettings
from src.presentation.api.dependencies import (
    get_current_user,
    get_user_repository,
    get_audit_repository,
)
from src.domain.entities.user import User
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)


router = APIRouter(prefix="/billing", tags=["Billing"])


def get_stripe_service(
    settings: APISettings = Depends(get_settings)
) -> StripeService:
    """Retourne le StripeService."""
    return StripeService(settings)


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Creer une session checkout",
    description="Redirige vers Stripe pour le paiement.",
)
def create_checkout(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
    stripe_service: StripeService = Depends(get_stripe_service),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repository),
):
    """
    Cree une session de checkout Stripe.

    Returns:
        URL de checkout et session_id.
    """
    try:
        url, session_id = stripe_service.create_checkout_session(
            user_id=user.id,
            email=user.email or f"{user.username}@example.com",
            plan=data.plan,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )

        # Audit
        audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="checkout_started",
            details={"plan": data.plan.value, "session_id": session_id},
        )

        return CheckoutResponse(checkout_url=url, session_id=session_id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Webhook Stripe",
    description="Recoit les events Stripe (ne pas appeler manuellement).",
)
async def stripe_webhook(
    request: Request,
    stripe_service: StripeService = Depends(get_stripe_service),
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    audit_repo: SqlAlchemyAuditRepository = Depends(get_audit_repository),
):
    """
    Traite les webhooks Stripe.

    Events geres:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.verify_webhook(payload, signature)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Traiter selon le type d'event
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data, user_repo, audit_repo)

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data, audit_repo)

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, user_repo, audit_repo)

    return WebhookResponse(received=True)


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Statut abonnement",
    description="Retourne le statut de l'abonnement de l'utilisateur.",
)
def get_subscription(
    user: User = Depends(get_current_user),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Retourne le statut d'abonnement.

    Returns:
        SubscriptionResponse avec status et plan.
    """
    # Si pas de stripe_customer_id, pas d'abonnement
    if not hasattr(user, 'stripe_customer_id') or not user.stripe_customer_id:
        return SubscriptionResponse(status=SubscriptionStatus.NONE)

    sub = stripe_service.get_subscription(user.stripe_customer_id)
    if not sub:
        return SubscriptionResponse(status=SubscriptionStatus.NONE)

    return SubscriptionResponse(**sub)


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Portail client",
    description="Retourne l'URL du portail client Stripe.",
)
def create_portal(
    data: PortalRequest,
    user: User = Depends(get_current_user),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    """
    Cree une session du portail client Stripe.

    Le portail permet de gerer l'abonnement et les paiements.
    """
    if not hasattr(user, 'stripe_customer_id') or not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun abonnement actif",
        )

    url = stripe_service.create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=data.return_url,
    )

    return PortalResponse(portal_url=url)


# Handlers internes

def _handle_checkout_completed(
    data: dict,
    user_repo: SqlAlchemyUserRepository,
    audit_repo: SqlAlchemyAuditRepository,
) -> None:
    """Traite un checkout complete."""
    user_id = data.get("metadata", {}).get("user_id")
    customer_id = data.get("customer")

    if user_id and customer_id:
        # Sauvegarder le customer_id sur l'utilisateur
        from uuid import UUID
        user = user_repo.get_by_id(UUID(user_id))
        if user:
            # Note: necessite d'ajouter stripe_customer_id au modele User
            audit_repo.log(
                user_id=user.id,
                username=user.username,
                action="subscription_created",
                details={"customer_id": customer_id},
            )


def _handle_subscription_updated(
    data: dict,
    audit_repo: SqlAlchemyAuditRepository,
) -> None:
    """Traite une mise a jour d'abonnement."""
    user_id = data.get("metadata", {}).get("user_id")
    if user_id:
        from uuid import UUID
        audit_repo.log(
            user_id=UUID(user_id),
            username="system",
            action="subscription_updated",
            details={"status": data.get("status")},
        )


def _handle_subscription_deleted(
    data: dict,
    user_repo: SqlAlchemyUserRepository,
    audit_repo: SqlAlchemyAuditRepository,
) -> None:
    """Traite une annulation d'abonnement."""
    user_id = data.get("metadata", {}).get("user_id")
    if user_id:
        from uuid import UUID
        audit_repo.log(
            user_id=UUID(user_id),
            username="system",
            action="subscription_canceled",
            details={},
        )
