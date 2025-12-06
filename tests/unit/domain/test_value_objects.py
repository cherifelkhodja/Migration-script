"""
Tests unitaires pour les Value Objects du domaine.
"""


import pytest

from src.domain.exceptions import (
    InvalidAdIdError,
    InvalidEtatError,
    InvalidPageIdError,
    InvalidUrlError,
)
from src.domain.value_objects import (
    CMS,
    AdId,
    Currency,
    Etat,
    PageId,
    Reach,
    Thematique,
    ThematiqueClassification,
    Url,
)
from src.domain.value_objects.cms import CMSType
from src.domain.value_objects.etat import EtatLevel

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - PageId
# ═══════════════════════════════════════════════════════════════════════════════

class TestPageId:
    """Tests pour PageId."""

    def test_create_valid_page_id(self):
        """Test creation d'un PageId valide."""
        page_id = PageId("123456789")
        assert page_id.value == "123456789"

    def test_create_from_int(self):
        """Test creation depuis un int."""
        page_id = PageId.from_any(123456789)
        assert page_id.value == "123456789"

    def test_create_from_existing(self):
        """Test creation depuis un PageId existant."""
        original = PageId("123")
        copy = PageId.from_any(original)
        assert copy == original

    def test_invalid_empty_page_id(self):
        """Test qu'un PageId vide leve une exception."""
        with pytest.raises(InvalidPageIdError):
            PageId("")

    def test_invalid_none_page_id(self):
        """Test qu'un PageId None leve une exception."""
        with pytest.raises(InvalidPageIdError):
            PageId.from_any(None)

    def test_invalid_non_numeric_page_id(self):
        """Test qu'un PageId non numerique leve une exception."""
        with pytest.raises(InvalidPageIdError):
            PageId("abc123")

    def test_page_id_equality(self):
        """Test egalite de PageId."""
        id1 = PageId("123")
        id2 = PageId("123")
        id3 = PageId("456")

        assert id1 == id2
        assert id1 != id3
        assert id1 == "123"  # Comparaison avec string

    def test_page_id_hash(self):
        """Test que PageId peut etre utilise dans un set."""
        ids = {PageId("123"), PageId("123"), PageId("456")}
        assert len(ids) == 2

    def test_page_id_str(self):
        """Test representation string."""
        page_id = PageId("123456789")
        assert str(page_id) == "123456789"


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - AdId
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdId:
    """Tests pour AdId."""

    def test_create_valid_ad_id(self):
        """Test creation d'un AdId valide."""
        ad_id = AdId("987654321")
        assert ad_id.value == "987654321"

    def test_create_from_any(self):
        """Test creation depuis differents types."""
        ad_id = AdId.from_any(987654321)
        assert ad_id.value == "987654321"

    def test_invalid_empty_ad_id(self):
        """Test qu'un AdId vide leve une exception."""
        with pytest.raises(InvalidAdIdError):
            AdId("")

    def test_ad_id_equality(self):
        """Test egalite de AdId."""
        id1 = AdId("123")
        id2 = AdId("123")
        assert id1 == id2


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Etat
# ═══════════════════════════════════════════════════════════════════════════════

