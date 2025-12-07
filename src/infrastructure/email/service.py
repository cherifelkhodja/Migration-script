"""
EmailService - Service d'envoi d'emails via SendGrid.

Responsabilite unique:
----------------------
Envoyer des emails transactionnels via l'API SendGrid.

Usage:
------
    service = EmailService(api_key="SG.xxx")
    service.send(
        to="user@example.com",
        subject="Hello",
        html="<h1>Hello World</h1>",
        text="Hello World"
    )
"""

from typing import Optional, List
from dataclasses import dataclass
import os

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmailResult:
    """
    Resultat d'envoi d'email.

    Attributes:
        success: True si envoi reussi.
        message_id: ID du message si succes.
        error: Message d'erreur si echec.
    """

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailService:
    """
    Service d'envoi d'emails via SendGrid.

    Gere l'envoi d'emails transactionnels avec templates.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: str = "noreply@metaadsanalyzer.com",
        from_name: str = "Meta Ads Analyzer",
    ):
        """
        Initialise le service email.

        Args:
            api_key: Cle API SendGrid (defaut: env SENDGRID_API_KEY).
            from_email: Email expediteur.
            from_name: Nom expediteur.
        """
        self._api_key = api_key or os.getenv("SENDGRID_API_KEY", "")
        self._from_email = from_email
        self._from_name = from_name
        self._enabled = bool(self._api_key)

        if not self._enabled:
            logger.warning("email_disabled", reason="No SendGrid API key")

    def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> EmailResult:
        """
        Envoie un email.

        Args:
            to: Destinataire principal.
            subject: Sujet de l'email.
            html: Corps HTML.
            text: Corps texte (fallback).
            cc: Destinataires en copie.
            bcc: Destinataires en copie cachee.

        Returns:
            EmailResult avec statut d'envoi.
        """
        if not self._enabled:
            logger.info("email_skipped", to=to, subject=subject)
            return EmailResult(
                success=False,
                error="Email service disabled (no API key)"
            )

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Email, To, Content, Cc, Bcc
            )

            # Construire le message
            message = Mail(
                from_email=Email(self._from_email, self._from_name),
                to_emails=To(to),
                subject=subject,
            )

            # Ajouter le contenu
            message.add_content(Content("text/html", html))
            if text:
                message.add_content(Content("text/plain", text))

            # Ajouter CC/BCC
            if cc:
                for email in cc:
                    message.add_cc(Cc(email))
            if bcc:
                for email in bcc:
                    message.add_bcc(Bcc(email))

            # Envoyer
            client = SendGridAPIClient(self._api_key)
            response = client.send(message)

            logger.info(
                "email_sent",
                to=to,
                subject=subject,
                status_code=response.status_code,
            )

            return EmailResult(
                success=True,
                message_id=response.headers.get("X-Message-Id"),
            )

        except Exception as e:
            logger.error(
                "email_failed",
                to=to,
                subject=subject,
                error=str(e),
            )
            return EmailResult(success=False, error=str(e))

    def send_template(
        self,
        to: str,
        template_id: str,
        dynamic_data: dict,
    ) -> EmailResult:
        """
        Envoie un email avec template SendGrid.

        Args:
            to: Destinataire.
            template_id: ID du template SendGrid.
            dynamic_data: Donnees pour le template.

        Returns:
            EmailResult avec statut d'envoi.
        """
        if not self._enabled:
            return EmailResult(
                success=False,
                error="Email service disabled"
            )

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To

            message = Mail(
                from_email=Email(self._from_email, self._from_name),
                to_emails=To(to),
            )
            message.template_id = template_id
            message.dynamic_template_data = dynamic_data

            client = SendGridAPIClient(self._api_key)
            response = client.send(message)

            logger.info(
                "email_template_sent",
                to=to,
                template_id=template_id,
                status_code=response.status_code,
            )

            return EmailResult(
                success=True,
                message_id=response.headers.get("X-Message-Id"),
            )

        except Exception as e:
            logger.error(
                "email_template_failed",
                to=to,
                template_id=template_id,
                error=str(e),
            )
            return EmailResult(success=False, error=str(e))

    @property
    def is_enabled(self) -> bool:
        """Retourne True si le service est configure."""
        return self._enabled
