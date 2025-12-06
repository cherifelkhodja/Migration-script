"""
Entite Ad - Annonce publicitaire Meta.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Dict, Any

from src.domain.value_objects import AdId, PageId, Reach, Currency


@dataclass
class Ad:
    """
    Annonce publicitaire Meta Ads.

    Represente une annonce de l'archive Meta Ads Library
    avec toutes ses metadonnees.

    Attributes:
        id: Identifiant unique de l'annonce.
        page_id: ID de la page Facebook associee.
        page_name: Nom de la page.
        creation_date: Date de creation de l'annonce.
        reach: Portee estimee de l'annonce.
        bodies: Textes du corps de l'annonce.
        link_titles: Titres des liens.
        link_captions: Captions des liens (souvent le domaine).
        snapshot_url: URL de l'apercu de l'annonce.
        currency: Devise de l'annonce.
        languages: Langues ciblees.
        platforms: Plateformes de diffusion.
        target_ages: Tranches d'age ciblees.
        target_gender: Genre cible.

    Example:
        >>> ad = Ad(
        ...     id=AdId("987654321"),
        ...     page_id=PageId("123456789"),
        ...     page_name="Ma Boutique",
        ...     creation_date=date.today(),
        ...     reach=Reach(50000)
        ... )
        >>> ad.age_days
        0
    """

    id: AdId
    page_id: PageId
    page_name: str = ""
    creation_date: Optional[date] = None
    reach: Reach = field(default_factory=Reach.zero)
    bodies: List[str] = field(default_factory=list)
    link_titles: List[str] = field(default_factory=list)
    link_captions: List[str] = field(default_factory=list)
    snapshot_url: str = ""
    currency: Optional[Currency] = None
    languages: List[str] = field(default_factory=list)
    platforms: List[str] = field(default_factory=list)
    target_ages: str = ""
    target_gender: str = ""

    # Champs internes
    _keyword: Optional[str] = field(default=None, repr=False)
    _raw_data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @classmethod
    def from_meta_response(cls, data: Dict[str, Any]) -> "Ad":
        """
        Cree une Ad depuis une reponse de l'API Meta.

        Args:
            data: Dictionnaire de la reponse API.

        Returns:
            Instance de Ad.
        """
        # Parser la date de creation
        creation_date = None
        creation_str = data.get("ad_creation_time")
        if creation_str:
            try:
                if isinstance(creation_str, str):
                    # Format: "2024-01-15T10:30:00+0000"
                    dt = datetime.fromisoformat(
                        creation_str.replace("+0000", "+00:00")
                    )
                    creation_date = dt.date()
                elif isinstance(creation_str, datetime):
                    creation_date = creation_str.date()
            except (ValueError, AttributeError):
                pass

        # Parser le reach
        reach = Reach.from_meta_response(data.get("eu_total_reach"))

        # Parser les listes
        def to_list(val: Any) -> List[str]:
            if val is None:
                return []
            if isinstance(val, list):
                return [str(v) for v in val if v]
            return [str(val)] if val else []

        return cls(
            id=AdId.from_any(data.get("id", "")),
            page_id=PageId.from_any(data.get("page_id", "")),
            page_name=str(data.get("page_name", "")).strip(),
            creation_date=creation_date,
            reach=reach,
            bodies=to_list(data.get("ad_creative_bodies")),
            link_titles=to_list(data.get("ad_creative_link_titles")),
            link_captions=to_list(data.get("ad_creative_link_captions")),
            snapshot_url=str(data.get("ad_snapshot_url", "")),
            currency=Currency.from_string(str(data.get("currency", ""))),
            languages=to_list(data.get("languages")),
            platforms=to_list(data.get("publisher_platforms")),
            target_ages=str(data.get("target_ages", "")),
            target_gender=str(data.get("target_gender", "")),
            _raw_data=data,
        )

    @property
    def age_days(self) -> int:
        """
        Retourne l'age de l'annonce en jours.

        Returns:
            Nombre de jours depuis la creation, ou -1 si inconnu.
        """
        if not self.creation_date:
            return -1
        today = date.today()
        return (today - self.creation_date).days

    @property
    def is_recent(self) -> bool:
        """Retourne True si l'annonce a moins de 7 jours."""
        age = self.age_days
        return 0 <= age <= 7

    @property
    def is_very_recent(self) -> bool:
        """Retourne True si l'annonce a moins de 3 jours."""
        age = self.age_days
        return 0 <= age <= 3

    @property
    def primary_body(self) -> str:
        """Retourne le texte principal de l'annonce."""
        return self.bodies[0] if self.bodies else ""

    @property
    def primary_title(self) -> str:
        """Retourne le titre principal du lien."""
        return self.link_titles[0] if self.link_titles else ""

    @property
    def primary_caption(self) -> str:
        """Retourne la caption principale (souvent le domaine)."""
        return self.link_captions[0] if self.link_captions else ""

    @property
    def extracted_domain(self) -> Optional[str]:
        """
        Essaie d'extraire le domaine depuis les captions.

        Returns:
            Domaine extrait ou None.
        """
        for caption in self.link_captions:
            caption = caption.lower().strip()
            # Verifier si c'est un domaine valide
            if "." in caption and " " not in caption:
                # Nettoyer
                domain = caption.replace("www.", "").strip("/")
                if len(domain) > 4 and len(domain) < 60:
                    return domain
        return None

    def set_keyword(self, keyword: str) -> None:
        """Definit le mot-cle qui a trouve cette annonce."""
        self._keyword = keyword

    def __eq__(self, other: object) -> bool:
        """Compare deux annonces par leur ID."""
        if isinstance(other, Ad):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash base sur l'ID."""
        return hash(self.id)

    def __str__(self) -> str:
        """Representation string."""
        return f"Ad({self.id}) - {self.page_name}"

    def __repr__(self) -> str:
        """Representation debug."""
        return (
            f"Ad(id={self.id}, page={self.page_id}, "
            f"reach={self.reach}, age={self.age_days}d)"
        )
