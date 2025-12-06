"""
Adapters pour la persistence des donnees.

Ce module expose les repositories et le DatabaseManager
pour l'architecture hexagonale.
"""

from src.infrastructure.persistence.sqlalchemy_page_repository import SQLAlchemyPageRepository
from src.infrastructure.persistence.sqlalchemy_winning_ad_repository import (
    SQLAlchemyWinningAdRepository,
)

# Models (depuis le module models/)
from src.infrastructure.persistence.models import (
    Base,
    PageRecherche,
    SuiviPage,
    SuiviPageArchive,
    AdsRecherche,
    AdsRechercheArchive,
    WinningAds,
    WinningAdsArchive,
    Tag,
    PageTag,
    PageNote,
    Favorite,
    Collection,
    CollectionPage,
    Blacklist,
    SavedFilter,
    ScheduledScan,
    SearchLog,
    PageSearchHistory,
    WinningAdSearchHistory,
    SearchQueue,
    APICallLog,
    UserSettings,
    ClassificationTaxonomy,
    MetaToken,
    TokenUsageLog,
    AppSettings,
    APICache,
)

# DatabaseManager et migrations
from src.infrastructure.persistence.database import (
    DatabaseManager,
    ensure_tables_exist,
    get_suivi_stats,
    search_pages,
    get_winning_ads_stats_filtered,
    get_search_log_detail,
    cleanup_old_data,
)

# Repository functions
from src.infrastructure.persistence.repositories import (
    # Utils
    get_etat_from_ads_count,
    to_str_list,
    # Settings
    get_app_setting,
    set_app_setting,
    get_all_app_settings,
    # Pages
    save_pages_recherche,
    save_suivi_page,
    save_ads_recherche,
    get_all_pages,
    get_page_history,
    get_all_countries,
    get_all_subcategories,
    add_country_to_page,
    get_pages_count,
    # Organization
    add_to_blacklist,
    remove_from_blacklist,
    get_blacklist,
    is_in_blacklist,
    get_blacklist_ids,
    get_all_tags,
    create_tag,
    delete_tag,
    add_tag_to_page,
    remove_tag_from_page,
    get_page_tags,
    get_pages_by_tag,
    # Winning ads
    is_winning_ad,
    save_winning_ads,
    cleanup_duplicate_winning_ads,
    get_winning_ads,
    get_winning_ads_filtered,
    get_winning_ads_stats,
    get_winning_ads_by_page,
    # Search
    record_page_search_history,
    record_winning_ad_search_history,
    record_pages_search_history_batch,
    record_winning_ads_search_history_batch,
    get_search_history_stats,
    # Taxonomy
    get_taxonomy_categories,
)

__all__ = [
    # Repositories
    "SQLAlchemyPageRepository",
    "SQLAlchemyWinningAdRepository",
    # Core
    "Base",
    "DatabaseManager",
    "ensure_tables_exist",
    # Models
    "PageRecherche",
    "SuiviPage",
    "SuiviPageArchive",
    "AdsRecherche",
    "AdsRechercheArchive",
    "WinningAds",
    "WinningAdsArchive",
    "Tag",
    "PageTag",
    "PageNote",
    "Favorite",
    "Collection",
    "CollectionPage",
    "Blacklist",
    "SavedFilter",
    "ScheduledScan",
    "SearchLog",
    "PageSearchHistory",
    "WinningAdSearchHistory",
    "SearchQueue",
    "APICallLog",
    "UserSettings",
    "ClassificationTaxonomy",
    "MetaToken",
    "TokenUsageLog",
    "AppSettings",
    "APICache",
]
