"""
Billing API - Integration Stripe.

Endpoints:
----------
- POST /billing/checkout: Creer une session checkout
- POST /billing/webhook: Recevoir les events Stripe
- GET /billing/subscription: Statut abonnement
- POST /billing/portal: Lien vers le portail client
"""

from src.presentation.api.billing.router import router

__all__ = ["router"]
