"""
EmailTemplate - Templates d'emails.

Responsabilite unique:
----------------------
Definir les templates HTML pour les emails transactionnels.

Usage:
------
    template = EmailTemplate.welcome(username="John")
    service.send(to="john@example.com", **template)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailContent:
    """
    Contenu d'un email.

    Attributes:
        subject: Sujet de l'email.
        html: Corps HTML.
        text: Corps texte (fallback).
    """

    subject: str
    html: str
    text: str


class EmailTemplate:
    """
    Factory pour les templates d'emails.

    Chaque methode retourne un EmailContent pret a envoyer.
    """

    # Base HTML template
    _BASE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
            .button {{ display: inline-block; background: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Meta Ads Analyzer</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>© 2024 Meta Ads Analyzer. Tous droits reserves.</p>
        </div>
    </body>
    </html>
    """

    @classmethod
    def welcome(cls, username: str) -> EmailContent:
        """
        Email de bienvenue.

        Args:
            username: Nom de l'utilisateur.

        Returns:
            EmailContent pret a envoyer.
        """
        html_content = f"""
        <h2>Bienvenue {username}!</h2>
        <p>Votre compte Meta Ads Analyzer a ete cree avec succes.</p>
        <p>Vous pouvez maintenant:</p>
        <ul>
            <li>Rechercher des publicites Meta</li>
            <li>Analyser les sites Shopify</li>
            <li>Detecter les winning ads</li>
        </ul>
        <a href="#" class="button">Acceder au dashboard</a>
        """

        return EmailContent(
            subject="Bienvenue sur Meta Ads Analyzer",
            html=cls._BASE_HTML.format(content=html_content),
            text=f"Bienvenue {username}! Votre compte a ete cree.",
        )

    @classmethod
    def password_reset(cls, username: str, reset_url: str) -> EmailContent:
        """
        Email de reset mot de passe.

        Args:
            username: Nom de l'utilisateur.
            reset_url: URL de reset.

        Returns:
            EmailContent pret a envoyer.
        """
        html_content = f"""
        <h2>Reset de mot de passe</h2>
        <p>Bonjour {username},</p>
        <p>Vous avez demande un reset de mot de passe.</p>
        <p>Cliquez sur le bouton ci-dessous pour definir un nouveau mot de passe:</p>
        <a href="{reset_url}" class="button">Reinitialiser le mot de passe</a>
        <p><small>Ce lien expire dans 1 heure.</small></p>
        <p>Si vous n'avez pas fait cette demande, ignorez cet email.</p>
        """

        return EmailContent(
            subject="Reset de mot de passe - Meta Ads Analyzer",
            html=cls._BASE_HTML.format(content=html_content),
            text=f"Bonjour {username}, cliquez ici pour reset: {reset_url}",
        )

    @classmethod
    def subscription_confirmed(
        cls,
        username: str,
        plan: str,
        amount: str
    ) -> EmailContent:
        """
        Email de confirmation d'abonnement.

        Args:
            username: Nom de l'utilisateur.
            plan: Nom du plan (starter, pro, enterprise).
            amount: Montant facture.

        Returns:
            EmailContent pret a envoyer.
        """
        html_content = f"""
        <h2>Abonnement confirme!</h2>
        <p>Bonjour {username},</p>
        <p>Votre abonnement <strong>{plan.upper()}</strong> est maintenant actif.</p>
        <table style="width: 100%; margin: 20px 0;">
            <tr>
                <td>Plan:</td>
                <td><strong>{plan.upper()}</strong></td>
            </tr>
            <tr>
                <td>Montant:</td>
                <td><strong>{amount}</strong>/mois</td>
            </tr>
        </table>
        <p>Merci pour votre confiance!</p>
        <a href="#" class="button">Acceder au dashboard</a>
        """

        return EmailContent(
            subject=f"Abonnement {plan.upper()} confirme",
            html=cls._BASE_HTML.format(content=html_content),
            text=f"Bonjour {username}, votre abonnement {plan} est actif.",
        )

    @classmethod
    def scan_completed(
        cls,
        username: str,
        site_count: int,
        winning_count: int
    ) -> EmailContent:
        """
        Email de notification de scan termine.

        Args:
            username: Nom de l'utilisateur.
            site_count: Nombre de sites scannes.
            winning_count: Nombre de winning ads detectees.

        Returns:
            EmailContent pret a envoyer.
        """
        html_content = f"""
        <h2>Scan termine!</h2>
        <p>Bonjour {username},</p>
        <p>Votre scan est termine. Voici les resultats:</p>
        <table style="width: 100%; margin: 20px 0; border-collapse: collapse;">
            <tr style="background: #e5e7eb;">
                <td style="padding: 10px;">Sites analyses:</td>
                <td style="padding: 10px;"><strong>{site_count}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px;">Winning ads detectees:</td>
                <td style="padding: 10px;"><strong>{winning_count}</strong></td>
            </tr>
        </table>
        <a href="#" class="button">Voir les resultats</a>
        """

        return EmailContent(
            subject=f"Scan termine - {winning_count} winning ads detectees",
            html=cls._BASE_HTML.format(content=html_content),
            text=f"Scan termine: {site_count} sites, {winning_count} winning ads.",
        )

    @classmethod
    def alert_rate_limit(cls, api_name: str, retry_after: int) -> EmailContent:
        """
        Alerte de rate limit atteint.

        Args:
            api_name: Nom de l'API limitee.
            retry_after: Secondes avant retry.

        Returns:
            EmailContent pret a envoyer.
        """
        html_content = f"""
        <h2>⚠️ Alerte Rate Limit</h2>
        <p>L'API <strong>{api_name}</strong> a atteint sa limite.</p>
        <p>Prochain essai dans: <strong>{retry_after} secondes</strong></p>
        <p>Actions recommandees:</p>
        <ul>
            <li>Verifier la configuration des tokens</li>
            <li>Ajuster les parametres de throttling</li>
            <li>Contacter le support si le probleme persiste</li>
        </ul>
        """

        return EmailContent(
            subject=f"⚠️ Rate Limit - {api_name}",
            html=cls._BASE_HTML.format(content=html_content),
            text=f"Rate limit atteint sur {api_name}. Retry dans {retry_after}s.",
        )
