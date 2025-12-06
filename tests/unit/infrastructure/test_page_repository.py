"""
Tests unitaires pour SQLAlchemyPageRepository.

Ces tests verifient le comportement du repository avec et sans db_manager.
"""

from unittest.mock import MagicMock

import pytest

from src.domain.entities.page import Page
from src.domain.value_objects import PageId
from src.infrastructure.persistence.sqlalchemy_page_repository import (
    SQLAlchemyPageRepository,
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
) -> SQLAlchemyPageRepository:
    """Repository avec mocks."""
    return SQLAlchemyPageRepository(mock_session, mock_db_manager)


class TestNoDatabaseManager:
    """Tests sans db_manager - verifie les fallbacks."""

    def test_get_by_id_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne None."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.get_by_id(PageId("123456789"))
        assert result is None

    def test_find_all_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_all()
        assert result == []

    def test_find_by_etat_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_by_etat(["L"])
        assert result == []

    def test_find_by_cms_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_by_cms(["shopify"])
        assert result == []

    def test_find_by_category_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_by_category("Mode")
        assert result == []

    def test_find_by_keyword_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_by_keyword("bijoux")
        assert result == []

    def test_find_needing_scan_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.find_needing_scan(limit=10)
        assert result == []

    def test_count_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne 0."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.count()
        assert result == 0

    def test_count_by_etat_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne dict vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.count_by_etat()
        assert result == {}

    def test_count_by_cms_no_db(self, mock_session: MagicMock) -> None:
        """Test sans db_manager retourne dict vide."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        result = repo.count_by_cms()
        assert result == {}


class TestWithDatabaseManager:
    """Tests avec db_manager mocke."""

    def test_get_by_id_found(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation page existante."""
        mock_db_manager.get_page.return_value = {
            "page_id": "123456789",
            "page_name": "Test Shop",
            "website": "https://test.com",
            "nb_ads_active": 50,
            "etat": "L",
            "cms": "shopify",
            "nb_products": 100,
        }

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_by_id(PageId("123456789"))

        assert result is not None
        assert str(result.id) == "123456789"
        assert result.name == "Test Shop"

    def test_get_by_id_not_found(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test page non trouvee."""
        mock_db_manager.get_page.return_value = None

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_by_id(PageId("999999999"))

        assert result is None

    def test_get_by_id_exception(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test exception lors de la recuperation."""
        mock_db_manager.get_page.side_effect = RuntimeError("DB error")

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_by_id(PageId("123456789"))

        assert result is None

    def test_find_all_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation toutes les pages."""
        mock_db_manager.get_all_pages.return_value = [
            {"page_id": "111111111", "page_name": "Shop 1"},
            {"page_id": "222222222", "page_name": "Shop 2"},
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_all(limit=10, offset=0)

        assert len(result) == 2

    def test_find_all_exception(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test exception dans find_all."""
        mock_db_manager.get_all_pages.side_effect = RuntimeError("DB error")

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_all()

        assert result == []

    def test_find_by_etat_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation par etat."""
        mock_db_manager.get_pages_by_etat.return_value = [
            {"page_id": "111111111", "page_name": "Shop 1", "etat": "L"},
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_etat(["L"])

        assert len(result) == 1

    def test_find_by_etat_empty_list(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test avec liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_etat([])

        assert result == []

    def test_find_by_cms_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation par CMS."""
        mock_db_manager.get_pages_by_cms.return_value = [
            {"page_id": "111111111", "page_name": "Shop 1", "cms": "shopify"},
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_cms(["shopify"])

        assert len(result) == 1

    def test_find_by_cms_empty_list(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test avec liste vide."""
        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_cms([])

        assert result == []

    def test_find_by_category_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation par categorie."""
        mock_db_manager.get_pages_by_category.return_value = [
            {"page_id": "111111111", "page_name": "Shop 1", "category": "Mode"},
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_category("Mode")

        assert len(result) == 1

    def test_find_by_keyword_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation par mot-cle."""
        mock_db_manager.get_pages_by_keyword.return_value = [
            {"page_id": "111111111", "page_name": "Shop Bijoux"},
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.find_by_keyword("bijoux")

        assert len(result) == 1

    def test_count_success(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test comptage."""
        mock_db_manager.count_pages.return_value = 100

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.count()

        assert result == 100

    def test_count_exception(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test exception dans count."""
        mock_db_manager.count_pages.side_effect = RuntimeError("DB error")

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.count()

        assert result == 0


class TestNotImplemented:
    """Tests pour methodes avec implementation simplifiee."""

    def test_delete_not_implemented(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test suppression non implementee."""
        result = repository.delete(PageId("123456789"))
        assert result is False

    def test_exists_uses_get_by_id(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test exists utilise get_by_id."""
        mock_db_manager.get_page.return_value = {
            "page_id": "123456789",
            "page_name": "Test",
        }

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.exists(PageId("123456789"))

        assert result is True

    def test_exists_not_found(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test exists retourne False si page non trouvee."""
        mock_db_manager.get_page.return_value = None

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.exists(PageId("999999999"))

        assert result is False

    def test_find_unclassified_returns_empty(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test find_unclassified retourne liste vide."""
        result = repository.find_unclassified(limit=10)
        assert result == []

    def test_search_returns_empty(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test search retourne liste vide."""
        result = repository.search("query")
        assert result == []

    def test_get_category_distribution_returns_empty(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test get_category_distribution retourne dict vide."""
        result = repository.get_category_distribution()
        assert result == {}


class TestSaveAndUpdate:
    """Tests pour save et update."""

    def test_save_page(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde page."""
        page = Page.create(
            page_id="123456789",
            name="Test Shop",
            website="https://test.com",
            active_ads_count=50,
        )

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.save(page)

        assert result == page
        mock_db_manager.upsert_page.assert_called_once()

    def test_save_page_exception(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde avec exception."""
        mock_db_manager.upsert_page.side_effect = RuntimeError("DB error")

        page = Page.create(
            page_id="123456789",
            name="Test Shop",
            active_ads_count=50,
        )

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.save(page)

        # Retourne la page meme en cas d'erreur
        assert result == page

    def test_update_calls_save(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test update appelle save."""
        page = Page.create(
            page_id="123456789",
            name="Test Shop",
            active_ads_count=50,
        )

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.update(page)

        assert result == page

    def test_save_many(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde multiple."""
        pages = [
            Page.create(page_id="111111111", name="Shop 1", active_ads_count=10),
            Page.create(page_id="222222222", name="Shop 2", active_ads_count=20),
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.save_many(pages)

        assert result == 2
        assert mock_db_manager.upsert_page.call_count == 2

    def test_get_by_ids(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation par liste d'IDs."""
        mock_db_manager.get_page.side_effect = [
            {"page_id": "111111111", "page_name": "Shop 1"},
            None,  # Second ID not found
        ]

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_by_ids([PageId("111111111"), PageId("222222222")])

        assert len(result) == 1

    def test_update_classification(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test mise a jour classification."""
        mock_db_manager.get_page.return_value = {
            "page_id": "123456789",
            "page_name": "Test Shop",
        }

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.update_classification(
            PageId("123456789"),
            category="Mode",
            subcategory="Bijoux",
            confidence=0.9,
        )

        assert result is True

    def test_update_classification_not_found(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test mise a jour classification page non trouvee."""
        mock_db_manager.get_page.return_value = None

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.update_classification(
            PageId("999999999"),
            category="Mode",
            subcategory=None,
            confidence=0.8,
        )

        assert result is False

    def test_update_scan_date(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test mise a jour date de scan."""
        mock_db_manager.get_page.return_value = {
            "page_id": "123456789",
            "page_name": "Test Shop",
        }

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        from datetime import datetime
        result = repo.update_scan_date(PageId("123456789"), datetime.now())

        assert result is True

    def test_update_scan_date_not_found(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test mise a jour date de scan page non trouvee."""
        mock_db_manager.get_page.return_value = None

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        from datetime import datetime
        result = repo.update_scan_date(PageId("999999999"), datetime.now())

        assert result is False


class TestGetStatistics:
    """Tests pour get_statistics et distributions."""

    def test_get_statistics(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test recuperation statistiques."""
        mock_db_manager.count_pages.return_value = 100
        mock_db_manager.count_pages_by_etat.return_value = {"L": 50, "XL": 30}
        mock_db_manager.count_pages_by_cms.return_value = {"Shopify": 80}

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_statistics()

        assert result["total"] == 100
        assert result["by_etat"]["L"] == 50
        assert result["by_cms"]["Shopify"] == 80

    def test_get_etat_distribution(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test distribution par etat."""
        mock_db_manager.count_pages_by_etat.return_value = {"L": 50, "XL": 30}

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_etat_distribution()

        assert result["L"] == 50
        assert result["XL"] == 30

    def test_get_cms_distribution(
        self, mock_session: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """Test distribution par CMS."""
        mock_db_manager.count_pages_by_cms.return_value = {"Shopify": 80, "WooCommerce": 20}

        repo = SQLAlchemyPageRepository(mock_session, mock_db_manager)
        result = repo.get_cms_distribution()

        assert result["Shopify"] == 80
        assert result["WooCommerce"] == 20
