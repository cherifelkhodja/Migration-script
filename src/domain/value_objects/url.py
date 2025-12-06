"""
Value Object pour les URLs.
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse
import re

from src.domain.exceptions import InvalidUrlError


# Pattern pour valider les domaines
DOMAIN_PATTERN = re.compile(
    r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$',
    re.IGNORECASE
)

# Domaines a exclure (reseaux sociaux, raccourcisseurs, etc.)
EXCLUDED_DOMAINS = frozenset({
    "facebook.com", "instagram.com", "fb.me", "fb.com", "fb.watch",
    "messenger.com", "whatsapp.com", "meta.com",
    "twitter.com", "x.com", "tiktok.com", "pinterest.com",
    "linkedin.com", "snapchat.com", "threads.net",
    "google.com", "google.fr", "youtube.com", "youtu.be", "goo.gl",
    "bit.ly", "t.co", "ow.ly", "tinyurl.com", "short.link",
    "rebrand.ly", "cutt.ly", "is.gd",
    "linktr.ee", "linkin.bio", "beacons.ai", "allmylinks.com",
    "shopify.com", "myshopify.com",
    "wixsite.com", "squarespace.com",
    "apple.com", "apps.apple.com", "play.google.com",
})


@dataclass(frozen=True, slots=True)
class Url:
    """
    URL d'un site web avec normalisation et validation.

    L'URL est automatiquement normalisee (scheme https, sans trailing slash).

    Attributes:
        value: URL complete normalisee.
        domain: Domaine extrait de l'URL.

    Example:
        >>> url = Url.from_string("example.com")
        >>> url.value
        'https://example.com'
        >>> url.domain
        'example.com'
    """

    value: str
    domain: str

    def __post_init__(self) -> None:
        """Valide l'URL apres initialisation."""
        if not self.value or not self.domain:
            raise InvalidUrlError(self.value, "URL ou domaine vide")

    @classmethod
    def from_string(cls, url: str, allow_excluded: bool = False) -> "Url":
        """
        Cree une URL depuis une chaine.

        Args:
            url: URL a parser (avec ou sans scheme).
            allow_excluded: Si True, autorise les domaines exclus.

        Returns:
            Url valide et normalisee.

        Raises:
            InvalidUrlError: Si l'URL est invalide ou exclue.

        Example:
            >>> Url.from_string("www.example.com")
            Url('https://example.com')
        """
        if not url or not url.strip():
            raise InvalidUrlError(url, "URL vide")

        url = url.strip()

        # Ajouter le scheme si absent
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Parser l'URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise InvalidUrlError(url, str(e))

        # Extraire et normaliser le domaine
        domain = parsed.netloc.lower()

        # Supprimer www.
        if domain.startswith("www."):
            domain = domain[4:]

        # Supprimer le port si present
        if ":" in domain:
            domain = domain.split(":")[0]

        # Valider le domaine
        if not domain:
            raise InvalidUrlError(url, "Domaine vide")

        if not DOMAIN_PATTERN.match(domain):
            raise InvalidUrlError(url, f"Format de domaine invalide: {domain}")

        # Verifier si le domaine est exclu
        if not allow_excluded:
            for excluded in EXCLUDED_DOMAINS:
                if domain == excluded or domain.endswith(f".{excluded}"):
                    raise InvalidUrlError(url, f"Domaine exclu: {excluded}")

        # Reconstruire l'URL normalisee
        normalized = urlunparse((
            "https",  # Toujours HTTPS
            domain,
            parsed.path.rstrip("/") or "/",
            "",  # params
            "",  # query
            ""   # fragment
        ))

        # Supprimer le "/" final si c'est juste le domaine
        if normalized.endswith("/") and parsed.path in ("", "/"):
            normalized = normalized[:-1]

        return cls(value=normalized, domain=domain)

    @classmethod
    def try_from_string(cls, url: str) -> Optional["Url"]:
        """
        Essaie de creer une URL, retourne None si invalide.

        Args:
            url: URL a parser.

        Returns:
            Url si valide, None sinon.
        """
        try:
            return cls.from_string(url)
        except InvalidUrlError:
            return None

    @property
    def is_shopify_hosted(self) -> bool:
        """Retourne True si le site est heberge sur Shopify."""
        return self.domain.endswith(".myshopify.com")

    @property
    def root(self) -> str:
        """Retourne l'URL racine (scheme + domain)."""
        return f"https://{self.domain}"

    def with_path(self, path: str) -> "Url":
        """
        Cree une nouvelle URL avec un chemin different.

        Args:
            path: Nouveau chemin a utiliser.

        Returns:
            Nouvelle Url avec le chemin.
        """
        if not path.startswith("/"):
            path = f"/{path}"
        new_value = f"https://{self.domain}{path}"
        return Url(value=new_value, domain=self.domain)

    def __str__(self) -> str:
        """Retourne l'URL complete."""
        return self.value

    def __repr__(self) -> str:
        """Retourne la representation debug."""
        return f"Url('{self.value}')"

    def __hash__(self) -> int:
        """Hash base sur le domaine pour deduplication."""
        return hash(self.domain)

    def __eq__(self, other: object) -> bool:
        """Compare par domaine (ignore le path)."""
        if isinstance(other, Url):
            return self.domain == other.domain
        if isinstance(other, str):
            try:
                other_url = Url.from_string(other)
                return self.domain == other_url.domain
            except InvalidUrlError:
                return False
        return False