class TestEtat:
    """Tests pour Etat."""

    @pytest.mark.parametrize("ads_count,expected_level", [
        (0, EtatLevel.XS),
        (5, EtatLevel.XS),
        (10, EtatLevel.S),
        (19, EtatLevel.S),
        (20, EtatLevel.M),
        (35, EtatLevel.L),
        (80, EtatLevel.XL),
        (150, EtatLevel.XXL),
        (500, EtatLevel.XXL),
    ])
    def test_from_ads_count(self, ads_count: int, expected_level: EtatLevel):
        """Test calcul de l'etat depuis le nombre d'ads."""
        etat = Etat.from_ads_count(ads_count)
        assert etat.level == expected_level
        assert etat.ads_count == ads_count

    def test_from_string(self):
        """Test creation depuis une chaine."""
        etat = Etat.from_string("XL", ads_count=100)
        assert etat.level == EtatLevel.XL
        assert etat.ads_count == 100

    def test_invalid_etat_string(self):
        """Test qu'un etat invalide leve une exception."""
        with pytest.raises(InvalidEtatError):
            Etat.from_string("XXXL")

    def test_etat_properties(self):
        """Test les proprietes de l'etat."""
        etat_xs = Etat.from_ads_count(5)
        etat_l = Etat.from_ads_count(50)
        etat_xxl = Etat.from_ads_count(200)

        assert etat_xs.is_small
        assert not etat_xs.is_large

        assert etat_l.is_large
        assert not etat_l.is_small

        assert etat_xxl.is_extra_large

    def test_etat_comparison(self):
        """Test comparaison des etats."""
        etat_s = Etat.from_ads_count(15)
        etat_l = Etat.from_ads_count(50)

        assert etat_s < etat_l
        assert etat_l > etat_s
        assert etat_s <= etat_s
        assert etat_l >= etat_l

    def test_etat_str(self):
        """Test representation string."""
        etat = Etat.from_ads_count(50)
        assert str(etat) == "L"


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - CMS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCMS:
    """Tests pour CMS."""

    def test_create_shopify(self):
        """Test creation CMS Shopify."""
        cms = CMS.shopify(theme="Dawn", confidence=0.95)
        assert cms.type == CMSType.SHOPIFY
        assert cms.is_shopify
        assert cms.theme == "Dawn"
        assert cms.confidence == 0.95

    def test_create_from_string(self):
        """Test creation depuis une chaine."""
        cms = CMS.from_string("woocommerce")
        assert cms.type == CMSType.WOOCOMMERCE
        assert cms.is_woocommerce

    def test_create_unknown(self):
        """Test creation CMS inconnu."""
        cms = CMS.unknown()
        assert cms.type == CMSType.UNKNOWN
        assert not cms.is_known

    def test_cms_aliases(self):
        """Test que les alias fonctionnent."""
        assert CMS.from_string("shopify").is_shopify
        assert CMS.from_string("woo").is_woocommerce
        assert CMS.from_string("prestashop").type == CMSType.PRESTASHOP

    def test_cms_is_ecommerce(self):
        """Test detection e-commerce."""
        assert CMS.shopify().is_ecommerce
        assert CMS.woocommerce().is_ecommerce
        assert not CMS.from_string("wix").is_ecommerce

    def test_cms_name(self):
        """Test nom du CMS."""
        cms = CMS.shopify()
        assert cms.name == "Shopify"

    def test_cms_str_with_theme(self):
        """Test representation avec theme."""
        cms = CMS.shopify(theme="Dawn")
        assert str(cms) == "Shopify (Dawn)"


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Url
# ═══════════════════════════════════════════════════════════════════════════════

class TestUrl:
    """Tests pour Url."""

    def test_create_from_full_url(self):
        """Test creation depuis URL complete."""
        url = Url.from_string("https://www.example.com/path")
        assert url.domain == "example.com"
        assert "https://example.com" in url.value

    def test_create_from_domain_only(self):
        """Test creation depuis domaine seul."""
        url = Url.from_string("example.com")
        assert url.domain == "example.com"
        assert url.value == "https://example.com"

    def test_normalize_www(self):
        """Test que www est supprime."""
        url = Url.from_string("www.example.com")
        assert url.domain == "example.com"

    def test_excluded_domains(self):
        """Test que les domaines exclus levent une exception."""
        with pytest.raises(InvalidUrlError):
            Url.from_string("facebook.com")

        with pytest.raises(InvalidUrlError):
            Url.from_string("https://instagram.com")

    def test_allow_excluded(self):
        """Test autorisation des domaines exclus."""
        url = Url.from_string("facebook.com", allow_excluded=True)
        assert url.domain == "facebook.com"

    def test_invalid_url(self):
        """Test URL invalide."""
        with pytest.raises(InvalidUrlError):
            Url.from_string("")

    def test_try_from_string(self):
        """Test creation sans exception."""
        url = Url.try_from_string("example.com")
        assert url is not None

        invalid = Url.try_from_string("facebook.com")
        assert invalid is None

    def test_url_with_path(self):
        """Test creation avec chemin."""
        url = Url.from_string("example.com")
        new_url = url.with_path("/products")
        assert "/products" in new_url.value

    def test_url_equality(self):
        """Test egalite basee sur le domaine."""
        url1 = Url.from_string("https://example.com/path1")
        url2 = Url.from_string("https://example.com/path2")
        assert url1 == url2  # Meme domaine

    def test_url_hash(self):
        """Test hash pour utilisation dans set."""
        urls = {
            Url.from_string("example.com/a"),
            Url.from_string("example.com/b"),
            Url.from_string("other.com"),
        }
        assert len(urls) == 2  # example.com compte une fois


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Reach
# ═══════════════════════════════════════════════════════════════════════════════

