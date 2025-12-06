"""
Tests d'integration pour SQLAlchemyPageRepository.
"""

from unittest.mock import MagicMock

import pytest

from src.domain.entities.page import Page
from src.domain.value_objects import PageId
from src.infrastructure.persistence.sqlalchemy_page_repository import (
    SQLAlchemyPageRepository,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock de la session SQLAlchemy."""
    return MagicMock()


@pytest.fixture
def mock_db_manager() -> MagicMock:
    """Mock du DatabaseManager."""
    return MagicMock()


@pytest.fixture
def repository(mock_session: MagicMock, mock_db_manager: MagicMock) -> SQLAlchemyPageRepository:
    """Repository avec mocks."""
    return SQLAlchemyPageRepository(mock_session, mock_db_manager)


@pytest.fixture
def sample_page_row() -> dict:
    """Ligne de base de donnees."""
    return {
        "page_id": "123456789",
        "page_name": "Test Shop",
        "website": "https://test-shop.com",
        "nb_ads_active": 50,
        "etat": "L",
        "cms": "Shopify",
        "nb_products": 100,
        "category": "Mode & Accessoires",
        "sub_category": "Bijoux",
        "confidence": 0.85,
        "keywords": ["bijoux", "mode"],
        "last_scan": None,
    }


# ============================================================
# Tests get_by_id
# ============================================================


class TestGetById:
    """Tests pour get_by_id."""

    def test_get_by_id_found(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation page existante."""
        mock_db_manager.get_page.return_value = sample_page_row

        page_id = PageId("123456789")
        page = repository.get_by_id(page_id)

        assert page is not None
        assert str(page.id) == "123456789"
        assert page.name == "Test Shop"

    def test_get_by_id_not_found(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test page non trouvee."""
        mock_db_manager.get_page.return_value = None

        page_id = PageId("123456789")
        page = repository.get_by_id(page_id)

        assert page is None

    def test_get_by_id_exception(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test gestion exception."""
        mock_db_manager.get_page.side_effect = Exception("DB error")

        page_id = PageId("123456789")
        page = repository.get_by_id(page_id)

        assert page is None

    def test_get_by_id_no_db_manager(self, mock_session: MagicMock) -> None:
        """Test sans db_manager."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)

        page_id = PageId("123456789")
        page = repo.get_by_id(page_id)

        assert page is None


# ============================================================
# Tests save
# ============================================================


class TestSave:
    """Tests pour save."""

    def test_save_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde reussie."""
        page = Page.create(
            page_id="123456789",
            name="Test Shop",
            website="https://test.com",
            cms="shopify",
            active_ads_count=50,
        )

        result = repository.save(page)

        assert result == page
        mock_db_manager.upsert_page.assert_called_once()

    def test_save_with_classification(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde avec classification."""
        page = Page.create(
            page_id="123456789",
            name="Test Shop",
        )
        page.update_classification(
            category="Mode & Accessoires",
            subcategory="Bijoux",
            confidence=0.9,
        )

        repository.save(page)

        call_kwargs = mock_db_manager.upsert_page.call_args[1]
        assert call_kwargs["category"] == "Mode & Accessoires"

    def test_save_exception(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test sauvegarde avec exception."""
        mock_db_manager.upsert_page.side_effect = Exception("DB error")

        page = Page.create(page_id="123456789", name="Test")
        result = repository.save(page)

        assert result == page

    def test_save_no_db_manager(self, mock_session: MagicMock) -> None:
        """Test sans db_manager."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)
        page = Page.create(page_id="123456789", name="Test")

        result = repo.save(page)

        assert result == page


# ============================================================
# Tests delete
# ============================================================


class TestDelete:
    """Tests pour delete."""

    def test_delete_returns_false(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test suppression non implementee."""
        page_id = PageId("123456789")
        result = repository.delete(page_id)

        assert result is False


# ============================================================
# Tests find_all
# ============================================================


class TestFindAll:
    """Tests pour find_all."""

    def test_find_all_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation toutes les pages."""
        mock_db_manager.get_all_pages.return_value = [sample_page_row]

        pages = repository.find_all(limit=10, offset=0)

        assert len(pages) == 1
        mock_db_manager.get_all_pages.assert_called_once()

    def test_find_all_empty(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test sans resultats."""
        mock_db_manager.get_all_pages.return_value = []

        pages = repository.find_all()

        assert len(pages) == 0

    def test_find_all_exception(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test avec exception."""
        mock_db_manager.get_all_pages.side_effect = Exception("DB error")

        pages = repository.find_all()

        assert len(pages) == 0

    def test_find_all_no_db_manager(self, mock_session: MagicMock) -> None:
        """Test sans db_manager."""
        repo = SQLAlchemyPageRepository(mock_session, db_manager=None)

        pages = repo.find_all()

        assert len(pages) == 0


# ============================================================
# Tests find_by_etat
# ============================================================


class TestFindByEtat:
    """Tests pour find_by_etat."""

    def test_find_by_etat_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation par etat."""
        mock_db_manager.get_pages_by_etat.return_value = [sample_page_row]

        pages = repository.find_by_etat(["L"])

        assert len(pages) == 1
        mock_db_manager.get_pages_by_etat.assert_called_once_with("L")

    def test_find_by_etat_empty_list(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test avec liste vide."""
        pages = repository.find_by_etat([])

        assert len(pages) == 0


# ============================================================
# Tests find_by_cms
# ============================================================


class TestFindByCms:
    """Tests pour find_by_cms."""

    def test_find_by_cms_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation par CMS."""
        mock_db_manager.get_pages_by_cms.return_value = [sample_page_row]

        pages = repository.find_by_cms(["Shopify"])

        assert len(pages) == 1

    def test_find_by_cms_empty_list(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test avec liste vide."""
        pages = repository.find_by_cms([])

        assert len(pages) == 0


# ============================================================
# Tests find_by_category
# ============================================================


class TestFindByCategory:
    """Tests pour find_by_category."""

    def test_find_by_category_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation par categorie."""
        mock_db_manager.get_pages_by_category.return_value = [sample_page_row]

        pages = repository.find_by_category("Mode & Accessoires")

        assert len(pages) == 1


# ============================================================
# Tests find_needing_scan
# ============================================================


class TestFindNeedingScan:
    """Tests pour find_needing_scan."""

    def test_find_needing_scan_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test recuperation pages a scanner."""
        mock_db_manager.get_pages_needing_scan.return_value = [sample_page_row]

        pages = repository.find_needing_scan(limit=50)

        assert len(pages) == 1


# ============================================================
# Tests count
# ============================================================


class TestCount:
    """Tests pour count."""

    def test_count_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test comptage."""
        mock_db_manager.count_pages.return_value = 100

        count = repository.count()

        assert count == 100

    def test_count_exception(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test comptage avec exception."""
        mock_db_manager.count_pages.side_effect = Exception("DB error")

        count = repository.count()

        assert count == 0


# ============================================================
# Tests count_by_etat / count_by_cms
# ============================================================


class TestCountDistributions:
    """Tests pour count_by_etat et count_by_cms."""

    def test_count_by_etat_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test distribution par etat."""
        mock_db_manager.count_pages_by_etat.return_value = {"L": 50, "XL": 30}

        distribution = repository.count_by_etat()

        assert distribution["L"] == 50

    def test_count_by_cms_success(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test distribution par CMS."""
        mock_db_manager.count_pages_by_cms.return_value = {"Shopify": 80}

        distribution = repository.count_by_cms()

        assert distribution["Shopify"] == 80


# ============================================================
# Tests methodes supplementaires
# ============================================================


class TestAdditionalMethods:
    """Tests pour methodes supplementaires."""

    def test_exists_true(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test exists retourne True."""
        mock_db_manager.get_page.return_value = sample_page_row

        result = repository.exists(PageId("123456789"))

        assert result is True

    def test_exists_false(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test exists retourne False."""
        mock_db_manager.get_page.return_value = None

        result = repository.exists(PageId("123456789"))

        assert result is False

    def test_get_by_ids(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock,
        sample_page_row: dict
    ) -> None:
        """Test get_by_ids."""
        mock_db_manager.get_page.return_value = sample_page_row

        pages = repository.get_by_ids([PageId("123456789")])

        assert len(pages) == 1

    def test_save_many(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test save_many."""
        pages = [
            Page.create(page_id="123456789", name="Test1"),
            Page.create(page_id="987654321", name="Test2"),
        ]

        saved = repository.save_many(pages)

        assert saved == 2

    def test_get_statistics(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test get_statistics."""
        mock_db_manager.count_pages.return_value = 100
        mock_db_manager.count_pages_by_etat.return_value = {"L": 50}
        mock_db_manager.count_pages_by_cms.return_value = {"Shopify": 80}

        stats = repository.get_statistics()

        assert stats["total"] == 100

    def test_get_etat_distribution(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test get_etat_distribution."""
        mock_db_manager.count_pages_by_etat.return_value = {"L": 50}

        dist = repository.get_etat_distribution()

        assert dist["L"] == 50

    def test_get_cms_distribution(
        self, repository: SQLAlchemyPageRepository,
        mock_db_manager: MagicMock
    ) -> None:
        """Test get_cms_distribution."""
        mock_db_manager.count_pages_by_cms.return_value = {"Shopify": 80}

        dist = repository.get_cms_distribution()

        assert dist["Shopify"] == 80


# ============================================================
# Tests _row_to_page
# ============================================================


class TestRowToPage:
    """Tests pour _row_to_page."""

    def test_row_to_page_dict(
        self, repository: SQLAlchemyPageRepository,
        sample_page_row: dict
    ) -> None:
        """Test conversion depuis dict."""
        page = repository._row_to_page(sample_page_row)

        assert str(page.id) == "123456789"
        assert page.name == "Test Shop"
        assert page.active_ads_count == 50
        assert page.cms.is_shopify

    def test_row_to_page_object(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test conversion depuis objet avec attributs."""
        row = MagicMock()
        row.page_id = "123456789"
        row.page_name = "Test Shop"
        row.website = "https://test.com"
        row.nb_ads_active = 25
        row.etat = "M"
        row.cms = "WooCommerce"
        row.nb_products = 50
        row.category = None
        row.sub_category = None
        row.confidence = None
        row.keywords = []
        row.last_scan = None

        page = repository._row_to_page(row)

        assert str(page.id) == "123456789"
        assert page.active_ads_count == 25
        assert page.cms.is_woocommerce

    def test_row_to_page_minimal(
        self, repository: SQLAlchemyPageRepository
    ) -> None:
        """Test conversion avec donnees minimales."""
        row = {
            "page_id": "123456789",
            "page_name": "Test",
        }

        page = repository._row_to_page(row)

        assert str(page.id) == "123456789"
        assert page.name == "Test"
