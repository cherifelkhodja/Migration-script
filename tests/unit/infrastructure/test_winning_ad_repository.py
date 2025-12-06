"""
Tests unitaires pour SQLAlchemyWinningAdRepository.

Note: Ces tests sont simplifies car le repository delegue
au DatabaseManager existant. Les tests verifient le comportement
sans db_manager (cas de fallback).
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.domain.value_objects import AdId, PageId
from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
    SQLAlchemyWinningAdRepository,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock de la session SQLAlchemy."""
    return MagicMock()


@pytest.fixture
def mock_db_manager() -> MagicMock:
    """Mock du DatabaseManager."""
    return MagicMock()


@pytest.fixture
def repository(
    mock_session: MagicMock, mock_db_manager: MagicMock
) -> SQLAlchemyWinningAdRepository:
    """Repository avec mocks."""
    return SQLAlchemyWinningAdRepository(mock_session, mock_db_manager)


class TestNoDatabaseManager:
    """Tests sans db_manager - verifie les fallbacks."""

    def test_get_by_ad_id_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne None."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.get_by_ad_id(AdId("1234567890"))
        assert result is None

    def test_exists_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne False."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.exists(AdId("1234567890"))
        assert result is False

    def test_find_all_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.find_all()
        assert result == []

    def test_find_by_page_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.find_by_page(PageId("123456789"))
        assert result == []

    def test_find_by_criteria_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.find_by_criteria("4d/15k")
        assert result == []

    def test_find_recent_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.find_recent(days=7)
        assert result == []

    def test_find_by_search_log_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.find_by_search_log(search_log_id=123)
        assert result == []

    def test_count_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne 0."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.count()
        assert result == 0

    def test_get_statistics_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne dict vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.get_statistics()
        assert result == {}

    def test_get_criteria_distribution_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne dict vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.get_criteria_distribution()
        assert result == {}

    def test_get_daily_counts_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne dict vide."""
        repo = SQLAlchemyWinningAdRepository(mock_session, db_manager=None)
        result = repo.get_daily_counts()
        assert result == {}


class TestNotImplemented:
    """Tests pour methodes non implementees."""

    def test_delete_not_implemented(
        self, repository: SQLAlchemyWinningAdRepository
    ) -> None:
        """Test suppression non implementee."""
        result = repository.delete(AdId("1234567890"))
        assert result is False

    def test_delete_older_than_not_implemented(
        self, repository: SQLAlchemyWinningAdRepository
    ) -> None:
        """Test suppression ancienne non implementee."""
        result = repository.delete_older_than(days=30)
        assert result == 0

    def test_save_many_empty(self, repository: SQLAlchemyWinningAdRepository) -> None:
        """Test save_many avec liste vide."""
        saved, skipped = repository.save_many([])
        assert saved == 0
        assert skipped == 0
