"""
Tests unitaires pour les Exceptions du domaine.
"""


from src.domain.exceptions import (
    AdNotFoundError,
    ClassificationError,
    DomainException,
    InvalidAdIdError,
    InvalidCMSError,
    InvalidEtatError,
    InvalidPageIdError,
    InvalidThematiqueError,
    InvalidUrlError,
    PageNotFoundError,
    RateLimitError,
    SearchError,
    WinningAdCriteriaError,
)


class TestDomainException:
    """Tests pour DomainException."""

    def test_create_with_message_only(self):
        """Test creation avec message seul."""
        exc = DomainException("Test error")
        assert exc.message == "Test error"
        assert exc.code == "DomainException"

    def test_create_with_code(self):
        """Test creation avec code."""
        exc = DomainException("Test error", code="TEST_CODE")
        assert exc.code == "TEST_CODE"

    def test_str_representation(self):
        """Test representation string."""
        exc = DomainException("Test error", code="TEST")
        assert str(exc) == "[TEST] Test error"


class TestInvalidPageIdError:
    """Tests pour InvalidPageIdError."""

    def test_create(self):
        """Test creation."""
        exc = InvalidPageIdError("abc")
        assert exc.invalid_value == "abc"
        assert exc.code == "INVALID_PAGE_ID"
        assert "abc" in str(exc)


class TestInvalidAdIdError:
    """Tests pour InvalidAdIdError."""

    def test_create(self):
        """Test creation."""
        exc = InvalidAdIdError("")
        assert exc.invalid_value == ""
        assert exc.code == "INVALID_AD_ID"


class TestInvalidEtatError:
    """Tests pour InvalidEtatError."""

    def test_create(self):
        """Test creation."""
        exc = InvalidEtatError("XXXL")
        assert exc.invalid_value == "XXXL"
        assert exc.code == "INVALID_ETAT"
        assert "XS" in str(exc)  # Valid etats listed


class TestInvalidCMSError:
    """Tests pour InvalidCMSError."""

    def test_create(self):
        """Test creation."""
        exc = InvalidCMSError("InvalidCMS")
        assert exc.invalid_value == "InvalidCMS"
        assert exc.code == "INVALID_CMS"
        assert "Shopify" in str(exc)


class TestInvalidUrlError:
    """Tests pour InvalidUrlError."""

    def test_create_without_reason(self):
        """Test creation sans raison."""
        exc = InvalidUrlError("not-a-url")
        assert exc.invalid_value == "not-a-url"
        assert exc.code == "INVALID_URL"

    def test_create_with_reason(self):
        """Test creation avec raison."""
        exc = InvalidUrlError("facebook.com", reason="Excluded domain")
        assert "Excluded domain" in str(exc)


class TestInvalidThematiqueError:
    """Tests pour InvalidThematiqueError."""

    def test_create_category_only(self):
        """Test creation avec categorie seule."""
        exc = InvalidThematiqueError("Invalid Cat")
        assert exc.category == "Invalid Cat"
        assert exc.subcategory is None
        assert exc.code == "INVALID_THEMATIQUE"

    def test_create_with_subcategory(self):
        """Test creation avec sous-categorie."""
        exc = InvalidThematiqueError("Mode", "InvalidSub")
        assert exc.subcategory == "InvalidSub"
        assert "sous-categorie" in str(exc)


class TestWinningAdCriteriaError:
    """Tests pour WinningAdCriteriaError."""

    def test_create(self):
        """Test creation."""
        exc = WinningAdCriteriaError(age_days=-1, reach=-100)
        assert exc.age_days == -1
        assert exc.reach == -100
        assert exc.code == "INVALID_WINNING_CRITERIA"


class TestPageNotFoundError:
    """Tests pour PageNotFoundError."""

    def test_create(self):
        """Test creation."""
        exc = PageNotFoundError("123456789")
        assert exc.page_id == "123456789"
        assert exc.code == "PAGE_NOT_FOUND"
        assert "123456789" in str(exc)


class TestAdNotFoundError:
    """Tests pour AdNotFoundError."""

    def test_create(self):
        """Test creation."""
        exc = AdNotFoundError("987654321")
        assert exc.ad_id == "987654321"
        assert exc.code == "AD_NOT_FOUND"


class TestSearchError:
    """Tests pour SearchError."""

    def test_create_without_keyword(self):
        """Test creation sans mot-cle."""
        exc = SearchError("API error")
        assert exc.keyword is None
        assert exc.code == "SEARCH_ERROR"

    def test_create_with_keyword(self):
        """Test creation avec mot-cle."""
        exc = SearchError("Rate limit", keyword="bijoux")
        assert exc.keyword == "bijoux"
        assert "bijoux" in str(exc)


class TestRateLimitError:
    """Tests pour RateLimitError."""

    def test_create_without_retry(self):
        """Test creation sans retry."""
        exc = RateLimitError("Meta API")
        assert exc.service == "Meta API"
        assert exc.retry_after_seconds is None
        assert exc.code == "RATE_LIMIT"

    def test_create_with_retry(self):
        """Test creation avec retry."""
        exc = RateLimitError("Meta API", retry_after_seconds=60)
        assert exc.retry_after_seconds == 60
        assert "60 secondes" in str(exc)


class TestClassificationError:
    """Tests pour ClassificationError."""

    def test_create_without_page_id(self):
        """Test creation sans page_id."""
        exc = ClassificationError("Gemini error")
        assert exc.page_id is None
        assert exc.code == "CLASSIFICATION_ERROR"

    def test_create_with_page_id(self):
        """Test creation avec page_id."""
        exc = ClassificationError("Timeout", page_id="123456789")
        assert exc.page_id == "123456789"
        assert "123456789" in str(exc)
