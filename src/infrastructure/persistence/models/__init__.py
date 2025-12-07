"""
Modeles SQLAlchemy - exports centralises.

Organisation par domaine:
- base: Base declarative
- page_models: Pages et suivi
- ads_models: Publicites et winning ads
- organization_models: Tags, collections, blacklist
- search_models: Logs et historique recherche
- settings_models: Parametres et tokens
- cache_models: Cache API
"""

from src.infrastructure.persistence.models.base import Base

from src.infrastructure.persistence.models.page_models import (
    PageRecherche,
    SuiviPage,
    SuiviPageArchive,
)

from src.infrastructure.persistence.models.ads_models import (
    AdsRecherche,
    WinningAds,
    AdsRechercheArchive,
    WinningAdsArchive,
)

from src.infrastructure.persistence.models.organization_models import (
    Tag,
    PageTag,
    PageNote,
    Favorite,
    Collection,
    CollectionPage,
    Blacklist,
    SavedFilter,
    ScheduledScan,
)

from src.infrastructure.persistence.models.search_models import (
    SearchLog,
    PageSearchHistory,
    WinningAdSearchHistory,
    SearchQueue,
    APICallLog,
)

from src.infrastructure.persistence.models.settings_models import (
    UserSettings,
    ClassificationTaxonomy,
    MetaToken,
    TokenUsageLog,
    AppSettings,
)

from src.infrastructure.persistence.models.cache_models import (
    APICache,
)

from src.infrastructure.persistence.models.auth_models import (
    UserModel,
    AuditLog,
    AuditAction,
)

__all__ = [
    # Base
    "Base",
    # Pages
    "PageRecherche",
    "SuiviPage",
    "SuiviPageArchive",
    # Ads
    "AdsRecherche",
    "WinningAds",
    "AdsRechercheArchive",
    "WinningAdsArchive",
    # Organization
    "Tag",
    "PageTag",
    "PageNote",
    "Favorite",
    "Collection",
    "CollectionPage",
    "Blacklist",
    "SavedFilter",
    "ScheduledScan",
    # Search
    "SearchLog",
    "PageSearchHistory",
    "WinningAdSearchHistory",
    "SearchQueue",
    "APICallLog",
    # Settings
    "UserSettings",
    "ClassificationTaxonomy",
    "MetaToken",
    "TokenUsageLog",
    "AppSettings",
    # Cache
    "APICache",
    # Auth
    "UserModel",
    "AuditLog",
    "AuditAction",
]