class TestReach:
    """Tests pour Reach."""

    def test_create_reach(self):
        """Test creation de Reach."""
        reach = Reach(50000)
        assert reach.value == 50000

    def test_create_with_bounds(self):
        """Test creation avec bornes."""
        reach = Reach(50000, lower_bound=40000, upper_bound=60000)
        assert reach.range == (40000, 60000)

    def test_from_meta_response(self):
        """Test creation depuis reponse API Meta."""
        data = {"lower_bound": 40000, "upper_bound": 60000}
        reach = Reach.from_meta_response(data)
        assert reach.value == 50000  # Moyenne
        assert reach.lower_bound == 40000
        assert reach.upper_bound == 60000

    def test_from_meta_response_int(self):
        """Test creation depuis int."""
        reach = Reach.from_meta_response(50000)
        assert reach.value == 50000

    def test_reach_properties(self):
        """Test proprietes de Reach."""
        reach_low = Reach(500)
        reach_mid = Reach(5000)
        reach_high = Reach(50000)
        reach_very_high = Reach(150000)

        assert not reach_low.is_significant
        assert reach_mid.is_significant
        assert reach_high.is_high
        assert reach_very_high.is_very_high

    def test_reach_format(self):
        """Test formatage de Reach."""
        assert Reach(500).format() == "500"
        assert Reach(5000).format() == "5K"
        assert Reach(50000).format() == "50K"
        assert Reach(1500000).format() == "1.5M"

    def test_reach_format_range(self):
        """Test formatage de la plage."""
        reach = Reach(50000, lower_bound=40000, upper_bound=60000)
        assert reach.format_range() == "40K - 60K"

    def test_reach_comparison(self):
        """Test comparaison de Reach."""
        r1 = Reach(1000)
        r2 = Reach(2000)
        assert r1 < r2
        assert r2 > r1

    def test_reach_addition(self):
        """Test addition de Reach."""
        r1 = Reach(1000)
        r2 = Reach(2000)
        total = r1 + r2
        assert total.value == 3000


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Currency
# ═══════════════════════════════════════════════════════════════════════════════

class TestCurrency:
    """Tests pour Currency."""

    def test_create_euro(self):
        """Test creation Euro."""
        currency = Currency.euro()
        assert currency.code == "EUR"
        assert currency.is_euro

    def test_create_from_string(self):
        """Test creation depuis string."""
        currency = Currency.from_string("usd")
        assert currency.code == "USD"

    def test_currency_symbol(self):
        """Test symbole de devise."""
        assert Currency.euro().symbol == "\u20ac"
        assert Currency.usd().symbol == "$"

    def test_currency_format(self):
        """Test formatage de montant."""
        eur = Currency.euro()
        assert eur.format(99.99) == "99.99 \u20ac"

        usd = Currency.usd()
        assert usd.format(99.99) == "$99.99"

    def test_unknown_currency(self):
        """Test devise inconnue."""
        currency = Currency.unknown()
        assert not currency.is_known
        assert not bool(currency)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS - Thematique
# ═══════════════════════════════════════════════════════════════════════════════

class TestThematique:
    """Tests pour Thematique."""

    def test_create_thematique(self):
        """Test creation de Thematique."""
        theme = Thematique("Mode & Accessoires", "Bijoux")
        assert theme.category == "Mode & Accessoires"
        assert theme.subcategory == "Bijoux"

    def test_thematique_full_path(self):
        """Test chemin complet."""
        theme = Thematique("Mode & Accessoires", "Bijoux")
        assert theme.full_path == "Mode & Accessoires > Bijoux"

    def test_thematique_unknown(self):
        """Test thematique inconnue."""
        theme = Thematique.unknown()
        assert theme.is_unknown

    def test_from_classification(self):
        """Test creation avec validation taxonomie."""
        theme = Thematique.from_classification("Mode & Accessoires", "Bijoux")
        assert theme.category == "Mode & Accessoires"

    def test_from_classification_fallback(self):
        """Test fallback si categorie inconnue."""
        theme = Thematique.from_classification("Categorie Inexistante")
        assert theme.category == "Divers & Specialise"


class TestThematiqueClassification:
    """Tests pour ThematiqueClassification."""

    def test_create_classification(self):
        """Test creation de classification."""
        theme = Thematique("Mode & Accessoires", "Bijoux")
        classification = ThematiqueClassification(
            thematique=theme,
            confidence=0.92,
            source="gemini"
        )
        assert classification.confidence == 0.92
        assert classification.is_confident

    def test_from_gemini(self):
        """Test creation depuis reponse Gemini."""
        classification = ThematiqueClassification.from_gemini(
            "Mode & Accessoires", "Bijoux", 0.85
        )
        assert classification.source == "gemini"

    def test_confidence_levels(self):
        """Test niveaux de confiance."""
        low = ThematiqueClassification(
            thematique=Thematique.unknown(),
            confidence=0.5,
        )
        high = ThematiqueClassification(
            thematique=Thematique("Mode & Accessoires"),
            confidence=0.9,
        )

        assert not low.is_confident
        assert high.is_confident
        assert high.is_very_confident
