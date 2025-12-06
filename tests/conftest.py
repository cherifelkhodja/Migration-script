"""
Configuration et fixtures pytest.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

# Ajouter le repertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.entities.ad import Ad
from src.domain.entities.collection import Collection
from src.domain.entities.page import Page
from src.domain.entities.winning_ad import WinningAd
from src.domain.value_objects import (
    CMS,
    AdId,
    Currency,
    PageId,
    Reach,
    Thematique,
    ThematiqueClassification,
    Url,
)

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES - VALUE OBJECTS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_page_id() -> PageId:
    """PageId valide pour les tests."""
    return PageId("123456789")


@pytest.fixture
def valid_ad_id() -> AdId:
    """AdId valide pour les tests."""
    return AdId("987654321")


@pytest.fixture
def sample_url() -> Url:
    """URL valide pour les tests."""
    return Url.from_string("https://example-shop.com")


@pytest.fixture
def sample_reach() -> Reach:
    """Reach pour les tests."""
    return Reach(value=50000, lower_bound=40000, upper_bound=60000)


@pytest.fixture
def sample_currency() -> Currency:
    """Currency pour les tests."""
    return Currency.euro()


@pytest.fixture
def shopify_cms() -> CMS:
    """CMS Shopify pour les tests."""
    return CMS.shopify(theme="Dawn", confidence=0.95)


@pytest.fixture
def sample_thematique() -> Thematique:
    """Thematique pour les tests."""
    return Thematique("Mode & Accessoires", "Bijoux")


@pytest.fixture
def sample_classification() -> ThematiqueClassification:
    """Classification pour les tests."""
    return ThematiqueClassification(
        thematique=Thematique("Mode & Accessoires", "Bijoux"),
        confidence=0.92,
        source="gemini"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES - ENTITIES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_page(valid_page_id: PageId, sample_url: Url, shopify_cms: CMS) -> Page:
    """Page complete pour les tests."""
    return Page(
        id=valid_page_id,
        name="Ma Boutique Test",
        website=sample_url,
        cms=shopify_cms,
        active_ads_count=50,
        product_count=150,
    )


@pytest.fixture
def sample_ad(valid_ad_id: AdId, valid_page_id: PageId, sample_reach: Reach) -> Ad:
    """Annonce complete pour les tests."""
    return Ad(
        id=valid_ad_id,
        page_id=valid_page_id,
        page_name="Ma Boutique Test",
        creation_date=date.today(),
        reach=sample_reach,
        bodies=["Decouvrez nos nouveaux bijoux!"],
        link_titles=["Bijoux de qualite"],
        link_captions=["example-shop.com"],
    )


@pytest.fixture
def winning_ad(sample_ad: Ad) -> WinningAd:
    """Winning ad pour les tests."""
    return WinningAd(
        ad=sample_ad,
        matched_criteria="4d/15k",
        reach_at_detection=sample_ad.reach.value,
    )


@pytest.fixture
def sample_collection(valid_page_id: PageId) -> Collection:
    """Collection pour les tests."""
    return Collection(
        id=1,
        name="Mes Favoris",
        description="Pages favorites a surveiller",
        page_ids={valid_page_id},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES - LISTS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def multiple_ads() -> list[Ad]:
    """Liste d'annonces pour les tests."""
    ads = []
    for i in range(10):
        ad = Ad(
            id=AdId(str(1000 + i)),
            page_id=PageId(str(100 + i % 3)),  # 3 pages differentes
            page_name=f"Page {100 + i % 3}",
            creation_date=date.today(),
            reach=Reach(value=10000 * (i + 1)),
            bodies=[f"Annonce {i}"],
        )
        ads.append(ad)
    return ads


@pytest.fixture
def multiple_pages() -> list[Page]:
    """Liste de pages pour les tests."""
    pages = []
    cms_types = ["Shopify", "WooCommerce", "PrestaShop", "Unknown"]
    for i in range(5):
        page = Page(
            id=PageId(str(200 + i)),
            name=f"Boutique {i}",
            website=Url.try_from_string(f"https://shop{i}.com"),
            cms=CMS.from_string(cms_types[i % len(cms_types)]),
            active_ads_count=10 * (i + 1),
        )
        pages.append(page)
    return pages


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES - RAW DATA
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def meta_api_ad_response() -> dict:
    """Reponse type de l'API Meta Ads."""
    return {
        "id": "123456789",
        "page_id": "987654321",
        "page_name": "Test Shop",
        "ad_creation_time": "2024-01-15T10:30:00+0000",
        "eu_total_reach": {"lower_bound": 40000, "upper_bound": 60000},
        "ad_creative_bodies": ["Decouvrez nos produits!"],
        "ad_creative_link_titles": ["Promo speciale"],
        "ad_creative_link_captions": ["testshop.com"],
        "ad_snapshot_url": "https://facebook.com/ads/archive/render_ad/?id=123456789",
        "currency": "EUR",
        "languages": ["fr"],
        "publisher_platforms": ["facebook", "instagram"],
        "target_ages": "18-65+",
        "target_gender": "All",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MARKERS
# ═══════════════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Configure les markers personnalises."""
    config.addinivalue_line("markers", "unit: Tests unitaires rapides")
    config.addinivalue_line("markers", "integration: Tests d'integration")
    config.addinivalue_line("markers", "slow: Tests lents (>1s)")
