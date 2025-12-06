"""
Tests unitaires pour les Use Cases.
"""

from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from src.application.ports.services.ads_search_service import (
    SearchResult,
)
from src.application.use_cases.detect_winning_ads import (
    DetectWinningAdsRequest,
    DetectWinningAdsResponse,
    DetectWinningAdsUseCase,
)
from src.application.use_cases.search_ads import (
    PageWithAds,
    SearchAdsRequest,
    SearchAdsResponse,
    SearchAdsUseCase,
)
from src.domain.entities.ad import Ad
from src.domain.entities.page import Page
from src.domain.value_objects import AdId, PageId, Reach

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_ads() -> list[Ad]:
    """Fixture avec une liste d'annonces."""
    return [
        Ad(
            id=AdId("111"),
            page_id=PageId("123"),
            page_name="Shop A",
            creation_date=date.today(),
            reach=Reach(50000),
        ),
        Ad(
            id=AdId("222"),
            page_id=PageId("123"),
            page_name="Shop A",
            creation_date=date.today(),
            reach=Reach(30000),
        ),
        Ad(
            id=AdId("333"),
            page_id=PageId("456"),
            page_name="Shop B",
            creation_date=date.today() - timedelta(days=10),
            reach=Reach(100000),
        ),
    ]


@pytest.fixture
def winning_ad() -> Ad:
    """Fixture pour une annonce winning."""
    return Ad(
        id=AdId("444"),
        page_id=PageId("789"),
        page_name="Winning Shop",
        creation_date=date.today() - timedelta(days=3),
        reach=Reach(20000),
    )


@pytest.fixture
def mock_ads_service(sample_ads):
    """Mock du service de recherche d'annonces."""
    service = Mock()
    service.search_by_keywords.return_value = SearchResult(
        ads=sample_ads,
        total_unique_ads=3,
        ads_by_keyword={"bijoux": 2, "montres": 1},
        pages_found=2,
    )
    return service


@pytest.fixture
def mock_page_repository():
    """Mock du repository de pages."""
    repo = Mock()
    repo.get_by_id.return_value = None
    repo.save.return_value = None
    return repo


