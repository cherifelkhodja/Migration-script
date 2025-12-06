"""
Tests unitaires pour les Entites du domaine.
"""

from datetime import date, timedelta

import pytest

from src.domain.entities.ad import Ad
from src.domain.entities.collection import Collection
from src.domain.entities.page import Page
from src.domain.entities.winning_ad import WinningAd
from src.domain.value_objects import (
    AdId,
    PageId,
    Reach,
)
from src.domain.value_objects.etat import EtatLevel

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Page
# ═══════════════════════════════════════════════════════════════════════════════

class TestPage:
    """Tests pour l'entite Page."""

    def test_create_page(self):
        """Test creation d'une Page."""
        page = Page.create(
            page_id="123456789",
            name="Ma Boutique",
            website="example-shop.com",
            cms="Shopify",
            active_ads_count=50,
        )

        assert str(page.id) == "123456789"
        assert page.name == "Ma Boutique"
        assert page.cms.is_shopify
        assert page.active_ads_count == 50
        assert page.etat.level == EtatLevel.L

    def test_page_with_full_data(self, sample_page):
        """Test page avec toutes les donnees."""
        assert sample_page.is_shopify
        assert sample_page.is_active
        assert sample_page.domain == "example-shop.com"

    def test_update_ads_count(self):
        """Test mise a jour du nombre d'ads."""
        page = Page.create("123", "Test", active_ads_count=10)
        assert page.etat.level == EtatLevel.S

        page.update_ads_count(100)
        assert page.active_ads_count == 100
        assert page.etat.level == EtatLevel.XL

    def test_update_website(self):
        """Test mise a jour de l'URL."""
        page = Page.create("123", "Test")
        assert page.website is None

        page.update_website("https://newsite.com")
        assert page.website is not None
        assert page.domain == "newsite.com"

    def test_update_cms(self):
        """Test mise a jour du CMS."""
        page = Page.create("123", "Test")
        page.update_cms("WooCommerce")
        assert page.cms.is_woocommerce

    def test_update_classification(self):
        """Test mise a jour de la classification."""
        page = Page.create("123", "Test")
        assert not page.is_classified

        page.update_classification(
            category="Mode & Accessoires",
            subcategory="Bijoux",
            confidence=0.9,
            source="gemini"
        )

        assert page.is_classified
        assert page.category == "Mode & Accessoires"
        assert page.subcategory == "Bijoux"

    def test_add_keyword(self):
        """Test ajout de mot-cle."""
        page = Page.create("123", "Test")
        page.add_keyword("bijoux")
        page.add_keyword("BIJOUX")  # Doit etre normalise

        assert "bijoux" in page.keywords
        assert len(page.keywords) == 1  # Pas de doublon

    def test_mark_scanned(self):
        """Test marquage comme scanne."""
        page = Page.create("123", "Test")
        assert page.last_scan_at is None

        page.mark_scanned()
        assert page.last_scan_at is not None

    def test_page_equality(self):
        """Test egalite basee sur l'ID."""
        page1 = Page.create("123", "Boutique A")
        page2 = Page.create("123", "Boutique B")  # Meme ID, nom different
        page3 = Page.create("456", "Boutique A")  # ID different

        assert page1 == page2
        assert page1 != page3

    def test_page_hash(self):
        """Test hash pour utilisation dans set."""
        pages = {
            Page.create("123", "A"),
            Page.create("123", "B"),  # Meme ID
            Page.create("456", "C"),
        }
        assert len(pages) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Ad
# ═══════════════════════════════════════════════════════════════════════════════

class TestAd:
    """Tests pour l'entite Ad."""

    def test_create_ad(self):
        """Test creation d'une Ad."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            page_name="Test Shop",
            creation_date=date.today(),
            reach=Reach(50000),
        )

        assert str(ad.id) == "123"
        assert str(ad.page_id) == "456"
        assert ad.age_days == 0

    def test_from_meta_response(self, meta_api_ad_response):
        """Test creation depuis reponse API Meta."""
        ad = Ad.from_meta_response(meta_api_ad_response)

        assert str(ad.id) == "123456789"
        assert str(ad.page_id) == "987654321"
        assert ad.page_name == "Test Shop"
        assert ad.reach.value == 50000
        assert "Decouvrez nos produits!" in ad.bodies
        assert ad.currency.code == "EUR"

    def test_ad_age(self):
        """Test calcul de l'age."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        ad_today = Ad(id=AdId("1"), page_id=PageId("1"), creation_date=today, reach=Reach(0))
        ad_yesterday = Ad(id=AdId("2"), page_id=PageId("1"), creation_date=yesterday, reach=Reach(0))
        ad_week = Ad(id=AdId("3"), page_id=PageId("1"), creation_date=week_ago, reach=Reach(0))

        assert ad_today.age_days == 0
        assert ad_yesterday.age_days == 1
        assert ad_week.age_days == 7

        assert ad_today.is_very_recent
        assert ad_yesterday.is_recent
        assert ad_week.is_recent

    def test_ad_without_date(self):
        """Test ad sans date de creation."""
        ad = Ad(id=AdId("1"), page_id=PageId("1"), reach=Reach(0))
        assert ad.age_days == -1
        assert not ad.is_recent

    def test_primary_content(self):
        """Test extraction du contenu principal."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            reach=Reach(0),
            bodies=["Premier texte", "Second texte"],
            link_titles=["Premier titre"],
            link_captions=["example.com"],
        )

        assert ad.primary_body == "Premier texte"
        assert ad.primary_title == "Premier titre"
        assert ad.primary_caption == "example.com"

    def test_extracted_domain(self):
        """Test extraction du domaine."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            reach=Reach(0),
            link_captions=["www.example-shop.com"],
        )

        assert ad.extracted_domain == "example-shop.com"

    def test_ad_equality(self):
        """Test egalite basee sur l'ID."""
        ad1 = Ad(id=AdId("123"), page_id=PageId("1"), reach=Reach(0))
        ad2 = Ad(id=AdId("123"), page_id=PageId("2"), reach=Reach(1000))
        ad3 = Ad(id=AdId("456"), page_id=PageId("1"), reach=Reach(0))

        assert ad1 == ad2
        assert ad1 != ad3


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - WinningAd
# ═══════════════════════════════════════════════════════════════════════════════

