"""
Value Objects pour la thematique et la classification des sites.
"""

from dataclasses import dataclass

from src.domain.exceptions import InvalidThematiqueError

# Taxonomie par defaut des categories e-commerce
DEFAULT_TAXONOMY: dict[str, list[str]] = {
    "Mode & Accessoires": [
        "Bijoux", "Montres", "Maillots de bain", "Sacs a main", "Lunettes",
        "Chaussures", "Vetements homme", "Vetements femme", "Vetements sport"
    ],
    "Beaute & Soins": [
        "Serums", "Cremes", "Brosses nettoyantes", "Huiles essentielles",
        "Outils de massage"
    ],
    "Sante & Bien-etre": [
        "Ceintures de posture", "Pistolets de massage", "Patchs antidouleur",
        "Accessoires de relaxation", "Appareils de fitness"
    ],
    "Maison & Decoration": [
        "Luminaires", "Organisateurs", "Tableaux decoratifs",
        "Plantes artificielles", "Accessoires de rangement"
    ],
    "Animaux": [
        "Colliers", "Harnais", "Jouets", "Gamelles automatiques",
        "Produits d'hygiene"
    ],
    "High-Tech & Gadgets": [
        "Chargeurs sans fil", "Ecouteurs Bluetooth", "Montres connectees",
        "Cameras", "Mini projecteurs", "Gadgets"
    ],
    "Bebe & Enfant": [
        "Jouets educatifs", "Veilleuses", "Tapis d'eveil", "Bavoirs",
        "Articles de securite enfant"
    ],
    "Sport & Loisirs": [
        "Accessoires de yoga", "Elastiques de musculation",
        "Bouteilles isothermes", "Sacs de sport", "Gants de fitness"
    ],
    "Cuisine & Alimentation": [
        "Ustensiles", "Robots de cuisine", "Rangements alimentaires",
        "Accessoires de patisserie", "Gadgets de decoupe"
    ],
    "Divers & Specialise": [
        "Generaliste", "Autre"
    ],
}


@dataclass(frozen=True, slots=True)
class Thematique:
    """
    Thematique/categorie d'un site e-commerce.

    Represente la classification thematique d'un site
    selon une taxonomie hierarchique (categorie/sous-categorie).

    Attributes:
        category: Categorie principale.
        subcategory: Sous-categorie (optionnel).

    Example:
        >>> theme = Thematique("Mode & Accessoires", "Bijoux")
        >>> theme.category
        'Mode & Accessoires'
    """

    category: str
    subcategory: str | None = None

    def __post_init__(self) -> None:
        """Valide la thematique apres initialisation."""
        if not self.category or not self.category.strip():
            raise InvalidThematiqueError("", self.subcategory)

    @classmethod
    def from_classification(
        cls,
        category: str,
        subcategory: str | None = None,
        taxonomy: dict[str, list[str]] | None = None
    ) -> "Thematique":
        """
        Cree une Thematique avec validation contre la taxonomie.

        Args:
            category: Categorie principale.
            subcategory: Sous-categorie.
            taxonomy: Taxonomie de reference (optionnel).

        Returns:
            Thematique valide.

        Raises:
            InvalidThematiqueError: Si la categorie n'existe pas.
        """
        taxonomy = taxonomy or DEFAULT_TAXONOMY

        # Normaliser la categorie
        category = category.strip() if category else ""

        # Verifier si la categorie existe
        if category not in taxonomy:
            # Chercher une correspondance approximative
            for cat in taxonomy:
                if cat.lower() == category.lower():
                    category = cat
                    break
            else:
                # Utiliser "Divers & Specialise" par defaut
                category = "Divers & Specialise"
                subcategory = "Autre"

        # Normaliser la sous-categorie
        if subcategory:
            subcategory = subcategory.strip()
            valid_subs = taxonomy.get(category, [])
            if subcategory not in valid_subs:
                # Chercher une correspondance approximative
                for sub in valid_subs:
                    if sub.lower() == subcategory.lower():
                        subcategory = sub
                        break
                else:
                    subcategory = None

        return cls(category=category, subcategory=subcategory)

    @classmethod
    def unknown(cls) -> "Thematique":
        """Factory pour creer une thematique inconnue."""
        return cls(category="Divers & Specialise", subcategory="Generaliste")

    @property
    def is_unknown(self) -> bool:
        """Retourne True si la thematique est inconnue."""
        return (
            self.category == "Divers & Specialise" and
            self.subcategory in ("Generaliste", "Autre", None)
        )

    @property
    def full_path(self) -> str:
        """Retourne le chemin complet categorie/sous-categorie."""
        if self.subcategory:
            return f"{self.category} > {self.subcategory}"
        return self.category

    def __str__(self) -> str:
        """Retourne la representation string de la thematique."""
        return self.full_path

    def __repr__(self) -> str:
        """Retourne la representation debug de la thematique."""
        if self.subcategory:
            return f"Thematique('{self.category}', '{self.subcategory}')"
        return f"Thematique('{self.category}')"


@dataclass(frozen=True, slots=True)
class ThematiqueClassification:
    """
    Resultat de classification thematique avec score de confiance.

    Represente le resultat complet d'une classification,
    incluant la thematique detectee et la confiance.

    Attributes:
        thematique: Thematique classifiee.
        confidence: Score de confiance (0.0 a 1.0).
        source: Source de la classification (ex: "gemini", "rules").

    Example:
        >>> classification = ThematiqueClassification(
        ...     thematique=Thematique("Mode & Accessoires", "Bijoux"),
        ...     confidence=0.92,
        ...     source="gemini"
        ... )
        >>> classification.is_confident
        True
    """

    thematique: Thematique
    confidence: float
    source: str = "unknown"

    def __post_init__(self) -> None:
        """Valide la classification apres initialisation."""
        object.__setattr__(
            self,
            "confidence",
            max(0.0, min(1.0, self.confidence))
        )

    @classmethod
    def from_gemini(
        cls,
        category: str,
        subcategory: str | None,
        confidence: float
    ) -> "ThematiqueClassification":
        """
        Cree une classification depuis une reponse Gemini.

        Args:
            category: Categorie retournee par Gemini.
            subcategory: Sous-categorie retournee.
            confidence: Score de confiance.

        Returns:
            ThematiqueClassification valide.
        """
        thematique = Thematique.from_classification(category, subcategory)
        return cls(thematique=thematique, confidence=confidence, source="gemini")

    @classmethod
    def unknown(cls) -> "ThematiqueClassification":
        """Factory pour creer une classification inconnue."""
        return cls(
            thematique=Thematique.unknown(),
            confidence=0.0,
            source="default"
        )

    @property
    def is_confident(self) -> bool:
        """Retourne True si la classification est confiante (>= 0.7)."""
        return self.confidence >= 0.7

    @property
    def is_very_confident(self) -> bool:
        """Retourne True si la classification est tres confiante (>= 0.9)."""
        return self.confidence >= 0.9

    @property
    def category(self) -> str:
        """Raccourci vers la categorie."""
        return self.thematique.category

    @property
    def subcategory(self) -> str | None:
        """Raccourci vers la sous-categorie."""
        return self.thematique.subcategory

    def __str__(self) -> str:
        """Retourne la representation string."""
        return f"{self.thematique} ({self.confidence:.0%})"

    def __repr__(self) -> str:
        """Retourne la representation debug."""
        return (
            f"ThematiqueClassification("
            f"thematique={self.thematique!r}, "
            f"confidence={self.confidence:.2f}, "
            f"source='{self.source}')"
        )