@pytest.fixture
def mock_winning_ad_repository():
    """Mock du repository de winning ads."""
    repo = Mock()
    repo.save_many.return_value = (3, 0)  # (saved, skipped)
    repo.exists.return_value = False
    return repo


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - SearchAdsUseCase
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchAdsUseCase:
    """Tests pour le use case SearchAds."""

    def test_execute_basic_search(self, mock_ads_service, sample_ads):
        """Test recherche basique."""
        use_case = SearchAdsUseCase(
            ads_service=mock_ads_service,
        )

        request = SearchAdsRequest(
            keywords=["bijoux"],
            countries=["FR"],
        )

        response = use_case.execute(request)

        assert isinstance(response, SearchAdsResponse)
        assert response.total_ads_found == 3
        assert response.unique_ads_count == 3
        mock_ads_service.search_by_keywords.assert_called_once()

    def test_execute_groups_ads_by_page(self, mock_ads_service, sample_ads):
        """Test que les annonces sont regroupees par page."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(keywords=["bijoux"])

        response = use_case.execute(request)

        # 2 pages distinctes (123 et 456)
        assert response.pages_count == 2

        # Trouver la page "Shop A" qui a 2 annonces
        shop_a = next(p for p in response.pages if p.page.name == "Shop A")
        assert shop_a.ads_count == 2

    def test_execute_applies_min_ads_filter(self, mock_ads_service, sample_ads):
        """Test le filtre min_ads."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(
            keywords=["bijoux"],
            min_ads=2,  # Seulement pages avec 2+ annonces
        )

        response = use_case.execute(request)

        # Seule Shop A a 2 annonces, Shop B n'en a qu'une
        assert response.pages_count == 1
        assert response.pages[0].page.name == "Shop A"
        assert response.pages_before_filter == 2
        assert response.pages_after_filter == 1

    def test_execute_excludes_blacklisted_pages(self, mock_ads_service, sample_ads):
        """Test l'exclusion des pages blacklistees."""
        blacklist = {"123"}  # Exclure Shop A
        use_case = SearchAdsUseCase(
            ads_service=mock_ads_service,
            blacklist=blacklist,
        )
        request = SearchAdsRequest(keywords=["bijoux"])

        response = use_case.execute(request)

        # Shop A est exclue, reste seulement Shop B
        assert response.pages_count == 1
        assert response.pages[0].page.name == "Shop B"

    def test_execute_includes_blacklisted_when_disabled(
        self, mock_ads_service, sample_ads
    ):
        """Test inclusion des blacklistees quand desactive."""
        blacklist = {"123"}
        use_case = SearchAdsUseCase(
            ads_service=mock_ads_service,
            blacklist=blacklist,
        )
        request = SearchAdsRequest(
            keywords=["bijoux"],
            exclude_blacklisted=False,  # Ne pas exclure
        )

        response = use_case.execute(request)

        # Les deux pages sont presentes
        assert response.pages_count == 2

    def test_execute_tracks_keywords(self, mock_ads_service):
        """Test le suivi des mots-cles par page."""
        # Creer des annonces avec des mots-cles
        ads = [
            Ad(
                id=AdId("111"),
                page_id=PageId("123"),
                page_name="Shop A",
                reach=Reach(1000),
                _keyword="bijoux",
            ),
            Ad(
                id=AdId("222"),
                page_id=PageId("123"),
                page_name="Shop A",
                reach=Reach(1000),
                _keyword="montres",
            ),
        ]
        mock_ads_service.search_by_keywords.return_value = SearchResult(
            ads=ads,
            total_unique_ads=2,
            ads_by_keyword={"bijoux": 1, "montres": 1},
            pages_found=1,
        )

        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(keywords=["bijoux", "montres"])

        response = use_case.execute(request)

        page = response.pages[0]
        assert "bijoux" in page.keywords_found
        assert "montres" in page.keywords_found

    def test_execute_with_progress_callback(self, mock_ads_service, sample_ads):
        """Test avec callback de progression."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(keywords=["bijoux"])

        progress_calls = []

        def on_progress(message, current, total):
            progress_calls.append((message, current, total))

        use_case.execute(request, progress_callback=on_progress)

        # Verifier que le callback a ete passe au service
        mock_ads_service.search_by_keywords.assert_called_once()
        call_kwargs = mock_ads_service.search_by_keywords.call_args[1]
        assert call_kwargs.get("progress_callback") is not None

    def test_set_blacklist(self, mock_ads_service):
        """Test modification de la blacklist."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        use_case.set_blacklist({"123", "456"})

        assert "123" in use_case._blacklist
        assert "456" in use_case._blacklist

    def test_add_to_blacklist(self, mock_ads_service):
        """Test ajout a la blacklist."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        use_case.add_to_blacklist("789")

        assert "789" in use_case._blacklist

    def test_execute_calculates_duration(self, mock_ads_service, sample_ads):
        """Test que la duree est calculee."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(keywords=["bijoux"])

        response = use_case.execute(request)

        assert response.search_duration_ms >= 0

    def test_execute_returns_keyword_stats(self, mock_ads_service, sample_ads):
        """Test les statistiques par mot-cle."""
        use_case = SearchAdsUseCase(ads_service=mock_ads_service)
        request = SearchAdsRequest(keywords=["bijoux", "montres"])

        response = use_case.execute(request)

        assert "bijoux" in response.keywords_stats
        assert response.keywords_stats["bijoux"] == 2


class TestSearchAdsRequest:
    """Tests pour SearchAdsRequest."""

    def test_default_values(self):
        """Test valeurs par defaut."""
        request = SearchAdsRequest(keywords=["test"])

        assert request.countries == ["FR"]
        assert request.languages == ["fr"]
        assert request.min_ads == 1
        assert request.cms_filter == []
        assert request.exclude_blacklisted is True


class TestPageWithAds:
    """Tests pour PageWithAds."""

    def test_ads_count_property(self):
        """Test propriete ads_count."""
        page = Page.create("123", "Test")
        ads = [
            Ad(id=AdId("1"), page_id=PageId("123"), reach=Reach(0)),
            Ad(id=AdId("2"), page_id=PageId("123"), reach=Reach(0)),
        ]
        page_with_ads = PageWithAds(page=page, ads=ads)

        assert page_with_ads.ads_count == 2


