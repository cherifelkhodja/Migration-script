"""
Billing Router - Endpoints de facturation.

Responsabilite unique:
----------------------
Exposer les endpoints checkout, webhook, subscription, portal.
Delegue la logique metier aux Use Cases.

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
from src.presentation.api.dependencies import get_current_user
from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.audit_repository import AuditRepository
from src.infrastructure.persistence.auth.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.auth.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from src.infrastructure.persistence.database import DatabaseManager
from src.application.use_cases.billing import (
    HandleCheckoutCompleted,
    HandleSubscriptionUpdated,
    HandleSubscriptionCanceled,
)


router = APIRouter(prefix="/billing", tags=["Billing"])


# ============ Dependencies ============

def get_db() -> DatabaseManager:
    """Retourne le DatabaseManager."""
    return DatabaseManager()


def get_user_repository(db: DatabaseManager = Depends(get_db)) -> UserRepository:
    """Retourne le UserRepository (abstrait)."""
    return SqlAlchemyUserRepository(db)


def get_audit_repository(db: DatabaseManager = Depends(get_db)) -> AuditRepository:
    """Retourne l'AuditRepository (abstrait)."""
    return SqlAlchemyAuditRepository(db)


def get_stripe_service(
    settings: APISettings = Depends(get_settings)
) -> StripeService:
    """Retourne le StripeService."""
    return StripeService(settings)


# ============ Endpoints ============

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
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """Cree une session de checkout Stripe."""
    try:
        url, session_id = stripe_service.create_checkout_session(
            user_id=user.id,
            email=user.email or f"{user.username}@example.com",
            plan=data.plan,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )

        audit_repo.log(
            user_id=user.id,
            username=user.username,
            action="checkout_started",
            details={"plan": data.plan.value, "session_id": session_id},
        )

        return CheckoutResponse(checkout_url=url, session_id=session_id)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Webhook Stripe",
    description="Recoit les events Stripe (ne pas appeler manuellement).",
)
async def stripe_webhook(
    request: Request,
    stripe_service: StripeService = Depends(get_stripe_service),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
):
    """Traite les webhooks Stripe via Use Cases."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.verify_webhook(payload, signature)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        HandleCheckoutCompleted(user_repo, audit_repo).execute(event_data)

    elif event_type == "customer.subscription.updated":
        HandleSubscriptionUpdated(audit_repo).execute(event_data)

    elif event_type == "customer.subscription.deleted":
        HandleSubscriptionCanceled(audit_repo).execute(event_data)

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
    """Retourne le statut d'abonnement."""
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
    """Cree une session du portail client Stripe."""
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
