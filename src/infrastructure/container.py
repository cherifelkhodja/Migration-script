"""
Container d'injection de dependances.

Ce module fournit un conteneur qui initialise et connecte
tous les composants de l'architecture hexagonale.
"""

from dataclasses import dataclass
from typing import Any

from src.application.ports.repositories.page_repository import PageRepository
from src.application.ports.repositories.winning_ad_repository import WinningAdRepository
from src.application.use_cases.detect_winning_ads import DetectWinningAdsUseCase
from src.application.use_cases.search_ads import SearchAdsUseCase
from src.infrastructure.external_services.meta_ads_adapter import MetaAdsSearchAdapter
from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository
from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
    SQLAlchemyWinningAdRepository,
)
from src.presentation.view_models.page_view_model import PageViewModel
from src.presentation.view_models.search_view_model import SearchViewModel


@dataclass
class Container:
    """
    Conteneur d'injection de dependances.

    Initialise et expose tous les composants de l'architecture
    hexagonale pour une utilisation facile par le dashboard.

    Example:
        >>> from app.database import DatabaseManager
        >>> db = DatabaseManager()
        >>> container = Container.create(db)
        >>> results = container.search_use_case.execute(request)
    """

    # Repositories (required)
    page_repository: PageRepository

    # Use Cases (required)
    search_use_case: SearchAdsUseCase
    winning_ads_use_case: DetectWinningAdsUseCase

    # ViewModels (required)
    page_view_model: PageViewModel
    search_view_model: SearchViewModel

    # Optional repositories
    winning_ad_repository: WinningAdRepository | None = None

    # External Services (optional)
    meta_adapter: MetaAdsSearchAdapter | None = None

    @classmethod
    def create(
        cls,
        db_manager: Any = None,
        meta_client: Any = None,
        winning_ads_repository: Any = None,
    ) -> "Container":
        """
        Factory pour creer un conteneur avec toutes les dependances.

        Args:
            db_manager: Instance de DatabaseManager (app.database).
            meta_client: Client Meta API (optionnel, pour tests).
            winning_ads_repository: Repository des winning ads (optionnel).

        Returns:
            Container configure avec tous les composants.
        """
        # Creer la session SQLAlchemy depuis le db_manager
        session = None
        if db_manager:
            try:
                session = db_manager.Session() if hasattr(db_manager, 'Session') else None
            except Exception:
                session = None

        # Repositories
        page_repository = SQLAlchemyPageRepository(
            session=session,
            db_manager=db_manager
        )

        # Winning Ads Repository - creer si db_manager et pas fourni
        if winning_ads_repository is None and db_manager:
            winning_ads_repository = SQLAlchemyWinningAdRepository(
                session=session,
                db_manager=db_manager
            )

        # External Services - Meta Adapter
        meta_adapter = None
        if meta_client:
            meta_adapter = MetaAdsSearchAdapter(meta_client)

        # Use Cases
        search_use_case = SearchAdsUseCase(
            ads_service=meta_adapter,
            page_repository=page_repository
        )

        winning_ads_use_case = DetectWinningAdsUseCase(
            winning_ad_repository=winning_ads_repository
        )

        # ViewModels
        page_view_model = PageViewModel(page_repository=page_repository)
        search_view_model = SearchViewModel(
            ads_service=meta_adapter,
            winning_repository=winning_ads_repository,
        )

        return cls(
            page_repository=page_repository,
            winning_ad_repository=winning_ads_repository,
            search_use_case=search_use_case,
            winning_ads_use_case=winning_ads_use_case,
            page_view_model=page_view_model,
            search_view_model=search_view_model,
            meta_adapter=meta_adapter,
        )

    @classmethod
    def create_from_database_url(cls, database_url: str) -> "Container":
        """
        Cree un conteneur depuis une URL de base de donnees.

        Args:
            database_url: URL PostgreSQL.

        Returns:
            Container configure.
        """
        # Import tardif pour eviter les dependances circulaires
        try:
            from app.database import DatabaseManager
            db_manager = DatabaseManager(database_url)
            return cls.create(db_manager=db_manager)
        except Exception:
            # Fallback sans base de donnees
            return cls.create()


# Singleton global pour le dashboard
_container: Container | None = None


def get_container(db_manager: Any = None) -> Container:
    """
    Recupere ou cree le conteneur global.

    Args:
        db_manager: DatabaseManager (optionnel, utilise si pas de conteneur existant).

    Returns:
        Instance du conteneur.
    """
    global _container
    if _container is None:
        _container = Container.create(db_manager=db_manager)
    return _container


def reset_container() -> None:
    """Reset le conteneur global (utile pour les tests)."""
    global _container
    _container = None
