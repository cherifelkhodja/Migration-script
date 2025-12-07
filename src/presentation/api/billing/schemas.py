"""
Billing Schemas - Modeles Pydantic pour le billing.

Responsabilite unique:
----------------------
Definir les schemas de requete/reponse pour les endpoints billing.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class PlanType(str, Enum):
    """Types de plans disponibles."""

    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class CheckoutRequest(BaseModel):
    """
    Requete pour creer une session checkout.

    Example:
        {"plan": "pro", "success_url": "https://...", "cancel_url": "https://..."}
    """

    plan: PlanType
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Reponse avec l'URL de checkout Stripe."""

    checkout_url: str
    session_id: str


class PortalRequest(BaseModel):
    """Requete pour le portail client."""

    return_url: str


class PortalResponse(BaseModel):
    """Reponse avec l'URL du portail."""

    portal_url: str


class SubscriptionStatus(str, Enum):
    """Statuts d'abonnement."""

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    NONE = "none"


class SubscriptionResponse(BaseModel):
    """Statut de l'abonnement utilisateur."""

    status: SubscriptionStatus
    plan: Optional[PlanType] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class WebhookResponse(BaseModel):
    """Reponse au webhook."""

    received: bool