class TestSearchAdsResponse:
    """Tests pour SearchAdsResponse."""

    def test_pages_count_property(self):
        """Test propriete pages_count."""
        page = Page.create("123", "Test")
        pages = [PageWithAds(page=page, ads=[])]
        response = SearchAdsResponse(
            pages=pages,
            total_ads_found=0,
            unique_ads_count=0,
            pages_before_filter=1,
            pages_after_filter=1,
            search_duration_ms=100,
            keywords_stats={},
        )

        assert response.pages_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - DetectWinningAdsUseCase
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectWinningAdsUseCase:
    """Tests pour le use case DetectWinningAds."""

    def test_execute_detects_winning_ads(self, winning_ad):
        """Test detection basique."""
        use_case = DetectWinningAdsUseCase()

        ads = [winning_ad]
        request = DetectWinningAdsRequest(ads=ads)

        response = use_case.execute(request)

        assert response.count == 1
        assert response.total_analyzed == 1
        assert response.detection_rate > 0

    def test_execute_with_no_winning_ads(self):
        """Test quand aucune annonce n'est winning."""
        use_case = DetectWinningAdsUseCase()

        ads = [
            Ad(
                id=AdId("1"),
                page_id=PageId("123"),
                creation_date=date.today() - timedelta(days=30),
                reach=Reach(100),  # Reach trop faible
            )
        ]
        request = DetectWinningAdsRequest(ads=ads)

        response = use_case.execute(request)

        assert response.count == 0
        assert response.detection_rate == 0.0

    def test_execute_saves_to_repository(
        self, mock_winning_ad_repository, winning_ad
    ):
        """Test sauvegarde dans le repository."""
        use_case = DetectWinningAdsUseCase(
            winning_ad_repository=mock_winning_ad_repository
        )

        request = DetectWinningAdsRequest(ads=[winning_ad])
        response = use_case.execute(request)

        mock_winning_ad_repository.save_many.assert_called_once()
        assert response.saved_count == 3  # Retour du mock

    def test_execute_with_custom_criteria(self):
        """Test avec criteres personnalises."""
        custom_criteria = [(1, 1000)]  # Tres facile a atteindre
        use_case = DetectWinningAdsUseCase()

        ad = Ad(
            id=AdId("1"),
            page_id=PageId("123"),
            creation_date=date.today(),
            reach=Reach(1000),
        )
        request = DetectWinningAdsRequest(
            ads=[ad],
            custom_criteria=custom_criteria,
        )

        response = use_case.execute(request)

        assert response.count == 1

    def test_execute_with_search_log_id(self, winning_ad):
        """Test avec search_log_id."""
        use_case = DetectWinningAdsUseCase()

        request = DetectWinningAdsRequest(
            ads=[winning_ad],
            search_log_id=42,
        )

        response = use_case.execute(request)

        # Le search_log_id est transmis aux winning ads
        assert response.count >= 1

    def test_is_winning_quick_check(self, winning_ad):
        """Test verification rapide."""
        use_case = DetectWinningAdsUseCase()

        result = use_case.is_winning(winning_ad)

        assert result is True

    def test_is_winning_returns_false(self):
        """Test verification rapide - non winning."""
        use_case = DetectWinningAdsUseCase()

        ad = Ad(
            id=AdId("1"),
            page_id=PageId("123"),
            creation_date=date.today() - timedelta(days=100),
            reach=Reach(100),
        )

        result = use_case.is_winning(ad)

        assert result is False

    def test_explain_winning_ad(self, winning_ad):
        """Test explication pour winning ad."""
        use_case = DetectWinningAdsUseCase()

        explanation = use_case.explain(winning_ad)

        assert "WINNING" in explanation or "gagnante" in explanation.lower()

    def test_explain_non_winning_ad(self):
        """Test explication pour non-winning ad."""
        use_case = DetectWinningAdsUseCase()

        ad = Ad(
            id=AdId("1"),
            page_id=PageId("123"),
            creation_date=date.today() - timedelta(days=100),
            reach=Reach(100),
        )

        explanation = use_case.explain(ad)

        assert len(explanation) > 0

    def test_get_criteria(self):
        """Test recuperation des criteres."""
        custom_criteria = [(5, 25000), (10, 50000)]
        use_case = DetectWinningAdsUseCase(criteria=custom_criteria)

        criteria = use_case.get_criteria()

        assert criteria == custom_criteria
        # Verifier que c'est une copie
        criteria.append((15, 75000))
        assert len(use_case.get_criteria()) == 2

    def test_response_count_property(self, winning_ad):
        """Test propriete count de la reponse."""
        use_case = DetectWinningAdsUseCase()
        request = DetectWinningAdsRequest(ads=[winning_ad])

        response = use_case.execute(request)

        assert response.count == len(response.winning_ads)


class TestDetectWinningAdsRequest:
    """Tests pour DetectWinningAdsRequest."""

    def test_default_values(self):
        """Test valeurs par defaut."""
        request = DetectWinningAdsRequest(ads=[])

        assert request.search_log_id is None
        assert request.custom_criteria is None


class TestDetectWinningAdsResponse:
    """Tests pour DetectWinningAdsResponse."""

    def test_count_property(self):
        """Test propriete count."""
        response = DetectWinningAdsResponse(
            winning_ads=[],
            total_analyzed=10,
            detection_rate=0.0,
            criteria_distribution={},
        )

        assert response.count == 0
