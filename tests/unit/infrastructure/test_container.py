"""
Tests unitaires pour le Container d'injection de dependances.
"""

from unittest.mock import MagicMock

import pytest

from src.infrastructure.container import Container, get_container, reset_container


class TestContainer:
    """Tests pour Container."""

    def setup_method(self) -> None:
        """Reset le container avant chaque test."""
        reset_container()

    def test_create_without_dependencies(self) -> None:
        """Test creation sans dependances."""
        container = Container.create()

        assert container.page_repository is not None
        assert container.search_use_case is not None
        assert container.winning_ads_use_case is not None
        assert container.page_view_model is not None
        assert container.search_view_model is not None
        assert container.meta_adapter is None

    def test_create_with_db_manager(self) -> None:
        """Test creation avec db_manager."""
        mock_db = MagicMock()
        mock_db.Session.return_value = MagicMock()

        container = Container.create(db_manager=mock_db)

        assert container.page_repository is not None
        assert container.page_repository._db == mock_db

    def test_create_with_db_manager_no_session(self) -> None:
        """Test creation avec db_manager sans Session."""
        mock_db = MagicMock(spec=[])  # Pas de Session

        container = Container.create(db_manager=mock_db)

        assert container.page_repository is not None

    def test_create_with_db_manager_session_exception(self) -> None:
        """Test creation avec db_manager qui leve une exception."""
        mock_db = MagicMock()
        mock_db.Session.side_effect = Exception("DB error")

        container = Container.create(db_manager=mock_db)

        assert container.page_repository is not None

    def test_create_with_meta_client(self) -> None:
        """Test creation avec meta_client."""
        mock_meta = MagicMock()

        container = Container.create(meta_client=mock_meta)

        assert container.meta_adapter is not None

    def test_create_with_winning_ads_repository(self) -> None:
        """Test creation avec winning_ads_repository."""
        mock_repo = MagicMock()

        container = Container.create(winning_ads_repository=mock_repo)

        assert container.winning_ads_use_case is not None
        assert container.winning_ad_repository == mock_repo

    def test_page_view_model_uses_repository(self) -> None:
        """Test que le PageViewModel utilise le repository."""
        mock_db = MagicMock()
        container = Container.create(db_manager=mock_db)

        # Le view model doit utiliser le meme repository
        assert container.page_view_model._page_repo == container.page_repository


class TestGetContainer:
    """Tests pour get_container."""

    def setup_method(self) -> None:
        """Reset le container avant chaque test."""
        reset_container()

    def test_get_container_creates_singleton(self) -> None:
        """Test que get_container retourne un singleton."""
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_get_container_with_db_manager(self) -> None:
        """Test get_container avec db_manager."""
        mock_db = MagicMock()

        container = get_container(db_manager=mock_db)

        assert container is not None
        assert container.page_repository._db == mock_db

    def test_get_container_ignores_db_after_creation(self) -> None:
        """Test que db_manager est ignore si le container existe."""
        mock_db1 = MagicMock()
        mock_db2 = MagicMock()

        container1 = get_container(db_manager=mock_db1)
        container2 = get_container(db_manager=mock_db2)

        # Le second db_manager doit etre ignore
        assert container1 is container2
        assert container2.page_repository._db == mock_db1


class TestResetContainer:
    """Tests pour reset_container."""

    def test_reset_container_clears_singleton(self) -> None:
        """Test que reset_container efface le singleton."""
        container1 = get_container()
        reset_container()
        container2 = get_container()

        assert container1 is not container2

    def test_reset_allows_new_db_manager(self) -> None:
        """Test que reset permet un nouveau db_manager."""
        mock_db1 = MagicMock()
        mock_db2 = MagicMock()

        get_container(db_manager=mock_db1)
        reset_container()
        container = get_container(db_manager=mock_db2)

        assert container.page_repository._db == mock_db2
