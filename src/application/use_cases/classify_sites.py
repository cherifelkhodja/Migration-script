"""
Use Case: Classification thematique des sites.
"""

from collections.abc import Callable
from dataclasses import dataclass

from src.application.ports.repositories.page_repository import PageRepository
from src.application.ports.services.classification_service import (
    ClassificationService,
    SiteContent,
)
from src.domain.entities.page import Page
from src.domain.value_objects import ThematiqueClassification


@dataclass
class ClassifySitesRequest:
    """
    Requete de classification de sites.

    Attributes:
        pages: Pages a classifier avec leur contenu.
        contents: Contenu des sites (alternatif aux pages).
        skip_if_classified: Passer si deja classifie.
    """

    pages: list[Page] | None = None
    contents: list[SiteContent] | None = None
    skip_if_classified: bool = True


@dataclass
class ClassifySitesResponse:
    """
    Reponse de la classification.

    Attributes:
        classifications: Classifications par page_id.
        total_classified: Nombre de sites classifies.
        high_confidence_count: Nombre avec confiance >= 0.7.
        error_count: Nombre d'erreurs.
        saved_count: Nombre de mises a jour en BDD.
    """

    classifications: dict[str, ThematiqueClassification]
    total_classified: int
    high_confidence_count: int
    error_count: int
    saved_count: int = 0

    def get_classification(self, page_id: str) -> ThematiqueClassification | None:
        """Recupere la classification d'une page."""
        return self.classifications.get(page_id)


ProgressCallback = Callable[[int, int, str], None]


class ClassifySitesUseCase:
    """
    Use Case: Classification thematique des sites.

    Ce use case orchestre la classification des sites e-commerce
    via IA (Gemini) et met a jour les pages en base.

    Example:
        >>> classifier = ClassifySitesUseCase(class_service, page_repo)
        >>> request = ClassifySitesRequest(pages=my_pages)
        >>> response = classifier.execute(request)
        >>> print(f"{response.total_classified} sites classifies")
    """

    def __init__(
        self,
        classification_service: ClassificationService,
        page_repository: PageRepository | None = None,
    ) -> None:
        """
        Initialise le use case.

        Args:
            classification_service: Service de classification.
            page_repository: Repository pour sauvegarder les resultats.
        """
        self._classifier = classification_service
        self._page_repository = page_repository

    def execute(
        self,
        request: ClassifySitesRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> ClassifySitesResponse:
        """
        Execute la classification des sites.

        Args:
            request: Requete avec les pages/contenus a classifier.
            progress_callback: Callback de progression.

        Returns:
            Reponse avec les classifications.
        """
        # Preparer les contenus
        contents: list[SiteContent] = []

        if request.contents:
            contents = request.contents
        elif request.pages:
            for page in request.pages:
                # Sauter si deja classifie
                if request.skip_if_classified and page.is_classified:
                    continue

                # Creer le contenu depuis la page
                # Note: necessite que les metadonnees soient deja extraites
                content = SiteContent(
                    page_id=str(page.id),
                    url=page.website.value if page.website else "",
                    title="",  # A remplir depuis l'analyse web
                    description="",
                    h1="",
                    keywords="",
                )
                contents.append(content)

        if not contents:
            return ClassifySitesResponse(
                classifications={},
                total_classified=0,
                high_confidence_count=0,
                error_count=0,
            )

        # Classifier en batch
        batch_result = self._classifier.classify_batch(
            contents,
            progress_callback=progress_callback,
        )

        # Convertir les resultats
        classifications: dict[str, ThematiqueClassification] = {}
        error_count = 0
        high_confidence_count = 0

        for page_id, result in batch_result.results.items():
            if result.is_success:
                classifications[page_id] = result.classification
                if result.classification.is_confident:
                    high_confidence_count += 1
            else:
                error_count += 1
                # Utiliser classification par defaut
                classifications[page_id] = ThematiqueClassification.unknown()

        # Sauvegarder si repository disponible
        saved_count = 0
        if self._page_repository:
            for page_id, classification in classifications.items():
                success = self._page_repository.update_classification(
                    page_id=page_id,
                    category=classification.category,
                    subcategory=classification.subcategory,
                    confidence=classification.confidence,
                )
                if success:
                    saved_count += 1

        return ClassifySitesResponse(
            classifications=classifications,
            total_classified=len(classifications),
            high_confidence_count=high_confidence_count,
            error_count=error_count,
            saved_count=saved_count,
        )

    def classify_single(
        self,
        content: SiteContent,
    ) -> ThematiqueClassification:
        """
        Classifie un seul site.

        Args:
            content: Contenu du site.

        Returns:
            Classification thematique.
        """
        result = self._classifier.classify(content)
        return result.classification

    def get_taxonomy(self) -> dict[str, list[str]]:
        """Retourne la taxonomie utilisee."""
        return self._classifier.get_taxonomy()