class TestWinningAd:
    """Tests pour l'entite WinningAd."""

    def test_detect_winning_ad(self):
        """Test detection d'une winning ad."""
        # Ad avec 50k reach et 3 jours -> devrait matcher 4d/15k
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            creation_date=date.today() - timedelta(days=3),
            reach=Reach(50000),
        )

        winning = WinningAd.detect(ad)
        assert winning is not None
        assert "4d" in winning.matched_criteria

    def test_detect_non_winning_ad(self):
        """Test detection d'une ad non winning."""
        # Ad avec 5k reach et 10 jours -> ne match aucun critere
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            creation_date=date.today() - timedelta(days=10),
            reach=Reach(5000),
        )

        winning = WinningAd.detect(ad)
        assert winning is None

    def test_is_winning_static(self):
        """Test methode statique is_winning."""
        ad_winning = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=2),
            reach=Reach(20000),
        )
        ad_not_winning = Ad(
            id=AdId("2"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=30),
            reach=Reach(1000),
        )

        assert WinningAd.is_winning(ad_winning)
        assert not WinningAd.is_winning(ad_not_winning)

    def test_winning_ad_properties(self, winning_ad):
        """Test proprietes de WinningAd."""
        assert winning_ad.id == winning_ad.ad.id
        assert winning_ad.page_id == winning_ad.ad.page_id
        assert winning_ad.reach == winning_ad.ad.reach

    def test_winning_ad_to_dict(self, winning_ad):
        """Test serialisation en dict."""
        data = winning_ad.to_dict()

        assert "ad_id" in data
        assert "page_id" in data
        assert "reach" in data
        assert "matched_criteria" in data

    @pytest.mark.parametrize("age,reach,should_win", [
        (3, 20000, True),   # 4d/15k
        (4, 15000, True),   # 4d/15k exact
        (5, 20000, True),   # 5d/20k
        (7, 50000, True),   # 8d/50k
        (15, 100000, True), # 15d/100k
        (20, 200000, True), # 22d/200k
        (5, 10000, False),  # Pas assez de reach
        (10, 10000, False), # Trop vieux et pas assez de reach
        (30, 50000, False), # Trop vieux
    ])
    def test_winning_criteria(self, age: int, reach: int, should_win: bool):
        """Test differents criteres de winning."""
        ad = Ad(
            id=AdId("1"),
            page_id=PageId("1"),
            creation_date=date.today() - timedelta(days=age),
            reach=Reach(reach),
        )

        assert WinningAd.is_winning(ad) == should_win


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Collection
# ═══════════════════════════════════════════════════════════════════════════════

class TestCollection:
    """Tests pour l'entite Collection."""

    def test_create_collection(self):
        """Test creation d'une Collection."""
        collection = Collection.create(
            name="Mes Favoris",
            description="Pages a surveiller",
        )

        assert collection.name == "Mes Favoris"
        assert collection.description == "Pages a surveiller"
        assert collection.is_empty

    def test_create_with_pages(self):
        """Test creation avec pages initiales."""
        collection = Collection.create(
            name="Test",
            page_ids=["123", "456"],
        )

        assert len(collection) == 2
        assert not collection.is_empty

    def test_add_page(self):
        """Test ajout de page."""
        collection = Collection.create("Test")

        added = collection.add_page(PageId("123"))
        assert added
        assert len(collection) == 1

        # Ajout en doublon
        added_again = collection.add_page(PageId("123"))
        assert not added_again
        assert len(collection) == 1

    def test_remove_page(self):
        """Test retrait de page."""
        collection = Collection.create("Test", page_ids=["123", "456"])

        removed = collection.remove_page(PageId("123"))
        assert removed
        assert len(collection) == 1

        # Retrait d'une page absente
        removed_again = collection.remove_page(PageId("123"))
        assert not removed_again

    def test_contains(self):
        """Test verification de presence."""
        collection = Collection.create("Test", page_ids=["123"])

        assert collection.contains(PageId("123"))
        assert PageId("123") in collection  # Syntaxe 'in'
        assert PageId("456") not in collection

    def test_clear(self):
        """Test vidage de collection."""
        collection = Collection.create("Test", page_ids=["123", "456", "789"])

        count = collection.clear()
        assert count == 3
        assert collection.is_empty

    def test_rename(self):
        """Test renommage."""
        collection = Collection.create("Ancien Nom")
        collection.rename("Nouveau Nom")
        assert collection.name == "Nouveau Nom"

    def test_iteration(self):
        """Test iteration sur les pages."""
        collection = Collection.create("Test", page_ids=["123", "456"])

        page_ids = list(collection)
        assert len(page_ids) == 2

    def test_page_ids_list(self):
        """Test export en liste de strings."""
        collection = Collection.create("Test", page_ids=["123", "456"])

        ids = collection.page_ids_list
        assert "123" in ids
        assert "456" in ids
