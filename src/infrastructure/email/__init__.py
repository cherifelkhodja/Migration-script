"""
Email Infrastructure - Service d'envoi d'emails.

Responsabilite:
---------------
Envoyer des emails transactionnels via SendGrid.

Templates disponibles:
----------------------
- welcome: Email de bienvenue
- password_reset: Reset mot de passe
- subscription_confirmed: Confirmation abonnement
- scan_completed: Scan termine
"""

from src.infrastructure.email.service import EmailService
from src.infrastructure.email.templates import EmailTemplate

__all__ = ["EmailService", "EmailTemplate"]
