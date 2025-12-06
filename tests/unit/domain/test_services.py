"""
Tests unitaires pour les Services du domaine.
"""

from datetime import date, timedelta

import pytest

from src.domain.entities.ad import Ad
from src.domain.entities.page import Page
from src.domain.services.page_state_calculator import PageStateCalculator
from src.domain.services.winning_ad_detector import WinningAdDetector
from src.domain.value_objects import AdId, PageId, Reach
from src.domain.value_objects.etat import EtatLevel

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - WinningAdDetector
# ═══════════════════════════════════════════════════════════════════════════════

class TestWinningAdDetector:
    """Tests pour le service WinningAdDetector."""

    @pytest.fixture
    def detector(self):
        """Instance du detecteur."""
        return WinningAdDetector()

    @pytest.fixture
    def sample_ads(self):
        """Liste d'ads pour les tests."""
        ads = []
        # Winning ads
        ads.append(Ad(
            id=AdId("1"),
            page_id=PageId("100"),
            creation_date=date.today() - timedelta(days=2),
            reach=Reach(25000),
        ))
        ads.append(Ad(
            id=AdId("2"),
            page_id=PageId("100"),
            creation_date=date.today() - timedelta(days=5),
            reach=Reach(35000),
        ))
        # Non-winning ads
        ads.append(Ad(
            id=AdId("3"),
            page_id=PageId("101"),
            creation_date=date.today() - timedelta(days=30),
            reach=Reach(5000),
        ))
        ads.append(Ad(
            id=AdId("4"),
            page_id=PageId("101"),
            creation_date=date.today() - timedelta(days=5),
            reach=Reach(10000),
        ))
        return ads

    def test_detect_single_ad(self, detector):
        """Test detection d'une seule ad."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=3),
            reach=Reach(20000),
        )

        winning = detector.detect(ad)
        assert winning is not None
        assert winning.ad == ad

    def test_detect_non_winning(self, detector):
        """Test detection d'une ad non winning."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=50),
            reach=Reach(1000),
        )

        winning = detector.detect(ad)
        assert winning is None

    def test_detect_all(self, detector, sample_ads):
        """Test detection en batch."""
        result = detector.detect_all(sample_ads)

        assert result.total_ads_analyzed == 4
        assert result.count == 2  # 2 winning ads
        assert 0 < result.detection_rate < 1

    def test_detection_result_criteria_distribution(self, detector, sample_ads):
        """Test distribution par critere."""
        result = detector.detect_all(sample_ads)

        assert len(result.criteria_distribution) > 0
        total_by_criteria = sum(result.criteria_distribution.values())
        assert total_by_criteria == result.count

    def test_is_winning(self, detector):
        """Test methode is_winning."""
        ad_winning = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today(),
            reach=Reach(20000),
        )
        ad_not = Ad(
            id=AdId("2"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=100),
            reach=Reach(100),
        )

        assert detector.is_winning(ad_winning)
        assert not detector.is_winning(ad_not)

    def test_get_applicable_criteria(self, detector):
        """Test criteres applicables."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=3),
            reach=Reach(50000),
        )

        criteria = detector.get_applicable_criteria(ad)
        assert len(criteria) > 0
        # Avec 50k reach et 3 jours, plusieurs criteres devraient matcher

    def test_explain_winning(self, detector):
        """Test explication pour winning ad."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=2),
            reach=Reach(25000),
        )

        explanation = detector.explain(ad)
        assert "WINNING" in explanation

    def test_explain_not_winning(self, detector):
        """Test explication pour ad non winning."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=10),
            reach=Reach(10000),
        )

        explanation = detector.explain(ad)
        assert "NON WINNING" in explanation

    def test_custom_criteria(self):
        """Test avec criteres personnalises."""
        custom_criteria = [(5, 1000)]  # Critere tres permissif
        detector = WinningAdDetector(criteria=custom_criteria)

        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=4),
            reach=Reach(1500),
        )

        assert detector.is_winning(ad)

    def test_detect_iter(self, detector, sample_ads):
        """Test detection iterative."""
        winning_list = list(detector.detect_iter(iter(sample_ads)))
        assert len(winning_list) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - PageStateCalculator
# ═══════════════════════════════════════════════════════════════════════════════

class TestPageStateCalculator:
    """Tests pour le service PageStateCalculator."""

    @pytest.fixture
    def calculator(self):
        """Instance du calculateur."""
        return PageStateCalculator()

    @pytest.fixture
    def sample_pages(self):
        """Liste de pages pour les tests."""
        return [
            Page.create("1", "Page XS", active_ads_count=5),
            Page.create("2", "Page S", active_ads_count=15),
            Page.create("3", "Page M", active_ads_count=25),
            Page.create("4", "Page L", active_ads_count=50),
            Page.create("5", "Page XL", active_ads_count=100),
        ]

    @pytest.mark.parametrize("ads_count,expected_level", [
        (0, EtatLevel.XS),
        (9, EtatLevel.XS),
        (10, EtatLevel.S),
        (20, EtatLevel.M),
        (35, EtatLevel.L),
        (80, EtatLevel.XL),
        (150, EtatLevel.XXL),
    ])
    def test_calculate(self, calculator, ads_count, expected_level):
        """Test calcul de l'etat."""
        etat = calculator.calculate(ads_count)
        assert etat.level == expected_level

    def test_calculate_for_page(self, calculator):
        """Test calcul pour une page."""
        page = Page.create("1", "Test", active_ads_count=50)
        etat = calculator.calculate_for_page(page)
        assert etat.level == EtatLevel.L

    def test_get_statistics(self, calculator, sample_pages):
        """Test statistiques."""
        stats = calculator.get_statistics(sample_pages)

        assert stats.total_pages == 5
        assert stats.total_ads == 195  # 5+15+25+50+100
        assert stats.average_ads_per_page == 39.0

    def test_statistics_distribution(self, calculator, sample_pages):
        """Test distribution des statistiques."""
        stats = calculator.get_statistics(sample_pages)

        dist = stats.to_dict()
        assert "XS" in dist
        assert "L" in dist
        assert dist["XS"] == 1
        assert dist["L"] == 1

    def test_filter_by_state(self, calculator, sample_pages):
        """Test filtrage par etat."""
        large_pages = calculator.filter_by_state(
            sample_pages,
            [EtatLevel.L, EtatLevel.XL, EtatLevel.XXL]
        )
        assert len(large_pages) == 2  # L et XL

    def test_filter_minimum_state(self, calculator, sample_pages):
        """Test filtrage par etat minimum."""
        at_least_m = calculator.filter_minimum_state(sample_pages, EtatLevel.M)
        assert len(at_least_m) == 3  # M, L, XL

    def test_get_threshold(self, calculator):
        """Test recuperation des seuils."""
        assert calculator.get_threshold(EtatLevel.XS) == 1
        assert calculator.get_threshold(EtatLevel.M) == 20
        assert calculator.get_threshold(EtatLevel.XXL) == 150

    def test_get_threshold_range(self, calculator):
        """Test recuperation des plages."""
        min_s, max_s = calculator.get_threshold_range(EtatLevel.S)
        assert min_s == 10
        assert max_s == 19

        min_xxl, max_xxl = calculator.get_threshold_range(EtatLevel.XXL)
        assert min_xxl == 150
        assert max_xxl is None  # Pas de limite superieure

    def test_describe_thresholds(self, calculator):
        """Test description des seuils."""
        description = calculator.describe_thresholds()
        assert "XS" in description
        assert "XXL" in description
        assert "ads" in description

    def test_custom_thresholds(self):
        """Test avec seuils personnalises."""
        custom = {
            EtatLevel.XS: 1,
            EtatLevel.S: 5,
            EtatLevel.M: 10,
            EtatLevel.L: 20,
            EtatLevel.XL: 50,
            EtatLevel.XXL: 100,
        }
        calculator = PageStateCalculator(thresholds=custom)

        # Avec les seuils personnalises, 15 ads = M
        etat = calculator.calculate(15)
        assert etat.level == EtatLevel.M
