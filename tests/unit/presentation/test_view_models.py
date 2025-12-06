"""
Tests unitaires pour les View Models.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.application.ports.repositories.page_repository import PageRepository
from src.application.ports.services.ads_search_service import (
    AdsSearchService,
    PageAdsResult,
    SearchParameters,
    SearchResult,
)
from src.domain.entities.ad import Ad
from src.domain.entities.page import Page
from src.domain.value_objects import CMS, Etat, PageId, ThematiqueClassification
from src.presentation.view_models.page_view_model import (
    PageDetailItem,
    PageViewModel,
    ScanResult,
)
from src.presentation.view_models.search_view_model import (
    SearchResultItem,
    SearchStats,
    SearchViewModel,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_page() -> Page:
    """Page de test."""
    return Page.create(
        page_id="123456789",
        name="Test Shop",
        website="https://test-shop.com",
        cms="shopify",
        active_ads_count=50,
        product_count=100,
    )


@pytest.fixture
def sample_page_with_classification() -> Page:
    """Page avec classification."""
    page = Page.create(
        page_id="987654321",
        name="Fashion Store",
        website="https://fashion.com",
        cms="shopify",
        active_ads_count=100,
        product_count=500,
    )
    page.update_classification(
        category="Mode & Accessoires",
        subcategory="Bijoux",
        confidence=0.85,
    )
    page.keywords.add("mode")
    page.keywords.add("fashion")
    return page


@pytest.fixture
def mock_page_repository() -> MagicMock:
    """Mock du PageRepository."""
    return MagicMock(spec=PageRepository)


@pytest.fixture
def mock_ads_service() -> MagicMock:
    """Mock du AdsSearchService."""
    return MagicMock(spec=AdsSearchService)


# ============================================================
# Tests PageDetailItem
# ============================================================


class TestPageDetailItem:
    """Tests pour PageDetailItem."""

    def test_from_page_basic(self, sample_page: Page) -> None:
        """Test creation depuis une Page basique."""
        detail = PageDetailItem.from_page(sample_page)

        assert detail.page_id == "123456789"
        assert detail.page_name == "Test Shop"
        assert detail.website == "https://test-shop.com"
        assert detail.cms == "Shopify"
        assert detail.ads_count == 50
        assert detail.product_count == 100
        assert detail.is_shopify is True
        assert "facebook.com" in detail.facebook_url

    def test_from_page_with_classification(
        self, sample_page_with_classification: Page
    ) -> None:
        """Test creation avec classification."""
        detail = PageDetailItem.from_page(sample_page_with_classification)

        assert detail.category == "Mode & Accessoires"
        assert detail.subcategory == "Bijoux"
        assert detail.confidence == 0.85
        assert "mode" in detail.keywords
        assert "fashion" in detail.keywords

    def test_from_page_without_website(self) -> None:
        """Test creation sans website."""
        page = Page.create(
            page_id="111",
            name="No Website",
            active_ads_count=10,
        )
        detail = PageDetailItem.from_page(page)

        assert detail.website == ""
        assert detail.domain == ""

    def test_to_dict(self, sample_page: Page) -> None:
        """Test conversion en dictionnaire."""
        detail = PageDetailItem.from_page(sample_page)
        data = detail.to_dict()

        assert isinstance(data, dict)
        assert data["page_id"] == "123456789"
        assert data["page_name"] == "Test Shop"
        assert data["cms"] == "Shopify"


# ============================================================
# Tests PageViewModel
# ============================================================


class TestPageViewModel:
    """Tests pour PageViewModel."""

    def test_get_page_detail_found(
        self, mock_page_repository: MagicMock, sample_page: Page
    ) -> None:
        """Test recuperation page existante."""
        mock_page_repository.get_by_id.return_value = sample_page

        vm = PageViewModel(page_repository=mock_page_repository)
        detail = vm.get_page_detail("123456789")

        assert detail is not None
        assert detail.page_id == "123456789"
        assert vm.current_page == sample_page

    def test_get_page_detail_not_found(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test page non trouvee."""
        mock_page_repository.get_by_id.return_value = None

        vm = PageViewModel(page_repository=mock_page_repository)
        detail = vm.get_page_detail("nonexistent")

        assert detail is None

    def test_get_page_detail_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test gestion exception."""
        mock_page_repository.get_by_id.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        detail = vm.get_page_detail("123")

        assert detail is None

    def test_get_pages_by_etat(
        self, mock_page_repository: MagicMock, sample_page: Page
    ) -> None:
        """Test recuperation par etat."""
        mock_page_repository.find_by_etat.return_value = [sample_page]

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_etat("L")

        assert len(pages) == 1
        assert pages[0].page_id == "123456789"

    def test_get_pages_by_cms(
        self, mock_page_repository: MagicMock, sample_page: Page
    ) -> None:
        """Test recuperation par CMS."""
        mock_page_repository.find_by_cms.return_value = [sample_page]

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_cms("shopify")

        assert len(pages) == 1
        assert pages[0].is_shopify is True

    def test_get_pages_by_category(
        self, mock_page_repository: MagicMock,
        sample_page_with_classification: Page,
    ) -> None:
        """Test recuperation par categorie."""
        mock_page_repository.find_by_category.return_value = [
            sample_page_with_classification
        ]

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_category("Mode & Accessoires")

        assert len(pages) == 1
        assert pages[0].category == "Mode & Accessoires"

    def test_get_statistics(self, mock_page_repository: MagicMock) -> None:
        """Test recuperation statistiques."""
        mock_page_repository.count.return_value = 100
        mock_page_repository.get_etat_distribution.return_value = {"L": 50, "XL": 30}
        mock_page_repository.get_cms_distribution.return_value = {"Shopify": 80}

        vm = PageViewModel(page_repository=mock_page_repository)
        stats = vm.get_statistics()

        assert stats["total_pages"] == 100
        assert stats["by_etat"]["L"] == 50
        assert stats["by_cms"]["Shopify"] == 80

    def test_update_classification(
        self, mock_page_repository: MagicMock, sample_page: Page
    ) -> None:
        """Test mise a jour classification."""
        mock_page_repository.get_by_id.return_value = sample_page
        mock_page_repository.save.return_value = sample_page

        vm = PageViewModel(page_repository=mock_page_repository)
        result = vm.update_classification(
            page_id="123456789",
            category="Bijoux",
            subcategory="Colliers",
            confidence=0.9,
        )

        assert result is True
        mock_page_repository.save.assert_called_once()

    def test_update_classification_not_found(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test mise a jour page inexistante."""
        mock_page_repository.get_by_id.return_value = None

        vm = PageViewModel(page_repository=mock_page_repository)
        result = vm.update_classification(
            page_id="nonexistent",
            category="Test",
        )

        assert result is False

    def test_scan_website_no_analyzer(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test scan sans analyzer."""
        vm = PageViewModel(
            page_repository=mock_page_repository,
            analyzer_service=None,
        )
        result = vm.scan_website("123")

        assert result.success is False
        assert "non disponible" in result.error_message

    def test_get_pages_needing_scan(
        self, mock_page_repository: MagicMock, sample_page: Page
    ) -> None:
        """Test pages a scanner."""
        mock_page_repository.find_needing_scan.return_value = [sample_page]

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_needing_scan(limit=10)

        assert len(pages) == 1

    def test_get_pages_by_etat_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test exception dans get_pages_by_etat."""
        mock_page_repository.find_by_etat.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_etat("L")

        assert pages == []

    def test_get_pages_by_cms_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test exception dans get_pages_by_cms."""
        mock_page_repository.find_by_cms.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_cms("shopify")

        assert pages == []

    def test_get_pages_by_category_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test exception dans get_pages_by_category."""
        mock_page_repository.find_by_category.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_by_category("Mode")

        assert pages == []

    def test_get_statistics_exception(self, mock_page_repository: MagicMock) -> None:
        """Test exception dans get_statistics."""
        mock_page_repository.count.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        stats = vm.get_statistics()

        assert stats["total_pages"] == 0
        assert stats["by_etat"] == {}
        assert stats["by_cms"] == {}

    def test_update_classification_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test exception dans update_classification."""
        mock_page_repository.get_by_id.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        result = vm.update_classification(page_id="123", category="Test")

        assert result is False

    def test_get_pages_needing_scan_exception(
        self, mock_page_repository: MagicMock
    ) -> None:
        """Test exception dans get_pages_needing_scan."""
        mock_page_repository.find_needing_scan.side_effect = RuntimeError("DB error")

        vm = PageViewModel(page_repository=mock_page_repository)
        pages = vm.get_pages_needing_scan(limit=10)

        assert pages == []

    def test_set_page_ads(self, mock_page_repository: MagicMock) -> None:
        """Test set_page_ads et current_ads."""
        vm = PageViewModel(page_repository=mock_page_repository)

        # Creer des ads mock
        mock_ad1 = MagicMock(spec=Ad)
        mock_ad2 = MagicMock(spec=Ad)

        vm.set_page_ads([mock_ad1, mock_ad2])

        assert len(vm.current_ads) == 2
        assert vm.current_ads[0] == mock_ad1
        assert vm.current_ads[1] == mock_ad2


# ============================================================
# Tests SearchResultItem
# ============================================================


class TestSearchResultItem:
    """Tests pour SearchResultItem."""

    def test_to_dict(self) -> None:
        """Test conversion en dictionnaire."""
        item = SearchResultItem(
            page_id="123",
            page_name="Test",
            ads_count=50,
            etat="L",
            website="https://test.com",
            cms="Shopify",
            winning_count=5,
            keywords=["test", "demo"],
        )
        data = item.to_dict()

        assert data["page_id"] == "123"
        assert data["ads_count"] == 50
        assert data["keywords"] == "test, demo"

    def test_to_dict_empty_values(self) -> None:
        """Test avec valeurs vides."""
        item = SearchResultItem(
            page_id="123",
            page_name="Test",
            ads_count=10,
            etat="S",
        )
        data = item.to_dict()

        assert data["website"] == ""
        assert data["cms"] == "Unknown"
        assert data["keywords"] == ""


# ============================================================
# Tests SearchStats
# ============================================================


class TestSearchStats:
    """Tests pour SearchStats."""

    def test_winning_rate_calculation(self) -> None:
        """Test calcul du taux de winning."""
        stats = SearchStats(
            total_pages=10,
            total_ads=100,
            unique_ads=80,
            winning_ads=20,
            duration_ms=5000,
        )

        assert stats.winning_rate == 20.0

    def test_winning_rate_zero_ads(self) -> None:
        """Test taux avec zero annonces."""
        stats = SearchStats(
            total_pages=0,
            total_ads=0,
            unique_ads=0,
            winning_ads=0,
            duration_ms=100,
        )

        assert stats.winning_rate == 0.0


# ============================================================
# Tests SearchViewModel
# ============================================================


class TestSearchViewModel:
    """Tests pour SearchViewModel."""

    def test_initialization(self, mock_ads_service: MagicMock) -> None:
        """Test initialisation."""
        vm = SearchViewModel(
            ads_service=mock_ads_service,
            blacklist={"blocked_page"},
        )

        assert vm.stats is None
        assert vm.winning_ads == []

    def test_search_empty_results(self, mock_ads_service: MagicMock) -> None:
        """Test recherche sans resultats."""
        mock_ads_service.search_by_keywords.return_value = SearchResult(
            ads=[],
            ads_by_keyword={},
            total_unique_ads=0,
            pages_found=0,
        )

        vm = SearchViewModel(ads_service=mock_ads_service)
        results = vm.search(
            keywords=["test"],
            countries=["FR"],
        )

        assert len(results) == 0

    def test_get_page_ads_no_results(self, mock_ads_service: MagicMock) -> None:
        """Test get_page_ads sans recherche prealable."""
        vm = SearchViewModel(ads_service=mock_ads_service)
        ads = vm.get_page_ads("123")

        assert ads == []

    def test_to_dataframe_data_empty(self, mock_ads_service: MagicMock) -> None:
        """Test to_dataframe_data sans resultats."""
        vm = SearchViewModel(ads_service=mock_ads_service)
        data = vm.to_dataframe_data()

        assert data == []

    def test_set_blacklist(self, mock_ads_service: MagicMock) -> None:
        """Test mise a jour blacklist."""
        vm = SearchViewModel(ads_service=mock_ads_service)
        vm.set_blacklist({"page1", "page2"})

        # Verifie que ca ne leve pas d'exception
        assert True

    def test_add_to_blacklist(self, mock_ads_service: MagicMock) -> None:
        """Test ajout a la blacklist."""
        vm = SearchViewModel(ads_service=mock_ads_service)
        vm.add_to_blacklist("page1")

        # Verifie que ca ne leve pas d'exception
        assert True


# ============================================================
# Tests ScanResult
# ============================================================


class TestScanResult:
    """Tests pour ScanResult."""

    def test_success_result(self) -> None:
        """Test resultat succes."""
        result = ScanResult(
            success=True,
            cms_detected="Shopify",
            product_count=100,
            currency="EUR",
            duration_ms=2500,
        )

        assert result.success is True
        assert result.cms_detected == "Shopify"
        assert result.error_message == ""

    def test_failure_result(self) -> None:
        """Test resultat echec."""
        result = ScanResult(
            success=False,
            error_message="Connection timeout",
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"
