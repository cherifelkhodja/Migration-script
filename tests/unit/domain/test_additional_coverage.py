"""
Tests unitaires supplementaires pour atteindre 85% de couverture.
"""

import pytest
from datetime import date, datetime, timedelta

from src.domain.entities.ad import Ad
from src.domain.entities.collection import Collection
from src.domain.entities.winning_ad import WinningAd
from src.domain.entities.page import Page
from src.domain.value_objects import (
    PageId, AdId, Reach, Currency, Url, Etat, CMS, Thematique
)
from src.domain.value_objects.etat import EtatLevel


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Collection (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCollectionAdditional:
    """Tests supplementaires pour Collection."""

    def test_add_page_with_string(self):
        """Test ajout de page avec une string."""
        collection = Collection.create("Test")
        # Note: add_page accepte aussi des strings
        added = collection.add_page("123456789")
        assert added

    def test_remove_page_with_string(self):
        """Test retrait de page avec une string."""
        collection = Collection.create("Test", page_ids=["123456789"])
        removed = collection.remove_page("123456789")
        assert removed

    def test_contains_with_string(self):
        """Test contains avec une string."""
        collection = Collection.create("Test", page_ids=["123456789"])
        assert collection.contains("123456789")

    def test_update_description(self):
        """Test mise a jour de la description."""
        collection = Collection.create("Test", description="Old")
        collection.update_description("New description")
        assert collection.description == "New description"
        assert collection._is_dirty

    def test_update_description_same_value(self):
        """Test mise a jour avec meme valeur."""
        collection = Collection.create("Test", description="Same")
        collection._is_dirty = False
        collection.update_description("Same")
        assert not collection._is_dirty

    def test_size_property(self):
        """Test propriete size."""
        collection = Collection.create("Test", page_ids=["123", "456"])
        assert collection.size == 2

    def test_equality_by_id(self):
        """Test egalite par ID."""
        c1 = Collection.create("Test1")
        c1.id = 1
        c2 = Collection.create("Test2")
        c2.id = 1
        assert c1 == c2

    def test_equality_by_name_when_no_id(self):
        """Test egalite par nom quand pas d'ID."""
        c1 = Collection.create("Test")
        c2 = Collection.create("Test")
        assert c1 == c2

    def test_equality_with_non_collection(self):
        """Test egalite avec autre type."""
        c = Collection.create("Test")
        assert c != "Test"

    def test_hash_by_id(self):
        """Test hash par ID."""
        c = Collection.create("Test")
        c.id = 1
        assert hash(c) == hash(1)

    def test_hash_by_name(self):
        """Test hash par nom quand pas d'ID."""
        c = Collection.create("Test")
        assert hash(c) == hash("Test")

    def test_str_representation(self):
        """Test representation string."""
        c = Collection.create("Test", page_ids=["123"])
        assert str(c) == "Test (1 pages)"

    def test_clear_empty_collection(self):
        """Test clear sur collection vide."""
        c = Collection.create("Test")
        c._is_dirty = False
        count = c.clear()
        assert count == 0
        assert not c._is_dirty

    def test_rename_same_name(self):
        """Test rename avec meme nom."""
        c = Collection.create("Test")
        c._is_dirty = False
        c.rename("Test")
        assert not c._is_dirty

    def test_rename_empty_name(self):
        """Test rename avec nom vide."""
        c = Collection.create("Test")
        c._is_dirty = False
        c.rename("   ")
        assert c.name == "Test"
        assert not c._is_dirty

    def test_create_with_invalid_page_ids(self):
        """Test creation avec IDs invalides (ignores)."""
        collection = Collection.create("Test", page_ids=["abc", "123"])
        # abc est invalide (non numerique) donc ignore
        assert len(collection) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Reach (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReachAdditional:
    """Tests supplementaires pour Reach."""

    def test_zero_factory(self):
        """Test factory zero."""
        reach = Reach.zero()
        assert reach.value == 0
        assert reach.is_zero

    def test_is_zero(self):
        """Test is_zero property."""
        assert Reach(0).is_zero
        assert not Reach(1).is_zero

    def test_negative_value_corrected(self):
        """Test que les valeurs negatives sont corrigees."""
        reach = Reach(-100)
        assert reach.value == 0

    def test_from_meta_response_empty(self):
        """Test from_meta_response avec None."""
        reach = Reach.from_meta_response(None)
        assert reach.value == 0

    def test_from_meta_response_string_bounds(self):
        """Test from_meta_response avec bornes en string."""
        data = {"lower_bound": "1000", "upper_bound": "5000"}
        reach = Reach.from_meta_response(data)
        assert reach.value == 3000

    def test_from_meta_response_invalid_string_bounds(self):
        """Test from_meta_response avec bornes string invalides."""
        data = {"lower_bound": "abc", "upper_bound": "def"}
        reach = Reach.from_meta_response(data)
        assert reach.value == 0

    def test_from_meta_response_only_lower(self):
        """Test from_meta_response avec seulement lower."""
        data = {"lower_bound": 1000, "upper_bound": 0}
        reach = Reach.from_meta_response(data)
        assert reach.value == 1000

    def test_range_none(self):
        """Test range quand pas de bornes."""
        reach = Reach(1000)
        assert reach.range is None

    def test_format_range_without_range(self):
        """Test format_range sans plage."""
        reach = Reach(1000)
        assert reach.format_range() == "1K"

    def test_format_with_precision(self):
        """Test format avec precision."""
        reach = Reach(1500)
        result = reach.format(precision=2)
        assert "1.50K" == result

    def test_int_conversion(self):
        """Test conversion en int."""
        reach = Reach(1234)
        assert int(reach) == 1234

    def test_str_representation(self):
        """Test representation string."""
        reach = Reach(50000)
        assert str(reach) == "50K"

    def test_repr_with_range(self):
        """Test repr avec range."""
        reach = Reach(3000, lower_bound=1000, upper_bound=5000)
        assert "range=" in repr(reach)

    def test_repr_without_range(self):
        """Test repr sans range."""
        reach = Reach(1000)
        assert repr(reach) == "Reach(1000)"

    def test_comparison_with_int(self):
        """Test comparaison avec int."""
        reach = Reach(1000)
        assert reach < 2000
        assert reach <= 1000
        assert reach > 500
        assert reach >= 1000

    def test_addition_with_int(self):
        """Test addition avec int."""
        reach = Reach(1000)
        result = reach + 500
        assert result.value == 1500


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Ad (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdAdditional:
    """Tests supplementaires pour Ad."""

    def test_set_keyword(self):
        """Test set_keyword."""
        ad = Ad(id=AdId("123"), page_id=PageId("456"), reach=Reach(0))
        ad.set_keyword("bijoux")
        assert ad._keyword == "bijoux"

    def test_str_representation(self):
        """Test representation string."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            page_name="Test Shop",
            reach=Reach(0)
        )
        assert "123" in str(ad)
        assert "Test Shop" in str(ad)

    def test_repr_representation(self):
        """Test representation debug."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            reach=Reach(1000)
        )
        result = repr(ad)
        assert "123" in result
        assert "456" in result
        assert "1000" in result or "1K" in result

    def test_hash(self):
        """Test hash."""
        ad1 = Ad(id=AdId("123"), page_id=PageId("456"), reach=Reach(0))
        ad2 = Ad(id=AdId("123"), page_id=PageId("789"), reach=Reach(1000))
        assert hash(ad1) == hash(ad2)

    def test_extracted_domain_none(self):
        """Test extracted_domain sans caption valide."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            reach=Reach(0),
            link_captions=["Not a domain with spaces"]
        )
        assert ad.extracted_domain is None

    def test_extracted_domain_too_short(self):
        """Test extracted_domain avec domaine trop court."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            reach=Reach(0),
            link_captions=["a.b"]
        )
        assert ad.extracted_domain is None

    def test_from_meta_response_datetime_object(self):
        """Test from_meta_response avec datetime objet."""
        data = {
            "id": "123456789",
            "page_id": "987654321",
            "page_name": "Test",
            "ad_creation_time": datetime.now(),
            "eu_total_reach": 1000,
        }
        ad = Ad.from_meta_response(data)
        assert ad.creation_date is not None

    def test_from_meta_response_invalid_date(self):
        """Test from_meta_response avec date invalide."""
        data = {
            "id": "123456789",
            "page_id": "987654321",
            "ad_creation_time": "not-a-date",
        }
        ad = Ad.from_meta_response(data)
        assert ad.creation_date is None


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - WinningAd (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWinningAdAdditional:
    """Tests supplementaires pour WinningAd."""

    def test_detected_at(self):
        """Test que detected_at est defini."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            creation_date=date.today(),
            reach=Reach(20000)
        )
        winning = WinningAd.detect(ad)
        assert winning is not None
        assert winning.detected_at is not None

    def test_str_representation(self):
        """Test representation string."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            creation_date=date.today(),
            reach=Reach(20000)
        )
        winning = WinningAd.detect(ad)
        result = str(winning)
        assert "123" in result

    def test_repr_representation(self):
        """Test representation debug."""
        ad = Ad(
            id=AdId("123"),
            page_id=PageId("456"),
            creation_date=date.today(),
            reach=Reach(20000)
        )
        winning = WinningAd.detect(ad)
        result = repr(winning)
        assert "WinningAd" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - AdId (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdIdAdditional:
    """Tests supplementaires pour AdId."""

    def test_from_existing_ad_id(self):
        """Test creation depuis AdId existant."""
        original = AdId("123")
        copy = AdId.from_any(original)
        assert copy == original

    def test_str_representation(self):
        """Test representation string."""
        ad_id = AdId("123456789")
        assert str(ad_id) == "123456789"

    def test_repr_representation(self):
        """Test representation debug."""
        ad_id = AdId("123")
        result = repr(ad_id)
        assert "AdId" in result
        assert "123" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Url (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUrlAdditional:
    """Tests supplementaires pour Url."""

    def test_try_from_string_none(self):
        """Test try_from_string avec None."""
        url = Url.try_from_string(None)
        assert url is None

    def test_from_string_with_http(self):
        """Test from_string avec http."""
        url = Url.from_string("http://example.com")
        assert "https" in url.value

    def test_str_representation(self):
        """Test representation string."""
        url = Url.from_string("example.com")
        assert str(url) == "https://example.com"

    def test_repr_representation(self):
        """Test representation debug."""
        url = Url.from_string("example.com")
        result = repr(url)
        assert "Url" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Currency (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCurrencyAdditional:
    """Tests supplementaires pour Currency."""

    def test_gbp(self):
        """Test livre sterling."""
        currency = Currency.from_string("GBP")
        assert currency.code == "GBP"
        assert currency.symbol == "£"

    def test_format_unknown(self):
        """Test formatage devise inconnue."""
        currency = Currency.unknown()
        result = currency.format(99.99)
        assert "99.99" in result

    def test_bool_known(self):
        """Test bool pour devise connue."""
        currency = Currency.euro()
        assert bool(currency)

    def test_str_representation(self):
        """Test representation string."""
        currency = Currency.euro()
        assert str(currency) == "EUR"

    def test_repr_representation(self):
        """Test representation debug."""
        currency = Currency.usd()
        result = repr(currency)
        assert "Currency" in result
        assert "USD" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Thematique (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestThematiqueAdditional:
    """Tests supplementaires pour Thematique."""

    def test_str_representation(self):
        """Test representation string."""
        theme = Thematique("Mode & Accessoires", "Bijoux")
        assert str(theme) == "Mode & Accessoires > Bijoux"

    def test_str_without_subcategory(self):
        """Test representation sans sous-categorie."""
        theme = Thematique("Mode & Accessoires")
        assert str(theme) == "Mode & Accessoires"

    def test_repr_representation(self):
        """Test representation debug."""
        theme = Thematique("Mode & Accessoires", "Bijoux")
        result = repr(theme)
        assert "Thematique" in result

    def test_from_classification_with_valid_subcategory(self):
        """Test from_classification avec sous-categorie valide."""
        theme = Thematique.from_classification(
            "Mode & Accessoires",
            "Vetements"
        )
        assert theme.category == "Mode & Accessoires"

    def test_bool_unknown(self):
        """Test bool pour thematique inconnue."""
        theme = Thematique.unknown()
        # unknown() returns "Divers & Specialise" which is a valid category
        assert theme.is_unknown


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Page (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPageAdditional:
    """Tests supplementaires pour Page."""

    def test_str_representation(self):
        """Test representation string."""
        page = Page.create("123456789", "Ma Boutique")
        result = str(page)
        assert "Ma Boutique" in result

    def test_repr_representation(self):
        """Test representation debug."""
        page = Page.create("123456789", "Ma Boutique", active_ads_count=10)
        result = repr(page)
        assert "Page" in result
        assert "123456789" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Etat (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEtatAdditional:
    """Tests supplementaires pour Etat."""

    def test_repr_representation(self):
        """Test representation debug."""
        etat = Etat.from_ads_count(50)
        result = repr(etat)
        assert "Etat" in result

    def test_is_medium(self):
        """Test is_medium property."""
        etat_m = Etat.from_ads_count(25)
        assert etat_m.level == EtatLevel.M

    def test_comparison_equal(self):
        """Test comparaison egale."""
        etat1 = Etat.from_ads_count(50)
        etat2 = Etat.from_ads_count(50)  # Same ads_count
        assert etat1 == etat2  # Same level and ads_count


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - PageId (Couverture supplementaire)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPageIdAdditional:
    """Tests supplementaires pour PageId."""

    def test_repr_representation(self):
        """Test representation debug."""
        page_id = PageId("123456789")
        result = repr(page_id)
        assert "PageId" in result
        assert "123456789" in result
