"""
Interface du service de classification de sites.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from src.domain.value_objects import ThematiqueClassification


@dataclass
class SiteContent:
    """
    Contenu d'un site pour classification.

    Attributes:
        page_id: ID de la page.
        url: URL du site.
        title: Titre du site.
        description: Meta description.
        h1: Premier H1.
        keywords: Meta keywords.
    """

    page_id: str
    url: str
    title: str = ""
    description: str = ""
    h1: str = ""
    keywords: str = ""

    def has_content(self) -> bool:
        """Retourne True si du contenu est disponible."""
        return bool(self.title or self.description or self.h1 or self.keywords)

    def to_text(self, max_length: int = 2000) -> str:
        """Convertit en texte pour le prompt."""
        parts = []
        if self.title:
            parts.append(f"Titre: {self.title[:200]}")
        if self.description:
            parts.append(f"Description: {self.description[:400]}")
        if self.h1:
            parts.append(f"H1: {self.h1[:150]}")
        if self.keywords:
            parts.append(f"Keywords: {self.keywords[:200]}")
        return " | ".join(parts)[:max_length]


@dataclass
class ClassificationResult:
    """
    Resultat de classification d'un site.

    Attributes:
        page_id: ID de la page.
        classification: Classification thematique.
        error: Message d'erreur si echec.
    """

    page_id: str
    classification: ThematiqueClassification
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Retourne True si la classification a reussi."""
        return self.error is None

    @property
    def category(self) -> str:
        """Raccourci vers la categorie."""
        return self.classification.category

    @property
    def subcategory(self) -> str | None:
        """Raccourci vers la sous-categorie."""
        return self.classification.subcategory

    @property
    def confidence(self) -> float:
        """Raccourci vers la confiance."""
        return self.classification.confidence


@dataclass
class ClassificationBatchResult:
    """
    Resultat de classification en batch.

    Attributes:
        results: Resultats par page_id.
        total_classified: Nombre de sites classifies.
        errors_count: Nombre d'erreurs.
        high_confidence_count: Nombre avec confiance >= 0.7.
    """

    results: dict[str, ClassificationResult]
    total_classified: int = 0
    errors_count: int = 0
    high_confidence_count: int = 0

    def get(self, page_id: str) -> ClassificationResult | None:
        """Recupere un resultat par page_id."""
        return self.results.get(page_id)


# Type pour le callback de progression
ClassificationProgressCallback = Callable[[int, int, str], None]  # (current, total, message)


class ClassificationService(ABC):
    """
    Interface pour le service de classification de sites.

    Ce service encapsule la classification thematique
    des sites e-commerce via IA (Gemini).
    """

    @abstractmethod
    def classify(
        self,
        content: SiteContent,
    ) -> ClassificationResult:
        """
        Classifie un site unique.

        Args:
            content: Contenu du site.

        Returns:
            Resultat de classification.
        """
        pass

    @abstractmethod
    def classify_batch(
        self,
        contents: list[SiteContent],
        progress_callback: ClassificationProgressCallback | None = None,
    ) -> ClassificationBatchResult:
        """
        Classifie plusieurs sites en batch.

        Args:
            contents: Liste des contenus de sites.
            progress_callback: Callback de progression.

        Returns:
            Resultats de classification.
        """
        pass

    @abstractmethod
    def get_taxonomy(self) -> dict[str, list[str]]:
        """
        Retourne la taxonomie utilisee.

        Returns:
            Dictionnaire {categorie: [sous-categories]}.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifie si le service est disponible.

        Returns:
            True si operationnel (cle API configuree).
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, str]:
        """
        Retourne les informations sur le modele utilise.

        Returns:
            Dictionnaire avec infos sur le modele.
        """
        pass


# Import du type Callable pour l'annotation
from collections.abc import Callable
