"""
Module de gestion de la base de donnees PostgreSQL.

Migre depuis app/database.py vers l'architecture hexagonale.
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Float, Index, Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert

# Import du cache (avec fallback si non disponible)
try:
    from src.infrastructure.cache import cached, invalidate_stats_cache
    CACHE_ENABLED = True
except ImportError:
    try:
        from app.cache import cached, invalidate_stats_cache
        CACHE_ENABLED = True
    except ImportError:
        CACHE_ENABLED = False
        def cached(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLES
# ═══════════════════════════════════════════════════════════════════════════════

class PageRecherche(Base):
    """Table liste_page_recherche - Toutes les pages analysées"""
    __tablename__ = "liste_page_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    page_name = Column(String(255))
    lien_site = Column(String(500))
    lien_fb_ad_library = Column(String(500))
    keywords = Column(Text)  # Keywords utilisés pour trouver cette page (séparés par |)
    thematique = Column(String(100))  # Catégorie principale (classification Gemini)
    subcategory = Column(String(100))  # Sous-catégorie (classification Gemini)
    classification_confidence = Column(Float)  # Score de confiance 0.0-1.0
    classified_at = Column(DateTime)  # Date de dernière classification
    type_produits = Column(Text)
    moyens_paiements = Column(Text)
    pays = Column(String(255))  # Multi-valeurs: "FR,DE,ES" (pays des recherches où la page apparaît)
    langue = Column(String(50))
    cms = Column(String(50))
    template = Column(String(100))
    devise = Column(String(10))
    etat = Column(String(20))  # inactif, XS, S, M, L, XL, XXL
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    dernier_scan = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Données extraites du site pour classification Gemini (évite re-scraping)
    site_title = Column(String(255))
    site_description = Column(Text)
    site_h1 = Column(String(200))
    site_keywords = Column(String(300))
    # Lien vers la dernière recherche qui a mis à jour cette page
    last_search_log_id = Column(Integer, nullable=True, index=True)
    # Flag indiquant si la page a été créée (True) ou mise à jour (False) lors de la dernière recherche
    was_created_in_last_search = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_page_etat', 'etat'),
        Index('idx_page_cms', 'cms'),
        Index('idx_page_dernier_scan', 'dernier_scan'),
        # Nouveaux index composites pour requêtes fréquentes
        Index('idx_page_cms_etat', 'cms', 'etat'),  # Filtre CMS + État
        Index('idx_page_etat_ads', 'etat', 'nombre_ads_active'),  # Tri par ads dans un état
        Index('idx_page_created', 'created_at'),  # Pour tendances
        Index('idx_page_thematique', 'thematique'),  # Pour filtrer par catégorie
    )


class SuiviPage(Base):
    """Table suivi_page - Historique des pages avec >= 10 ads actives"""
    __tablename__ = "suivi_page"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cle_suivi = Column(String(100))
    page_id = Column(String(50), nullable=False, index=True)
    nom_site = Column(String(255))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_suivi_page_date', 'page_id', 'date_scan'),
    )


class AdsRecherche(Base):
    """Table liste_ads_recherche - Annonces des pages avec >= 20 ads"""
    __tablename__ = "liste_ads_recherche"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    eu_total_reach = Column(String(100))
    languages = Column(String(100))
    country = Column(String(50))
    publisher_platforms = Column(String(200))
    target_ages = Column(String(100))
    target_gender = Column(String(50))
    beneficiary_payers = Column(Text)
    date_scan = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_ads_page', 'page_id'),
        Index('idx_ads_date', 'date_scan'),
    )


class Blacklist(Base):
    """Table blacklist - Pages à exclure des recherches"""
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    page_name = Column(String(255))
    raison = Column(String(255))  # Raison de la mise en blacklist
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_blacklist_page_name', 'page_name'),
    )


class WinningAds(Base):
    """Table winning_ads - Annonces performantes détectées"""
    __tablename__ = "winning_ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String(50), unique=True, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_age_days = Column(Integer)  # Âge de l'ad au moment du scan
    eu_total_reach = Column(Integer)  # Reach au moment du scan
    matched_criteria = Column(String(100))  # Critère validé (ex: "≤4d & >15k")
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    lien_site = Column(String(500))
    date_scan = Column(DateTime, default=datetime.utcnow)
    # Lien vers la recherche qui a trouvé cette winning ad
    search_log_id = Column(Integer, nullable=True, index=True)
    # Flag: nouvelle winning ad ou mise à jour d'une existante
    is_new = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_winning_ads_page', 'page_id'),
        Index('idx_winning_ads_date', 'date_scan'),
        Index('idx_winning_ads_ad', 'ad_id', 'date_scan'),
        # Nouveaux index composites
        Index('idx_winning_ads_page_date', 'page_id', 'date_scan'),  # Stats par page/période
        Index('idx_winning_ads_reach', 'eu_total_reach'),  # Tri par reach
    )


class Tag(Base):
    """Table tags - Tags personnalisés pour organiser les pages"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(20), default="#3B82F6")  # Couleur hex
    created_at = Column(DateTime, default=datetime.utcnow)


class PageTag(Base):
    """Table page_tags - Association pages <-> tags"""
    __tablename__ = "page_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    tag_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_page_tag_unique', 'page_id', 'tag_id', unique=True),
    )


class PageNote(Base):
    """Table page_notes - Notes sur les pages"""
    __tablename__ = "page_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(Base):
    """Table favorites - Pages favorites"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(50), unique=True, nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class Collection(Base):
    """Table collections - Dossiers/Collections de pages"""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(20), default="#6366F1")
    icon = Column(String(10), default="📁")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollectionPage(Base):
    """Table collection_pages - Association collections <-> pages"""
    __tablename__ = "collection_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_collection_page_unique', 'collection_id', 'page_id', unique=True),
    )


class SavedFilter(Base):
    """Table saved_filters - Filtres de recherche sauvegardés"""
    __tablename__ = "saved_filters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    filter_type = Column(String(50), default="pages")  # pages, ads, winning
    filters_json = Column(Text)  # JSON des filtres
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledScan(Base):
    """Table scheduled_scans - Scans programmés"""
    __tablename__ = "scheduled_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    keywords = Column(Text)  # Keywords à rechercher
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    frequency = Column(String(20), default="daily")  # daily, weekly, monthly
    is_active = Column(Integer, default=1)  # 1=actif, 0=inactif
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    """Table user_settings - Paramètres utilisateur"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClassificationTaxonomy(Base):
    """Table classification_taxonomy - Taxonomie pour la classification automatique"""
    __tablename__ = "classification_taxonomy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False)  # Catégorie principale
    subcategory = Column(String(100), nullable=False)  # Sous-catégorie
    description = Column(Text)  # Description/exemples pour aider Gemini
    is_active = Column(Boolean, default=True)  # Actif ou non
    sort_order = Column(Integer, default=0)  # Ordre d'affichage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_taxonomy_category', 'category'),
        Index('idx_taxonomy_active', 'is_active'),
    )


class MetaToken(Base):
    """Table meta_tokens - Gestion des tokens Meta API"""
    __tablename__ = "meta_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))  # Nom descriptif (ex: "Token Principal", "Token Backup 1")
    token = Column(Text, nullable=False)  # Le token Meta API (crypté en prod)
    proxy_url = Column(String(255), nullable=True)  # Proxy associé (ex: "http://user:pass@ip:port")
    is_active = Column(Boolean, default=True)  # Token actif ou désactivé

    # Statistiques d'utilisation
    total_calls = Column(Integer, default=0)  # Nombre total d'appels
    total_errors = Column(Integer, default=0)  # Nombre total d'erreurs
    rate_limit_hits = Column(Integer, default=0)  # Nombre de rate limits

    # État actuel
    last_used_at = Column(DateTime)  # Dernière utilisation
    last_error_at = Column(DateTime)  # Dernière erreur
    last_error_message = Column(Text)  # Dernier message d'erreur
    rate_limited_until = Column(DateTime)  # Rate limit jusqu'à cette date

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_meta_token_active', 'is_active'),
    )


class TokenUsageLog(Base):
    """Logs detailles d'utilisation des tokens Meta API"""
    __tablename__ = "token_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_id = Column(Integer, nullable=False, index=True)
    token_name = Column(String(100))

    # Type d'action
    action_type = Column(String(50))  # "search", "page_fetch", "verification", "rate_limit"

    # Details de la recherche
    keyword = Column(String(255))
    countries = Column(String(100))
    page_id = Column(String(50))

    # Resultats
    success = Column(Boolean, default=True)
    ads_count = Column(Integer, default=0)
    error_message = Column(Text)
    response_time_ms = Column(Integer)  # Temps de reponse en ms

    # Metadonnees
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_token_log_date', 'created_at'),
        Index('idx_token_log_token', 'token_id', 'created_at'),
    )


class AppSettings(Base):
    """Table app_settings - Paramètres persistants de l'application"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchLog(Base):
    """Table search_logs - Historique complet des recherches"""
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Paramètres de recherche
    keywords = Column(Text)  # Mots-clés séparés par |
    countries = Column(String(100))
    languages = Column(String(100))
    min_ads = Column(Integer, default=1)
    selected_cms = Column(String(200))  # CMS filtrés

    # Timing global
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    duration_seconds = Column(Float)

    # Résultats globaux
    status = Column(String(20), default="running")  # running, completed, failed, cancelled
    error_message = Column(Text)

    # Métriques par phase (JSON)
    phases_data = Column(Text)  # JSON avec détails de chaque phase

    # Résumé final
    total_ads_found = Column(Integer, default=0)
    total_pages_found = Column(Integer, default=0)
    pages_after_filter = Column(Integer, default=0)
    pages_shopify = Column(Integer, default=0)
    pages_other_cms = Column(Integer, default=0)
    winning_ads_count = Column(Integer, default=0)
    blacklisted_ads_skipped = Column(Integer, default=0)

    # Détails sauvegarde
    pages_saved = Column(Integer, default=0)
    ads_saved = Column(Integer, default=0)
    # Comptage new vs existing
    new_pages_count = Column(Integer, default=0)  # Nouvelles pages découvertes
    existing_pages_updated = Column(Integer, default=0)  # Pages existantes mises à jour
    new_winning_ads_count = Column(Integer, default=0)  # Nouvelles winning ads
    existing_winning_ads_updated = Column(Integer, default=0)  # Winning ads mises à jour

    # ═══ STATS API ═══
    # Compteurs d'appels
    meta_api_calls = Column(Integer, default=0)
    scraper_api_calls = Column(Integer, default=0)
    web_requests = Column(Integer, default=0)

    # Erreurs
    meta_api_errors = Column(Integer, default=0)
    scraper_api_errors = Column(Integer, default=0)
    web_errors = Column(Integer, default=0)
    rate_limit_hits = Column(Integer, default=0)

    # Temps de réponse (ms)
    meta_api_avg_time = Column(Float, default=0)
    scraper_api_avg_time = Column(Float, default=0)
    web_avg_time = Column(Float, default=0)

    # Coût estimé (pour ScraperAPI)
    scraper_api_cost = Column(Float, default=0)

    # Détails API par mot-clé (JSON)
    api_details = Column(Text)  # JSON avec détails par keyword

    # Liste des erreurs détaillées (JSON)
    errors_list = Column(Text)  # JSON array des erreurs [{"type": "meta_api", "message": "...", "keyword": "...", "timestamp": "..."}]

    # Détail erreurs scraper par type (JSON)
    scraper_errors_by_type = Column(Text)  # JSON {"timeout": 5, "403_forbidden": 2, ...}

    __table_args__ = (
        Index('idx_search_log_date', 'started_at'),
        Index('idx_search_log_status', 'status'),
        # Nouveaux index composites
        Index('idx_search_log_status_date', 'status', 'started_at'),  # Filtrer par statut + période
    )


class PageSearchHistory(Base):
    """
    Table de liaison many-to-many entre SearchLog et PageRecherche.
    Garde l'historique de toutes les recherches ayant trouvé chaque page.
    """
    __tablename__ = "page_search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    found_at = Column(DateTime, default=datetime.utcnow)
    was_new = Column(Boolean, default=True)  # True si la page était nouvelle lors de cette recherche
    # Infos snapshot au moment de la découverte
    ads_count_at_discovery = Column(Integer, default=0)
    keyword_matched = Column(String(255))  # Le mot-clé qui a trouvé cette page

    __table_args__ = (
        Index('idx_page_search_history_search', 'search_log_id'),
        Index('idx_page_search_history_page', 'page_id'),
        Index('idx_page_search_history_composite', 'search_log_id', 'page_id'),
    )


class WinningAdSearchHistory(Base):
    """
    Table de liaison many-to-many entre SearchLog et WinningAds.
    Garde l'historique de toutes les recherches ayant trouvé chaque winning ad.
    """
    __tablename__ = "winning_ad_search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, nullable=False, index=True)
    ad_id = Column(String(50), nullable=False, index=True)
    found_at = Column(DateTime, default=datetime.utcnow)
    was_new = Column(Boolean, default=True)  # True si l'ad était nouvelle lors de cette recherche
    # Infos snapshot au moment de la découverte
    reach_at_discovery = Column(Integer, default=0)
    age_days_at_discovery = Column(Integer, default=0)
    matched_criteria = Column(String(100))

    __table_args__ = (
        Index('idx_winning_ad_search_history_search', 'search_log_id'),
        Index('idx_winning_ad_search_history_ad', 'ad_id'),
        Index('idx_winning_ad_search_history_composite', 'search_log_id', 'ad_id'),
    )


class SearchQueue(Base):
    """Table search_queue - File d'attente des recherches en arrière-plan"""
    __tablename__ = "search_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Statut: pending, running, completed, failed, cancelled, interrupted
    status = Column(String(20), default="pending", index=True)

    # Paramètres de recherche (JSON)
    keywords = Column(Text)  # JSON array des mots-clés
    cms_filter = Column(Text)  # JSON array des CMS à inclure
    countries = Column(String(100), default="FR")
    languages = Column(String(100), default="fr")
    ads_min = Column(Integer, default=3)

    # Progression
    current_phase = Column(Integer, default=0)
    current_phase_name = Column(String(100))
    progress_percent = Column(Integer, default=0)
    progress_message = Column(Text)
    phases_data = Column(Text)  # JSON array des phases complétées avec stats

    # Résultats
    search_log_id = Column(Integer, nullable=True)  # Lien vers SearchLog une fois terminé
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Session utilisateur (pour identifier les recherches d'un utilisateur)
    user_session = Column(String(100), nullable=True, index=True)

    # Priorité (pour futures améliorations)
    priority = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_search_queue_status', 'status'),
        Index('idx_search_queue_user', 'user_session'),
        Index('idx_search_queue_created', 'created_at'),
    )


class APICallLog(Base):
    """Table api_call_logs - Détails de chaque appel API"""
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(Integer, index=True)  # Lien vers SearchLog

    # Type d'appel
    api_type = Column(String(50))  # meta_api, scraper_api, web_request
    endpoint = Column(String(500))  # URL ou endpoint appelé
    method = Column(String(10), default="GET")

    # Contexte
    keyword = Column(String(200))  # Mot-clé associé (si applicable)
    page_id = Column(String(50))  # Page ID (si applicable)
    site_url = Column(String(500))  # URL du site (si applicable)

    # Résultat
    status_code = Column(Integer)
    success = Column(Boolean, default=True)
    error_type = Column(String(100))  # rate_limit, timeout, http_error, network_error
    error_message = Column(Text)

    # Performance
    response_time_ms = Column(Float)  # Temps de réponse en ms
    response_size = Column(Integer)  # Taille réponse en bytes

    # Données récupérées
    items_returned = Column(Integer, default=0)  # Nombre d'éléments retournés

    # Timestamp
    called_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_api_call_search', 'search_log_id'),
        Index('idx_api_call_type', 'api_type'),
        Index('idx_api_call_date', 'called_at'),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLES D'ARCHIVE
# ═══════════════════════════════════════════════════════════════════════════════

class SuiviPageArchive(Base):
    """Archive de suivi_page - Données historiques >90 jours"""
    __tablename__ = "suivi_page_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer)  # ID original de la table source
    cle_suivi = Column(String(100))
    page_id = Column(String(50), nullable=False, index=True)
    nom_site = Column(String(255))
    nombre_ads_active = Column(Integer, default=0)
    nombre_produits = Column(Integer, default=0)
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)


class AdsRechercheArchive(Base):
    """Archive de liste_ads_recherche - Données historiques >90 jours"""
    __tablename__ = "liste_ads_recherche_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    eu_total_reach = Column(String(100))
    languages = Column(String(100))
    country = Column(String(50))
    publisher_platforms = Column(String(200))
    target_ages = Column(String(100))
    target_gender = Column(String(50))
    beneficiary_payers = Column(Text)
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)


class WinningAdsArchive(Base):
    """Archive de winning_ads - Données historiques >90 jours"""
    __tablename__ = "winning_ads_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_id = Column(Integer)
    ad_id = Column(String(50), nullable=False, index=True)
    page_id = Column(String(50), nullable=False, index=True)
    page_name = Column(String(255))
    ad_creation_time = Column(DateTime)
    ad_age_days = Column(Integer)
    eu_total_reach = Column(Integer)
    matched_criteria = Column(String(100))
    ad_creative_bodies = Column(Text)
    ad_creative_link_captions = Column(Text)
    ad_creative_link_titles = Column(Text)
    ad_snapshot_url = Column(String(500))
    lien_site = Column(String(500))
    date_scan = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE API
# ═══════════════════════════════════════════════════════════════════════════════

class APICache(Base):
    """Cache pour les appels API Meta"""
    __tablename__ = "api_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    cache_type = Column(String(50))  # "search_ads", "page_info", etc.
    response_data = Column(Text)  # JSON serialized
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    hit_count = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_cache_expires', 'expires_at'),
        Index('idx_cache_type', 'cache_type'),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA CONNEXION
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """Gestionnaire de connexion à la base de données avec connection pooling optimisé"""

    def __init__(self, database_url: str = None):
        """
        Initialise la connexion à la base de données avec pool de connexions.

        Args:
            database_url: URL de connexion PostgreSQL
        """
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/meta_ads"
            )

        # Configuration du pool de connexions optimisé
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,          # Vérifie que la connexion est valide avant utilisation
            pool_size=5,                  # Nombre de connexions permanentes dans le pool
            max_overflow=10,              # Connexions supplémentaires autorisées en pic
            pool_timeout=30,              # Timeout pour obtenir une connexion (secondes)
            pool_recycle=1800,            # Recycle les connexions après 30 min (évite timeout DB)
            echo=False,                   # Mettre à True pour debug SQL
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self):
        """Crée toutes les tables si elles n'existent pas"""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Context manager pour les sessions avec gestion automatique des transactions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pool_status(self) -> Dict:
        """Retourne les statistiques du pool de connexions"""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalidatedcount() if hasattr(pool, 'invalidatedcount') else 0
        }


def ensure_tables_exist(db: DatabaseManager) -> bool:
    """
    S'assure que toutes les tables existent dans la base de données.
    Crée les tables manquantes si nécessaire.
    Ajoute les colonnes manquantes aux tables existantes.

    Args:
        db: Instance DatabaseManager

    Returns:
        True si succès
    """
    try:
        # Créer toutes les tables manquantes
        Base.metadata.create_all(db.engine)

        # Vérifier explicitement les tables d'historique
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if "page_search_history" not in existing_tables:
            print("[ensure_tables_exist] Création de la table page_search_history...")
            PageSearchHistory.__table__.create(db.engine, checkfirst=True)

        if "winning_ad_search_history" not in existing_tables:
            print("[ensure_tables_exist] Création de la table winning_ad_search_history...")
            WinningAdSearchHistory.__table__.create(db.engine, checkfirst=True)

        # Migrations pour ajouter les colonnes manquantes
        _run_migrations(db)

        return True
    except Exception as e:
        print(f"Erreur création tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_migrations(db: DatabaseManager):
    """Exécute les migrations pour ajouter les colonnes manquantes"""
    from sqlalchemy import text

    migrations = [
        # Colonnes API stats pour SearchLog
        ("search_logs", "meta_api_calls", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_calls INTEGER DEFAULT 0"),
        ("search_logs", "scraper_api_calls", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_calls INTEGER DEFAULT 0"),
        ("search_logs", "web_requests", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_requests INTEGER DEFAULT 0"),
        ("search_logs", "meta_api_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_errors INTEGER DEFAULT 0"),
        ("search_logs", "scraper_api_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_errors INTEGER DEFAULT 0"),
        ("search_logs", "web_errors", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_errors INTEGER DEFAULT 0"),
        ("search_logs", "rate_limit_hits", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS rate_limit_hits INTEGER DEFAULT 0"),
        ("search_logs", "meta_api_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS meta_api_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "scraper_api_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "web_avg_time", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS web_avg_time FLOAT DEFAULT 0"),
        ("search_logs", "scraper_api_cost", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_api_cost FLOAT DEFAULT 0"),
        ("search_logs", "api_details", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS api_details TEXT"),
        ("search_logs", "errors_list", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS errors_list TEXT"),
        ("search_logs", "scraper_errors_by_type", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS scraper_errors_by_type TEXT"),
        # Comptage new vs existing pour Search Logs
        ("search_logs", "new_pages_count", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS new_pages_count INTEGER DEFAULT 0"),
        ("search_logs", "existing_pages_updated", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS existing_pages_updated INTEGER DEFAULT 0"),
        ("search_logs", "new_winning_ads_count", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS new_winning_ads_count INTEGER DEFAULT 0"),
        ("search_logs", "existing_winning_ads_updated", "ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS existing_winning_ads_updated INTEGER DEFAULT 0"),
        # Lien search_log pour pages et winning ads
        ("liste_page_recherche", "last_search_log_id", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS last_search_log_id INTEGER"),
        ("liste_page_recherche", "was_created_in_last_search", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS was_created_in_last_search BOOLEAN DEFAULT TRUE"),
        ("winning_ads", "search_log_id", "ALTER TABLE winning_ads ADD COLUMN IF NOT EXISTS search_log_id INTEGER"),
        ("winning_ads", "is_new", "ALTER TABLE winning_ads ADD COLUMN IF NOT EXISTS is_new BOOLEAN DEFAULT TRUE"),
        # Colonnes classification pour PageRecherche
        ("liste_page_recherche", "subcategory", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100)"),
        ("liste_page_recherche", "classification_confidence", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS classification_confidence FLOAT"),
        ("liste_page_recherche", "classified_at", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS classified_at TIMESTAMP"),
        # Extension du champ pays pour multi-valeurs
        ("liste_page_recherche", "pays_resize", "ALTER TABLE liste_page_recherche ALTER COLUMN pays TYPE VARCHAR(255)"),
        # Données pour classification Gemini (évite re-scraping des sites)
        ("liste_page_recherche", "site_title", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_title VARCHAR(255)"),
        ("liste_page_recherche", "site_description", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_description TEXT"),
        ("liste_page_recherche", "site_h1", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_h1 VARCHAR(200)"),
        ("liste_page_recherche", "site_keywords", "ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS site_keywords VARCHAR(300)"),
        # Proxy URL pour tokens Meta
        ("meta_tokens", "proxy_url", "ALTER TABLE meta_tokens ADD COLUMN IF NOT EXISTS proxy_url VARCHAR(255)"),
        # Updated_at pour SearchQueue (suivi des recherches actives)
        ("search_queue", "updated_at", "ALTER TABLE search_queue ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"),
    ]

    # Index migrations (CREATE INDEX IF NOT EXISTS)
    index_migrations = [
        "CREATE INDEX IF NOT EXISTS idx_page_cms_etat ON liste_page_recherche (cms, etat)",
        "CREATE INDEX IF NOT EXISTS idx_page_etat_ads ON liste_page_recherche (etat, nombre_ads_active)",
        "CREATE INDEX IF NOT EXISTS idx_page_created ON liste_page_recherche (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_page_thematique ON liste_page_recherche (thematique)",
        "CREATE INDEX IF NOT EXISTS idx_winning_ads_page_date ON winning_ads (page_id, date_scan)",
        "CREATE INDEX IF NOT EXISTS idx_winning_ads_reach ON winning_ads (eu_total_reach)",
        "CREATE INDEX IF NOT EXISTS idx_search_log_status_date ON search_logs (status, started_at)",
        "CREATE INDEX IF NOT EXISTS idx_page_last_search ON liste_page_recherche (last_search_log_id)",
        "CREATE INDEX IF NOT EXISTS idx_winning_search ON winning_ads (search_log_id)",
    ]

    # Nettoyage des doublons winning_ads AVANT d'ajouter la contrainte unique
    # Garde l'entrée la plus récente (id le plus élevé) pour chaque ad_id
    cleanup_duplicates_sql = """
    DELETE FROM winning_ads
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM winning_ads
        GROUP BY ad_id
    )
    """

    # Contrainte unique sur ad_id (après nettoyage des doublons)
    unique_constraint_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_winning_ads_ad_id'
        ) THEN
            ALTER TABLE winning_ads ADD CONSTRAINT uq_winning_ads_ad_id UNIQUE (ad_id);
        END IF;
    END $$;
    """

    with db.get_session() as session:
        # Run column migrations
        for table, column, sql in migrations:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception as e:
                # Colonne existe déjà ou autre erreur non critique
                session.rollback()
                pass

        # Run index migrations
        for sql in index_migrations:
            try:
                session.execute(text(sql))
                session.commit()
            except Exception as e:
                # Index existe déjà ou autre erreur non critique
                session.rollback()
                pass

        # Nettoyage des doublons winning_ads
        try:
            result = session.execute(text(cleanup_duplicates_sql))
            deleted = result.rowcount
            session.commit()
            if deleted > 0:
                print(f"[Migration] Supprimé {deleted} doublons de winning_ads")
        except Exception as e:
            session.rollback()
            pass

        # Ajout contrainte unique sur ad_id
        try:
            session.execute(text(unique_constraint_sql))
            session.commit()
        except Exception as e:
            # Contrainte existe déjà
            session.rollback()
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def get_etat_from_ads_count(ads_count: int, thresholds: Dict = None) -> str:
    """
    Détermine l'état basé sur le nombre d'ads actives

    Args:
        ads_count: Nombre d'ads actives
        thresholds: Dictionnaire des seuils personnalisés (optionnel)
                   Format: {"XS": 1, "S": 10, "M": 20, "L": 35, "XL": 80, "XXL": 150}

    Returns:
        État: inactif, XS, S, M, L, XL, XXL
    """
    # Seuils par défaut
    if thresholds is None:
        thresholds = {
            "XS": 1,
            "S": 10,
            "M": 20,
            "L": 35,
            "XL": 80,
            "XXL": 150,
        }

    if ads_count == 0:
        return "inactif"
    elif ads_count < thresholds.get("S", 10):
        return "XS"
    elif ads_count < thresholds.get("M", 20):
        return "S"
    elif ads_count < thresholds.get("L", 35):
        return "M"
    elif ads_count < thresholds.get("XL", 80):
        return "L"
    elif ads_count < thresholds.get("XXL", 150):
        return "XL"
    else:
        return "XXL"


def to_str_list(val: Any) -> str:
    """Convertit une valeur en chaîne (pour les listes)"""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val) if val else ""


# ═══════════════════════════════════════════════════════════════════════════════
# APP SETTINGS (paramètres persistants)
# ═══════════════════════════════════════════════════════════════════════════════

def get_app_setting(db: DatabaseManager, key: str, default: str = None) -> Optional[str]:
    """
    Récupère un paramètre de l'application.

    Args:
        db: Instance DatabaseManager
        key: Clé du paramètre
        default: Valeur par défaut si non trouvé

    Returns:
        Valeur du paramètre ou default
    """
    with db.get_session() as session:
        setting = session.query(AppSettings).filter(AppSettings.key == key).first()
        if setting:
            return setting.value
        return default


def set_app_setting(db: DatabaseManager, key: str, value: str, description: str = None) -> bool:
    """
    Définit ou met à jour un paramètre de l'application.

    Args:
        db: Instance DatabaseManager
        key: Clé du paramètre
        value: Valeur à stocker
        description: Description du paramètre (optionnel)

    Returns:
        True si succès
    """
    with db.get_session() as session:
        setting = session.query(AppSettings).filter(AppSettings.key == key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
            setting.updated_at = datetime.utcnow()
        else:
            setting = AppSettings(
                key=key,
                value=value,
                description=description
            )
            session.add(setting)
        return True


def get_all_app_settings(db: DatabaseManager) -> Dict[str, str]:
    """Récupère tous les paramètres de l'application"""
    with db.get_session() as session:
        settings = session.query(AppSettings).all()
        return {s.key: s.value for s in settings}


# Constantes pour les clés de paramètres
SETTING_GEMINI_MODEL = "gemini_model_name"
SETTING_GEMINI_MODEL_DEFAULT = "gemini-1.5-flash"


# ═══════════════════════════════════════════════════════════════════════════════
# OPÉRATIONS CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def save_pages_recherche(
    db: DatabaseManager,
    pages_final: Dict,
    web_results: Dict,
    countries: List[str],
    languages: List[str],
    thresholds: Dict = None,
    search_log_id: int = None
) -> int:
    """
    Sauvegarde ou met à jour les pages dans liste_page_recherche
    Si une page existe déjà, on ajoute les keywords s'ils ne sont pas déjà présents

    Args:
        db: Instance DatabaseManager
        pages_final: Dictionnaire des pages (avec _keywords set pour chaque page)
        web_results: Résultats d'analyse web
        countries: Liste des pays
        languages: Liste des langues
        thresholds: Seuils personnalisés pour les états (optionnel)
        search_log_id: ID du SearchLog pour tracer l'origine (optionnel)

    Returns:
        Nombre de pages sauvegardées (ou tuple (total, new, existing) si search_log_id fourni)
    """
    scan_time = datetime.utcnow()
    count = 0
    new_count = 0
    existing_count = 0
    new_page_ids = []
    existing_page_ids = []

    with db.get_session() as session:
        for pid, data in pages_final.items():
            web = web_results.get(pid, {})
            ads_count = data.get("ads_active_total", 0)

            # Keywords de cette recherche (set -> liste)
            new_keywords = data.get("_keywords", set())
            if isinstance(new_keywords, set):
                new_keywords = list(new_keywords)

            fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"

            # Vérifier si la page existe déjà
            existing_page = session.query(PageRecherche).filter(
                PageRecherche.page_id == str(pid)
            ).first()

            if existing_page:
                # La page existe - mise à jour avec ajout des keywords
                existing_keywords_str = existing_page.keywords or ""
                existing_keywords_list = [k.strip() for k in existing_keywords_str.split("|") if k.strip()]

                # Ajouter les nouveaux keywords s'ils ne sont pas déjà présents
                for kw in new_keywords:
                    if kw and kw not in existing_keywords_list:
                        existing_keywords_list.append(kw)

                merged_keywords = " | ".join(existing_keywords_list)

                # Merge des pays (ajouter les nouveaux sans supprimer les anciens)
                existing_pays_str = existing_page.pays or ""
                existing_pays_list = [c.strip().upper() for c in existing_pays_str.split(",") if c.strip()]
                for c in countries:
                    c_upper = c.upper().strip()
                    if c_upper and c_upper not in existing_pays_list:
                        existing_pays_list.append(c_upper)
                merged_pays = ",".join(existing_pays_list)

                # Merge des langues (ajouter les nouvelles sans supprimer les anciennes)
                existing_lang_str = existing_page.langue or ""
                existing_lang_list = [l.strip() for l in existing_lang_str.split(",") if l.strip()]
                for lang in languages:
                    if lang and lang not in existing_lang_list:
                        existing_lang_list.append(lang)
                merged_langues = ",".join(existing_lang_list)

                # Mise à jour des champs
                existing_page.page_name = data.get("page_name", "") or existing_page.page_name
                existing_page.lien_site = data.get("website", "") or existing_page.lien_site
                existing_page.lien_fb_ad_library = fb_link
                existing_page.keywords = merged_keywords
                # Classification Gemini prioritaire, sinon classification basique
                if web.get("gemini_category"):
                    existing_page.thematique = web.get("gemini_category", "")
                    existing_page.subcategory = web.get("gemini_subcategory", "")
                    existing_page.classification_confidence = web.get("gemini_confidence", 0.0)
                    existing_page.classified_at = scan_time
                else:
                    existing_page.thematique = web.get("thematique", "") or existing_page.thematique
                existing_page.type_produits = web.get("type_produits", "") or existing_page.type_produits
                existing_page.moyens_paiements = web.get("payments", "") or existing_page.moyens_paiements
                existing_page.pays = merged_pays
                existing_page.langue = merged_langues
                existing_page.cms = data.get("cms") or web.get("cms", "") or existing_page.cms
                existing_page.template = web.get("theme", "") or existing_page.template
                existing_page.devise = data.get("currency", "") or existing_page.devise
                existing_page.etat = get_etat_from_ads_count(ads_count, thresholds)
                existing_page.nombre_ads_active = ads_count
                existing_page.nombre_produits = web.get("product_count", 0) or existing_page.nombre_produits
                existing_page.dernier_scan = scan_time
                existing_page.updated_at = scan_time
                # Données pour classification Gemini (évite re-scraping)
                if web.get("site_title"):
                    existing_page.site_title = web.get("site_title", "")[:255]
                if web.get("site_description"):
                    existing_page.site_description = web.get("site_description", "")
                if web.get("site_h1"):
                    existing_page.site_h1 = web.get("site_h1", "")[:200]
                if web.get("site_keywords"):
                    existing_page.site_keywords = web.get("site_keywords", "")[:300]
                # Tracking recherche
                if search_log_id:
                    existing_page.last_search_log_id = search_log_id
                    existing_page.was_created_in_last_search = False
                existing_count += 1
                existing_page_ids.append(str(pid))
            else:
                # Nouvelle page - insertion
                keywords_str = " | ".join(new_keywords) if new_keywords else ""
                pays_str = ",".join([c.upper().strip() for c in countries if c])

                # Classification Gemini prioritaire, sinon classification basique
                thematique_val = web.get("gemini_category") or web.get("thematique", "")
                subcategory_val = web.get("gemini_subcategory", "")
                confidence_val = web.get("gemini_confidence", 0.0) if web.get("gemini_category") else None
                classified_at_val = scan_time if web.get("gemini_category") else None

                new_page = PageRecherche(
                    page_id=str(pid),
                    page_name=data.get("page_name", ""),
                    lien_site=data.get("website", ""),
                    lien_fb_ad_library=fb_link,
                    keywords=keywords_str,
                    thematique=thematique_val,
                    subcategory=subcategory_val,
                    classification_confidence=confidence_val,
                    classified_at=classified_at_val,
                    type_produits=web.get("type_produits", ""),
                    moyens_paiements=web.get("payments", ""),
                    pays=pays_str,
                    langue=",".join(languages),
                    cms=data.get("cms") or web.get("cms", "Unknown"),
                    template=web.get("theme", ""),
                    devise=data.get("currency", ""),
                    etat=get_etat_from_ads_count(ads_count, thresholds),
                    nombre_ads_active=ads_count,
                    nombre_produits=web.get("product_count", 0),
                    dernier_scan=scan_time,
                    created_at=scan_time,
                    updated_at=scan_time,
                    last_search_log_id=search_log_id,
                    was_created_in_last_search=True,
                    # Données pour classification Gemini (cache pour futures recherches)
                    site_title=web.get("site_title", "")[:255] if web.get("site_title") else None,
                    site_description=web.get("site_description", ""),
                    site_h1=web.get("site_h1", "")[:200] if web.get("site_h1") else None,
                    site_keywords=web.get("site_keywords", "")[:300] if web.get("site_keywords") else None,
                )
                session.add(new_page)
                new_count += 1
                new_page_ids.append(str(pid))

            count += 1

    # Log détaillé avec IDs
    print(f"[DB] Pages sauvées: {count} total")
    print(f"   🆕 Nouvelles ({new_count}):")
    for pid in new_page_ids[:10]:
        print(f"      → {pid}")
    if len(new_page_ids) > 10:
        print(f"      ... et {len(new_page_ids) - 10} autres")

    print(f"   📝 Doublons/mises à jour ({existing_count}):")
    for pid in existing_page_ids[:10]:
        print(f"      → {pid}")
    if len(existing_page_ids) > 10:
        print(f"      ... et {len(existing_page_ids) - 10} autres")

    # Retourner tuple (total, new, existing)
    return (count, new_count, existing_count)


def save_suivi_page(
    db: DatabaseManager,
    pages_final: Dict,
    web_results: Dict,
    min_ads: int = 10
) -> int:
    """
    Sauvegarde l'historique des pages dans suivi_page

    Args:
        db: Instance DatabaseManager
        pages_final: Dictionnaire des pages
        web_results: Résultats d'analyse web
        min_ads: Nombre minimum d'ads pour être inclus

    Returns:
        Nombre d'entrées créées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_final.items():
            ads_count = data.get("ads_active_total", 0)

            if ads_count < min_ads:
                continue

            web = web_results.get(pid, {})

            suivi = SuiviPage(
                cle_suivi="",
                page_id=str(pid),
                nom_site=data.get("page_name", ""),
                nombre_ads_active=ads_count,
                nombre_produits=web.get("product_count", 0),
                date_scan=scan_time
            )
            session.add(suivi)
            count += 1

    return count


def save_ads_recherche(
    db: DatabaseManager,
    pages_for_ads: Dict,
    page_ads: Dict,
    countries: List[str],
    min_ads: int = 20
) -> int:
    """
    Sauvegarde les annonces dans liste_ads_recherche

    Args:
        db: Instance DatabaseManager
        pages_for_ads: Pages avec assez d'ads
        page_ads: Dictionnaire des annonces par page
        countries: Liste des pays
        min_ads: Nombre minimum d'ads pour être inclus

    Returns:
        Nombre d'annonces sauvegardées
    """
    scan_time = datetime.utcnow()
    count = 0

    with db.get_session() as session:
        for pid, data in pages_for_ads.items():
            if data.get("ads_active_total", 0) < min_ads:
                continue

            for ad in page_ads.get(pid, []):
                ad_creation = None
                if ad.get("ad_creation_time"):
                    try:
                        ad_creation = datetime.fromisoformat(
                            ad["ad_creation_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                ads_entry = AdsRecherche(
                    ad_id=str(ad.get("id", "")),
                    page_id=str(pid),
                    page_name=ad.get("page_name", ""),
                    ad_creation_time=ad_creation,
                    ad_creative_bodies=to_str_list(ad.get("ad_creative_bodies")),
                    ad_creative_link_captions=to_str_list(ad.get("ad_creative_link_captions")),
                    ad_creative_link_titles=to_str_list(ad.get("ad_creative_link_titles")),
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    eu_total_reach=str(ad.get("eu_total_reach", "")),
                    languages=to_str_list(ad.get("languages")),
                    country=",".join(countries),
                    publisher_platforms=to_str_list(ad.get("publisher_platforms")),
                    target_ages=str(ad.get("target_ages", "")),
                    target_gender=str(ad.get("target_gender", "")),
                    beneficiary_payers=to_str_list(ad.get("beneficiary_payers")),
                    date_scan=scan_time
                )
                session.add(ads_entry)
                count += 1

    return count


# ═══════════════════════════════════════════════════════════════════════════════
# REQUÊTES DE LECTURE
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_pages(db: DatabaseManager, limit: int = 1000) -> List[Dict]:
    """Récupère toutes les pages"""
    with db.get_session() as session:
        pages = session.query(PageRecherche).order_by(
            PageRecherche.nombre_ads_active.desc()
        ).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "lien_fb_ad_library": p.lien_fb_ad_library,
                "keywords": p.keywords,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "dernier_scan": p.dernier_scan.isoformat() if p.dernier_scan else ""
            }
            for p in pages
        ]


def get_page_history(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère l'historique d'une page"""
    with db.get_session() as session:
        entries = session.query(SuiviPage).filter(
            SuiviPage.page_id == page_id
        ).order_by(SuiviPage.date_scan.desc()).all()

        return [
            {
                "page_id": e.page_id,
                "nom_site": e.nom_site,
                "nombre_ads_active": e.nombre_ads_active,
                "nombre_produits": e.nombre_produits,
                "date_scan": e.date_scan.isoformat() if e.date_scan else ""
            }
            for e in entries
        ]


@cached(ttl=30, key_prefix="suivi_")
def get_suivi_stats(db: DatabaseManager) -> Dict:
    """Récupère les statistiques de suivi (cached 30s)"""
    with db.get_session() as session:
        # Nombre total de pages suivies
        total_pages = session.query(PageRecherche).count()

        # Répartition par état
        from sqlalchemy import func
        etats = session.query(
            PageRecherche.etat,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.etat).all()

        # Répartition par CMS
        cms_stats = session.query(
            PageRecherche.cms,
            func.count(PageRecherche.id)
        ).group_by(PageRecherche.cms).all()

        return {
            "total_pages": total_pages,
            "etats": {e[0]: e[1] for e in etats},
            "cms": {c[0]: c[1] for c in cms_stats}
        }


def get_suivi_stats_filtered(
    db: DatabaseManager,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None
) -> Dict:
    """
    Récupère les statistiques de suivi avec filtres de classification.

    Args:
        db: DatabaseManager
        thematique: Filtrer par catégorie principale
        subcategory: Filtrer par sous-catégorie
        pays: Filtrer par pays (recherche dans champ multi-valeurs)

    Returns:
        Dict avec total_pages, etats, cms
    """
    from sqlalchemy import func

    with db.get_session() as session:
        # Base query
        query = session.query(PageRecherche)

        # Appliquer les filtres
        if thematique:
            query = query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            query = query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))

        # Nombre total de pages filtrées
        total_pages = query.count()

        # Répartition par état (avec filtres)
        etat_query = session.query(
            PageRecherche.etat,
            func.count(PageRecherche.id)
        )
        if thematique:
            etat_query = etat_query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            etat_query = etat_query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            etat_query = etat_query.filter(PageRecherche.pays.ilike(f"%{pays}%"))
        etats = etat_query.group_by(PageRecherche.etat).all()

        # Répartition par CMS (avec filtres)
        cms_query = session.query(
            PageRecherche.cms,
            func.count(PageRecherche.id)
        )
        if thematique:
            cms_query = cms_query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            cms_query = cms_query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            cms_query = cms_query.filter(PageRecherche.pays.ilike(f"%{pays}%"))
        cms_stats = cms_query.group_by(PageRecherche.cms).all()

        return {
            "total_pages": total_pages,
            "etats": {e[0]: e[1] for e in etats if e[0]},
            "cms": {c[0]: c[1] for c in cms_stats if c[0]}
        }


@cached(ttl=60, key_prefix="trends_")
def get_dashboard_trends(db: DatabaseManager, days: int = 7) -> Dict:
    """
    Calcule les tendances en comparant la période actuelle avec la précédente (cached 60s).

    Args:
        db: Instance DatabaseManager
        days: Nombre de jours pour chaque période (défaut: 7)

    Returns:
        Dict avec les stats actuelles, précédentes et deltas
    """
    from datetime import timedelta
    from sqlalchemy import func

    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    with db.get_session() as session:
        # ═══ PAGES AJOUTÉES ═══
        # Pages ajoutées dans la période actuelle
        current_pages = session.query(PageRecherche).filter(
            PageRecherche.created_at >= current_start
        ).count()

        # Pages ajoutées dans la période précédente
        previous_pages = session.query(PageRecherche).filter(
            PageRecherche.created_at >= previous_start,
            PageRecherche.created_at < current_start
        ).count()

        # ═══ WINNING ADS ═══
        # Winning ads période actuelle
        current_winning = session.query(WinningAds).filter(
            WinningAds.date_scan >= current_start
        ).count()

        # Winning ads période précédente
        previous_winning = session.query(WinningAds).filter(
            WinningAds.date_scan >= previous_start,
            WinningAds.date_scan < current_start
        ).count()

        # ═══ RECHERCHES ═══
        # Recherches période actuelle
        current_searches = session.query(SearchLog).filter(
            SearchLog.started_at >= current_start
        ).count()

        # Recherches période précédente
        previous_searches = session.query(SearchLog).filter(
            SearchLog.started_at >= previous_start,
            SearchLog.started_at < current_start
        ).count()

        # ═══ EVOLUTION DES ÉTATS ═══
        # Compter les pages XXL actuellement
        xxl_current = session.query(PageRecherche).filter(
            PageRecherche.etat == "XXL"
        ).count()

        # Shopify actuellement
        shopify_current = session.query(PageRecherche).filter(
            PageRecherche.cms == "Shopify"
        ).count()

        # Total actif (non inactif)
        active_current = session.query(PageRecherche).filter(
            PageRecherche.etat != "inactif"
        ).count()

        # Pour les deltas d'état, on utilise l'historique de suivi
        # Compter les évolutions positives (pages montantes)
        evolution = get_evolution_stats(db, period_days=days)
        rising_count = len([e for e in evolution if e.get("pct_ads", 0) >= 20])
        falling_count = len([e for e in evolution if e.get("pct_ads", 0) <= -20])

        def calc_delta(current, previous):
            """Calcule le delta et le pourcentage de changement"""
            delta = current - previous
            if previous > 0:
                pct = ((current - previous) / previous) * 100
            elif current > 0:
                pct = 100  # De 0 à quelque chose = +100%
            else:
                pct = 0
            return delta, pct

        pages_delta, pages_pct = calc_delta(current_pages, previous_pages)
        winning_delta, winning_pct = calc_delta(current_winning, previous_winning)
        searches_delta, searches_pct = calc_delta(current_searches, previous_searches)

        return {
            "period_days": days,
            "pages": {
                "current": current_pages,
                "previous": previous_pages,
                "delta": pages_delta,
                "pct": pages_pct
            },
            "winning_ads": {
                "current": current_winning,
                "previous": previous_winning,
                "delta": winning_delta,
                "pct": winning_pct
            },
            "searches": {
                "current": current_searches,
                "previous": previous_searches,
                "delta": searches_delta,
                "pct": searches_pct
            },
            "totals": {
                "xxl": xxl_current,
                "shopify": shopify_current,
                "active": active_current
            },
            "evolution": {
                "rising": rising_count,
                "falling": falling_count
            }
        }


def get_suivi_history(
    db: DatabaseManager,
    page_id: str = None,
    limit: int = 100
) -> List[Dict]:
    """Récupère l'historique de suivi"""
    with db.get_session() as session:
        query = session.query(SuiviPage).order_by(SuiviPage.date_scan.desc())

        if page_id:
            query = query.filter(SuiviPage.page_id == page_id)

        entries = query.limit(limit).all()

        return [
            {
                "page_id": e.page_id,
                "nom_site": e.nom_site,
                "nombre_ads_active": e.nombre_ads_active,
                "nombre_produits": e.nombre_produits,
                "date_scan": e.date_scan
            }
            for e in entries
        ]


def search_pages(
    db: DatabaseManager,
    cms: str = None,
    etat: str = None,
    search_term: str = None,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None,
    page_id: str = None,
    days: int = None,
    limit: int = 100
) -> List[Dict]:
    """
    Recherche des pages avec filtres.

    Args:
        db: DatabaseManager
        cms: Filtre par CMS
        etat: Filtre par état (XS, S, M, L, XL, XXL)
        search_term: Recherche dans nom/site
        thematique: Filtre par catégorie principale
        subcategory: Filtre par sous-catégorie
        pays: Filtre par pays (ex: "FR", recherche dans le champ multi-valeurs)
        page_id: Filtre par page_id spécifique
        days: Filtre par période (derniers X jours)
        limit: Nombre max de résultats
    """
    from datetime import timedelta

    with db.get_session() as session:
        query = session.query(PageRecherche)

        if page_id:
            query = query.filter(PageRecherche.page_id == page_id)
        if cms:
            query = query.filter(PageRecherche.cms == cms)
        if etat:
            query = query.filter(PageRecherche.etat == etat)
        if search_term:
            query = query.filter(
                PageRecherche.page_name.ilike(f"%{search_term}%") |
                PageRecherche.lien_site.ilike(f"%{search_term}%")
            )
        if thematique:
            if thematique == "__unclassified__":
                # Pages non classifiées
                query = query.filter(
                    (PageRecherche.thematique == None) | (PageRecherche.thematique == "")
                )
            else:
                query = query.filter(PageRecherche.thematique == thematique)
        if subcategory:
            query = query.filter(PageRecherche.subcategory == subcategory)
        if pays:
            # Le champ pays est multi-valeurs "FR,DE,ES", on cherche avec LIKE
            query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PageRecherche.dernier_scan >= cutoff)

        pages = query.order_by(
            PageRecherche.nombre_ads_active.desc()
        ).limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "lien_fb_ad_library": p.lien_fb_ad_library,
                "keywords": p.keywords,
                "cms": p.cms,
                "etat": p.etat,
                "nombre_ads_active": p.nombre_ads_active,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "subcategory": p.subcategory,
                "classification_confidence": p.classification_confidence,
                "pays": p.pays,
                "template": p.template,
                "devise": p.devise,
                "dernier_scan": p.dernier_scan,
                "updated_at": p.updated_at
            }
            for p in pages
        ]


def add_country_to_page(db: DatabaseManager, page_id: str, country: str) -> bool:
    """
    Ajoute un pays à une page (si pas déjà présent).

    Args:
        db: DatabaseManager
        page_id: ID de la page
        country: Code pays (ex: "FR", "DE")

    Returns:
        True si ajouté, False si déjà présent ou erreur
    """
    if not country:
        return False

    country = country.upper().strip()

    with db.get_session() as session:
        page = session.query(PageRecherche).filter(
            PageRecherche.page_id == page_id
        ).first()

        if not page:
            return False

        # Parser les pays existants
        existing_countries = []
        if page.pays:
            existing_countries = [c.strip() for c in page.pays.split(",") if c.strip()]

        # Vérifier si déjà présent
        if country in existing_countries:
            return False

        # Ajouter le nouveau pays
        existing_countries.append(country)
        page.pays = ",".join(existing_countries)

        return True


def add_countries_to_pages_batch(
    db: DatabaseManager,
    page_ids: List[str],
    country: str
) -> int:
    """
    Ajoute un pays à plusieurs pages en batch.

    Args:
        db: DatabaseManager
        page_ids: Liste des IDs de pages
        country: Code pays à ajouter

    Returns:
        Nombre de pages mises à jour
    """
    if not country or not page_ids:
        return 0

    country = country.upper().strip()
    updated = 0

    with db.get_session() as session:
        pages = session.query(PageRecherche).filter(
            PageRecherche.page_id.in_(page_ids)
        ).all()

        for page in pages:
            existing_countries = []
            if page.pays:
                existing_countries = [c.strip() for c in page.pays.split(",") if c.strip()]

            if country not in existing_countries:
                existing_countries.append(country)
                page.pays = ",".join(existing_countries)
                updated += 1

    return updated


def get_all_countries(db: DatabaseManager) -> List[str]:
    """
    Récupère tous les pays uniques présents dans la base.

    Returns:
        Liste de codes pays triés (ex: ["DE", "ES", "FR"])
    """
    with db.get_session() as session:
        pages = session.query(PageRecherche.pays).filter(
            PageRecherche.pays != None,
            PageRecherche.pays != ""
        ).distinct().all()

        all_countries = set()
        for (pays_str,) in pages:
            if pays_str:
                for c in pays_str.split(","):
                    c = c.strip().upper()
                    if c:
                        all_countries.add(c)

        return sorted(list(all_countries))


def get_all_subcategories(db: DatabaseManager, category: str = None) -> List[str]:
    """
    Récupère toutes les sous-catégories de la taxonomie.

    Args:
        db: DatabaseManager
        category: Filtrer par catégorie parente (optionnel)

    Returns:
        Liste de sous-catégories triées
    """
    with db.get_session() as session:
        query = session.query(ClassificationTaxonomy.subcategory).filter(
            ClassificationTaxonomy.is_active == True
        )

        if category:
            query = query.filter(ClassificationTaxonomy.category == category)

        results = query.distinct().order_by(ClassificationTaxonomy.subcategory).all()
        return [r[0] for r in results]


def get_cached_pages_info(
    db: DatabaseManager,
    page_ids: List[str],
    cache_days: int = 4
) -> Dict[str, Dict]:
    """
    Récupère les infos en cache pour les pages récemment scannées.

    Args:
        db: Instance DatabaseManager
        page_ids: Liste des page_ids à vérifier
        cache_days: Nombre de jours avant expiration du cache

    Returns:
        Dict {page_id: {cms, lien_site, nombre_produits, dernier_scan, needs_rescan}}
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=cache_days)

    with db.get_session() as session:
        pages = session.query(PageRecherche).filter(
            PageRecherche.page_id.in_(page_ids)
        ).all()

        result = {}
        for p in pages:
            # Vérifier si le scan est encore valide
            needs_rescan = True
            if p.dernier_scan and p.dernier_scan > cutoff:
                needs_rescan = False

            result[str(p.page_id)] = {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "lien_site": p.lien_site,
                "cms": p.cms,
                "template": p.template,
                "nombre_produits": p.nombre_produits,
                "thematique": p.thematique,
                "devise": p.devise,
                "dernier_scan": p.dernier_scan,
                "needs_rescan": needs_rescan,
                "needs_cms_detection": not p.cms or p.cms in ("Unknown", "Inconnu", ""),
                # Données pour classification Gemini (évite re-scraping)
                "site_title": p.site_title or "",
                "site_description": p.site_description or "",
                "site_h1": p.site_h1 or "",
                "site_keywords": p.site_keywords or "",
            }

        return result


def get_evolution_stats(
    db: DatabaseManager,
    period_days: int = 7
) -> List[Dict]:
    """
    Récupère les statistiques d'évolution des pages depuis le dernier scan

    Args:
        db: Instance DatabaseManager
        period_days: Nombre de jours pour la période (7, 14, 30)

    Returns:
        Liste des évolutions avec delta ads/produits et durée entre scans
    """
    from datetime import timedelta
    from sqlalchemy import func, desc

    cutoff_date = datetime.utcnow() - timedelta(days=period_days)

    with db.get_session() as session:
        # Récupérer les pages avec au moins 2 entrées dans suivi_page
        subquery = session.query(
            SuiviPage.page_id,
            func.count(SuiviPage.id).label('scan_count')
        ).filter(
            SuiviPage.date_scan >= cutoff_date
        ).group_by(SuiviPage.page_id).having(
            func.count(SuiviPage.id) >= 2
        ).subquery()

        # Pour chaque page, récupérer les 2 derniers scans
        results = []

        page_ids = session.query(subquery.c.page_id).all()

        for (page_id,) in page_ids:
            # Récupérer les 2 derniers scans pour cette page
            scans = session.query(SuiviPage).filter(
                SuiviPage.page_id == page_id
            ).order_by(desc(SuiviPage.date_scan)).limit(2).all()

            if len(scans) >= 2:
                current = scans[0]
                previous = scans[1]

                # Calculer la durée entre les scans
                duration = current.date_scan - previous.date_scan
                duration_hours = duration.total_seconds() / 3600

                # Calculer les deltas
                delta_ads = current.nombre_ads_active - previous.nombre_ads_active
                delta_produits = current.nombre_produits - previous.nombre_produits

                # Calculer le % de changement
                pct_ads = (delta_ads / previous.nombre_ads_active * 100) if previous.nombre_ads_active > 0 else 0
                pct_produits = (delta_produits / previous.nombre_produits * 100) if previous.nombre_produits > 0 else 0

                results.append({
                    "page_id": page_id,
                    "nom_site": current.nom_site,
                    "ads_actuel": current.nombre_ads_active,
                    "ads_precedent": previous.nombre_ads_active,
                    "delta_ads": delta_ads,
                    "pct_ads": round(pct_ads, 1),
                    "produits_actuel": current.nombre_produits,
                    "produits_precedent": previous.nombre_produits,
                    "delta_produits": delta_produits,
                    "pct_produits": round(pct_produits, 1),
                    "date_actuel": current.date_scan,
                    "date_precedent": previous.date_scan,
                    "duree_heures": round(duration_hours, 1),
                    "duree_jours": round(duration_hours / 24, 1)
                })

        # Trier par delta ads décroissant (les plus gros changements en premier)
        results.sort(key=lambda x: abs(x["delta_ads"]), reverse=True)

        return results


def get_page_evolution_history(
    db: DatabaseManager,
    page_id: str,
    limit: int = 50
) -> List[Dict]:
    """
    Récupère l'historique complet d'évolution d'une page

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page
        limit: Nombre max d'entrées

    Returns:
        Liste des scans avec évolution
    """
    from sqlalchemy import desc

    with db.get_session() as session:
        scans = session.query(SuiviPage).filter(
            SuiviPage.page_id == page_id
        ).order_by(desc(SuiviPage.date_scan)).limit(limit).all()

        results = []
        for i, scan in enumerate(scans):
            entry = {
                "date_scan": scan.date_scan,
                "nombre_ads_active": scan.nombre_ads_active,
                "nombre_produits": scan.nombre_produits,
                "delta_ads": 0,
                "delta_produits": 0
            }

            # Calculer le delta par rapport au scan précédent
            if i < len(scans) - 1:
                prev = scans[i + 1]
                entry["delta_ads"] = scan.nombre_ads_active - prev.nombre_ads_active
                entry["delta_produits"] = scan.nombre_produits - prev.nombre_produits

            results.append(entry)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════

def add_to_blacklist(
    db: DatabaseManager,
    page_id: str,
    page_name: str = "",
    raison: str = ""
) -> bool:
    """
    Ajoute une page à la blacklist

    Args:
        db: Instance DatabaseManager
        page_id: ID de la page
        page_name: Nom de la page
        raison: Raison de la mise en blacklist

    Returns:
        True si ajouté, False si déjà présent
    """
    with db.get_session() as session:
        # Vérifier si déjà présent
        existing = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()

        if existing:
            return False

        entry = Blacklist(
            page_id=str(page_id),
            page_name=page_name,
            raison=raison,
            added_at=datetime.utcnow()
        )
        session.add(entry)
        return True


def remove_from_blacklist(db: DatabaseManager, page_id: str) -> bool:
    """
    Retire une page de la blacklist

    Returns:
        True si retiré, False si non trouvé
    """
    with db.get_session() as session:
        entry = session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first()

        if entry:
            session.delete(entry)
            return True
        return False


def get_blacklist(db: DatabaseManager) -> List[Dict]:
    """Récupère toute la blacklist"""
    with db.get_session() as session:
        entries = session.query(Blacklist).order_by(
            Blacklist.added_at.desc()
        ).all()

        return [
            {
                "page_id": e.page_id,
                "page_name": e.page_name,
                "raison": e.raison,
                "added_at": e.added_at
            }
            for e in entries
        ]


def is_in_blacklist(db: DatabaseManager, page_id: str) -> bool:
    """Vérifie si une page est dans la blacklist"""
    with db.get_session() as session:
        return session.query(Blacklist).filter(
            Blacklist.page_id == str(page_id)
        ).first() is not None


def get_blacklist_ids(db: DatabaseManager) -> set:
    """Récupère tous les page_id de la blacklist"""
    with db.get_session() as session:
        entries = session.query(Blacklist.page_id).all()
        return {e.page_id for e in entries}


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DES WINNING ADS
# ═══════════════════════════════════════════════════════════════════════════════

def is_winning_ad(
    ad: Dict,
    scan_date: datetime,
    criteria: List = None
) -> tuple:
    """
    Vérifie si une annonce est une "winning ad" basé sur reach + âge

    Args:
        ad: Dictionnaire de l'annonce
        scan_date: Date du scan (pour calculer l'âge)
        criteria: Liste de tuples (max_age_days, min_reach) - optionnel

    Returns:
        Tuple (is_winning, age_days, reach, matched_criteria_str)
    """
    # Critères par défaut
    if criteria is None:
        criteria = [
            (4, 15000), (5, 20000), (6, 30000), (7, 40000),
            (8, 50000), (15, 100000), (22, 200000), (29, 400000)
        ]

    # Extraire le reach
    reach_raw = ad.get("eu_total_reach")
    if not reach_raw:
        return (False, None, None, None)

    # Parser le reach (peut être un dict avec lower_bound/upper_bound ou un int)
    if isinstance(reach_raw, dict):
        reach = reach_raw.get("lower_bound", 0)
    elif isinstance(reach_raw, str):
        try:
            reach = int(reach_raw.replace(",", "").replace(" ", ""))
        except (ValueError, AttributeError):
            return (False, None, None, None)
    else:
        try:
            reach = int(reach_raw)
        except (ValueError, TypeError):
            return (False, None, None, None)

    if reach <= 0:
        return (False, None, reach, None)

    # Calculer l'âge de l'ad
    ad_creation = ad.get("ad_creation_time")
    if not ad_creation:
        return (False, None, reach, None)

    # Parser la date de création
    if isinstance(ad_creation, str):
        try:
            ad_creation = datetime.fromisoformat(ad_creation.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return (False, None, reach, None)

    # Calculer l'âge en jours
    if ad_creation.tzinfo is not None:
        # Si ad_creation a un timezone, on enlève pour comparaison
        ad_creation = ad_creation.replace(tzinfo=None)

    age_days = (scan_date - ad_creation).days

    if age_days < 0:
        return (False, age_days, reach, None)

    # Vérifier les critères
    for max_age, min_reach in criteria:
        if age_days <= max_age and reach > min_reach:
            criteria_str = f"≤{max_age}d & >{min_reach // 1000}k"
            return (True, age_days, reach, criteria_str)

    return (False, age_days, reach, None)


def save_winning_ads(
    db: DatabaseManager,
    winning_ads_data: List[Dict],
    pages_final: Dict = None,
    search_log_id: int = None
) -> tuple:
    """
    Sauvegarde les winning ads dans la base de données.
    Si une ad existe déjà, met à jour ses données au lieu de créer un doublon.

    Args:
        db: Instance DatabaseManager
        winning_ads_data: Liste de dictionnaires avec les données des winning ads
        pages_final: Dictionnaire des pages (optionnel, pour récupérer le website)
        search_log_id: ID du SearchLog pour tracer l'origine (optionnel)

    Returns:
        Tuple (nombre nouvelles, nombre mises à jour)
    """
    if not winning_ads_data:
        return (0, 0)

    # Dédupliquer les données d'entrée (garder la première occurrence de chaque ad_id)
    seen_ad_ids = set()
    deduplicated_data = []
    for data in winning_ads_data:
        ad = data.get("ad", {})
        ad_id = str(ad.get("id", ""))
        if ad_id and ad_id not in seen_ad_ids:
            seen_ad_ids.add(ad_id)
            deduplicated_data.append(data)

    scan_time = datetime.utcnow()
    new_count = 0
    updated_count = 0
    new_ad_ids = []
    updated_ad_ids = []

    with db.get_session() as session:
        for data in deduplicated_data:
            ad = data.get("ad", {})
            ad_id = str(ad.get("id", ""))

            if not ad_id:
                continue

            page_id = str(data.get("page_id", ad.get("page_id", "")))

            # Récupérer le website depuis pages_final si disponible
            website = ""
            if pages_final and page_id in pages_final:
                website = pages_final[page_id].get("website", "")

            # Parser ad_creation_time
            ad_creation = None
            if ad.get("ad_creation_time"):
                try:
                    ad_creation = datetime.fromisoformat(
                        ad["ad_creation_time"].replace("Z", "+00:00")
                    )
                    if ad_creation.tzinfo is not None:
                        ad_creation = ad_creation.replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            # Vérifier si l'ad existe déjà
            existing = session.query(WinningAds).filter(WinningAds.ad_id == ad_id).first()

            if existing:
                # Mettre à jour l'ad existante
                existing.page_id = page_id
                existing.page_name = ad.get("page_name", existing.page_name)
                existing.ad_creation_time = ad_creation or existing.ad_creation_time
                existing.ad_age_days = data.get("age_days", existing.ad_age_days)
                existing.eu_total_reach = data.get("reach", existing.eu_total_reach)
                existing.matched_criteria = data.get("matched_criteria", existing.matched_criteria)
                existing.ad_creative_bodies = to_str_list(ad.get("ad_creative_bodies")) or existing.ad_creative_bodies
                existing.ad_creative_link_captions = to_str_list(ad.get("ad_creative_link_captions")) or existing.ad_creative_link_captions
                existing.ad_creative_link_titles = to_str_list(ad.get("ad_creative_link_titles")) or existing.ad_creative_link_titles
                existing.ad_snapshot_url = ad.get("ad_snapshot_url", existing.ad_snapshot_url)
                if website:
                    existing.lien_site = website
                existing.date_scan = scan_time  # Mettre à jour la date du scan
                # Tracking recherche
                if search_log_id:
                    existing.search_log_id = search_log_id
                    existing.is_new = False
                updated_count += 1
                updated_ad_ids.append(ad_id)
            else:
                # Créer une nouvelle entrée avec gestion des race conditions
                winning_entry = WinningAds(
                    ad_id=ad_id,
                    page_id=page_id,
                    page_name=ad.get("page_name", ""),
                    ad_creation_time=ad_creation,
                    ad_age_days=data.get("age_days"),
                    eu_total_reach=data.get("reach"),
                    matched_criteria=data.get("matched_criteria", ""),
                    ad_creative_bodies=to_str_list(ad.get("ad_creative_bodies")),
                    ad_creative_link_captions=to_str_list(ad.get("ad_creative_link_captions")),
                    ad_creative_link_titles=to_str_list(ad.get("ad_creative_link_titles")),
                    ad_snapshot_url=ad.get("ad_snapshot_url", ""),
                    lien_site=website,
                    date_scan=scan_time,
                    search_log_id=search_log_id,
                    is_new=True
                )
                try:
                    # Utiliser un savepoint pour ne pas annuler toute la transaction
                    with session.begin_nested():
                        session.add(winning_entry)
                        session.flush()
                    new_count += 1
                    new_ad_ids.append(ad_id)
                except IntegrityError:
                    # Race condition: l'ad a été insérée par un autre processus
                    # Le savepoint est automatiquement rollback, on fait une mise à jour
                    existing = session.query(WinningAds).filter(WinningAds.ad_id == ad_id).first()
                    if existing:
                        existing.page_id = page_id
                        existing.page_name = ad.get("page_name", existing.page_name)
                        existing.ad_creation_time = ad_creation or existing.ad_creation_time
                        existing.ad_age_days = data.get("age_days", existing.ad_age_days)
                        existing.eu_total_reach = data.get("reach", existing.eu_total_reach)
                        existing.date_scan = scan_time
                        if search_log_id:
                            existing.search_log_id = search_log_id
                            existing.is_new = False
                        updated_count += 1
                        updated_ad_ids.append(ad_id)

    # Log détaillé avec IDs
    print(f"[DB] Winning Ads sauvées:")
    print(f"   🆕 Nouvelles ({new_count}):")
    for aid in new_ad_ids[:10]:
        print(f"      → {aid}")
    if len(new_ad_ids) > 10:
        print(f"      ... et {len(new_ad_ids) - 10} autres")

    print(f"   🔄 Doublons/mises à jour ({updated_count}):")
    for aid in updated_ad_ids[:10]:
        print(f"      → {aid}")
    if len(updated_ad_ids) > 10:
        print(f"      ... et {len(updated_ad_ids) - 10} autres")

    return (new_count, updated_count)


def cleanup_duplicate_winning_ads(db: DatabaseManager) -> int:
    """
    Supprime les doublons de winning_ads (garde l'entrée la plus récente pour chaque ad_id).
    Utile pour la maintenance ou après une migration.

    Returns:
        Nombre de doublons supprimés
    """
    from sqlalchemy import text

    cleanup_sql = """
    DELETE FROM winning_ads
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM winning_ads
        GROUP BY ad_id
    )
    """

    with db.get_session() as session:
        try:
            result = session.execute(text(cleanup_sql))
            deleted = result.rowcount
            session.commit()
            return deleted
        except Exception as e:
            session.rollback()
            print(f"[cleanup_duplicate_winning_ads] Erreur: {e}")
            return 0


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS HISTORIQUE DE RECHERCHE (many-to-many)
# ═══════════════════════════════════════════════════════════════════════════════

def record_page_search_history(
    db: DatabaseManager,
    search_log_id: int,
    page_id: str,
    was_new: bool,
    ads_count: int = 0,
    keyword: str = None
) -> bool:
    """
    Enregistre qu'une page a été trouvée dans une recherche.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID de la recherche
        page_id: ID de la page
        was_new: True si la page était nouvelle lors de cette recherche
        ads_count: Nombre d'ads au moment de la découverte
        keyword: Mot-clé qui a trouvé la page
    """
    with db.get_session() as session:
        try:
            # Vérifier si déjà enregistré pour éviter les doublons
            existing = session.query(PageSearchHistory).filter(
                PageSearchHistory.search_log_id == search_log_id,
                PageSearchHistory.page_id == page_id
            ).first()

            if not existing:
                history = PageSearchHistory(
                    search_log_id=search_log_id,
                    page_id=str(page_id),
                    was_new=was_new,
                    ads_count_at_discovery=ads_count,
                    keyword_matched=keyword[:255] if keyword else None
                )
                session.add(history)
            return True
        except Exception as e:
            print(f"[record_page_search_history] Erreur: {e}")
            return False


def record_winning_ad_search_history(
    db: DatabaseManager,
    search_log_id: int,
    ad_id: str,
    was_new: bool,
    reach: int = 0,
    age_days: int = 0,
    matched_criteria: str = None
) -> bool:
    """
    Enregistre qu'une winning ad a été trouvée dans une recherche.
    """
    with db.get_session() as session:
        try:
            # Vérifier si déjà enregistré
            existing = session.query(WinningAdSearchHistory).filter(
                WinningAdSearchHistory.search_log_id == search_log_id,
                WinningAdSearchHistory.ad_id == ad_id
            ).first()

            if not existing:
                history = WinningAdSearchHistory(
                    search_log_id=search_log_id,
                    ad_id=str(ad_id),
                    was_new=was_new,
                    reach_at_discovery=reach,
                    age_days_at_discovery=age_days,
                    matched_criteria=matched_criteria[:100] if matched_criteria else None
                )
                session.add(history)
            return True
        except Exception as e:
            print(f"[record_winning_ad_search_history] Erreur: {e}")
            return False


def record_pages_search_history_batch(
    db: DatabaseManager,
    search_log_id: int,
    pages_data: List[Dict]
) -> int:
    """
    Enregistre plusieurs pages en batch pour une recherche.

    Args:
        pages_data: Liste de dicts avec {page_id, was_new, ads_count, keyword}

    Returns:
        Nombre d'entrées créées
    """
    if not pages_data:
        print(f"[record_pages_search_history_batch] Aucune page à enregistrer pour search #{search_log_id}")
        return 0

    print(f"[record_pages_search_history_batch] Enregistrement de {len(pages_data)} pages pour search #{search_log_id}")

    count = 0
    with db.get_session() as session:
        try:
            for data in pages_data:
                page_id = str(data.get("page_id", ""))
                if not page_id:
                    continue

                # Vérifier si déjà enregistré
                existing = session.query(PageSearchHistory).filter(
                    PageSearchHistory.search_log_id == search_log_id,
                    PageSearchHistory.page_id == page_id
                ).first()

                if not existing:
                    history = PageSearchHistory(
                        search_log_id=search_log_id,
                        page_id=page_id,
                        was_new=data.get("was_new", True),
                        ads_count_at_discovery=data.get("ads_count", 0),
                        keyword_matched=str(data.get("keyword", ""))[:255] if data.get("keyword") else None
                    )
                    session.add(history)
                    count += 1

            print(f"[record_pages_search_history_batch] {count} nouvelles entrées créées pour search #{search_log_id}")
            return count
        except Exception as e:
            print(f"[record_pages_search_history_batch] Erreur: {e}")
            import traceback
            traceback.print_exc()
            return count


def record_winning_ads_search_history_batch(
    db: DatabaseManager,
    search_log_id: int,
    ads_data: List[Dict]
) -> int:
    """
    Enregistre plusieurs winning ads en batch pour une recherche.

    Args:
        ads_data: Liste de dicts avec {ad_id, was_new, reach, age_days, matched_criteria}
    """
    if not ads_data:
        return 0

    count = 0
    with db.get_session() as session:
        try:
            for data in ads_data:
                ad_id = str(data.get("ad_id", ""))
                if not ad_id:
                    continue

                existing = session.query(WinningAdSearchHistory).filter(
                    WinningAdSearchHistory.search_log_id == search_log_id,
                    WinningAdSearchHistory.ad_id == ad_id
                ).first()

                if not existing:
                    history = WinningAdSearchHistory(
                        search_log_id=search_log_id,
                        ad_id=ad_id,
                        was_new=data.get("was_new", True),
                        reach_at_discovery=data.get("reach", 0),
                        age_days_at_discovery=data.get("age_days", 0),
                        matched_criteria=str(data.get("matched_criteria", ""))[:100] if data.get("matched_criteria") else None
                    )
                    session.add(history)
                    count += 1

            return count
        except Exception as e:
            print(f"[record_winning_ads_search_history_batch] Erreur: {e}")
            return count


def get_pages_for_search(
    db: DatabaseManager,
    search_log_id: int,
    limit: int = 500
) -> List[Dict]:
    """
    Récupère toutes les pages trouvées dans une recherche spécifique.
    Joint avec PageRecherche pour avoir les infos actuelles.
    """
    print(f"[get_pages_for_search] Recherche des pages pour search #{search_log_id}")

    with db.get_session() as session:
        try:
            # Vérifier d'abord combien d'entrées existent
            count = session.query(PageSearchHistory).filter(
                PageSearchHistory.search_log_id == search_log_id
            ).count()
            print(f"[get_pages_for_search] {count} entrées trouvées dans page_search_history pour search #{search_log_id}")

            # Query avec jointure
            results = session.query(
                PageSearchHistory,
                PageRecherche
            ).outerjoin(
                PageRecherche,
                PageSearchHistory.page_id == PageRecherche.page_id
            ).filter(
                PageSearchHistory.search_log_id == search_log_id
            ).order_by(
                PageSearchHistory.was_new.desc(),  # Nouvelles pages d'abord
                PageSearchHistory.ads_count_at_discovery.desc()
            ).limit(limit).all()

            pages = []
            for history, page in results:
                page_data = {
                    "page_id": history.page_id,
                    "was_new": history.was_new,
                    "found_at": history.found_at,
                    "ads_count_at_discovery": history.ads_count_at_discovery,
                    "keyword_matched": history.keyword_matched,
                }

                # Ajouter les infos actuelles de la page si elle existe
                if page:
                    page_data.update({
                        "page_name": page.page_name,
                        "lien_site": page.lien_site,
                        "cms": page.cms,
                        "etat": page.etat,
                        "nombre_ads_active": page.nombre_ads_active,
                        "thematique": page.thematique,
                        "pays": page.pays,
                    })
                else:
                    page_data.update({
                        "page_name": "[Supprimée]",
                        "lien_site": "",
                        "cms": "",
                        "etat": "",
                        "nombre_ads_active": 0,
                        "thematique": "",
                        "pays": "",
                    })

                pages.append(page_data)

            return pages
        except Exception as e:
            print(f"[get_pages_for_search] Erreur: {e}")
            return []


def get_winning_ads_for_search(
    db: DatabaseManager,
    search_log_id: int,
    limit: int = 500
) -> List[Dict]:
    """
    Récupère toutes les winning ads trouvées dans une recherche spécifique.
    Joint avec WinningAds pour avoir les infos actuelles.
    """
    with db.get_session() as session:
        try:
            results = session.query(
                WinningAdSearchHistory,
                WinningAds
            ).outerjoin(
                WinningAds,
                WinningAdSearchHistory.ad_id == WinningAds.ad_id
            ).filter(
                WinningAdSearchHistory.search_log_id == search_log_id
            ).order_by(
                WinningAdSearchHistory.was_new.desc(),
                WinningAdSearchHistory.reach_at_discovery.desc()
            ).limit(limit).all()

            ads = []
            for history, winning_ad in results:
                ad_data = {
                    "ad_id": history.ad_id,
                    "was_new": history.was_new,
                    "found_at": history.found_at,
                    "reach_at_discovery": history.reach_at_discovery,
                    "age_days_at_discovery": history.age_days_at_discovery,
                    "matched_criteria": history.matched_criteria,
                }

                if winning_ad:
                    ad_data.update({
                        "page_id": winning_ad.page_id,
                        "page_name": winning_ad.page_name,
                        "eu_total_reach": winning_ad.eu_total_reach,
                        "ad_age_days": winning_ad.ad_age_days,
                        "ad_snapshot_url": winning_ad.ad_snapshot_url,
                        "lien_site": winning_ad.lien_site,
                    })
                else:
                    ad_data.update({
                        "page_id": "",
                        "page_name": "[Supprimée]",
                        "eu_total_reach": 0,
                        "ad_age_days": 0,
                        "ad_snapshot_url": "",
                        "lien_site": "",
                    })

                ads.append(ad_data)

            return ads
        except Exception as e:
            print(f"[get_winning_ads_for_search] Erreur: {e}")
            return []


def get_searches_for_page(
    db: DatabaseManager,
    page_id: str,
    limit: int = 50
) -> List[Dict]:
    """
    Récupère l'historique de toutes les recherches ayant trouvé une page.
    """
    with db.get_session() as session:
        try:
            results = session.query(
                PageSearchHistory,
                SearchLog
            ).join(
                SearchLog,
                PageSearchHistory.search_log_id == SearchLog.id
            ).filter(
                PageSearchHistory.page_id == str(page_id)
            ).order_by(
                PageSearchHistory.found_at.desc()
            ).limit(limit).all()

            searches = []
            for history, search_log in results:
                searches.append({
                    "search_log_id": search_log.id,
                    "found_at": history.found_at,
                    "was_new": history.was_new,
                    "ads_count_at_discovery": history.ads_count_at_discovery,
                    "keyword_matched": history.keyword_matched,
                    "search_keywords": search_log.keywords,
                    "search_countries": search_log.countries,
                    "search_started_at": search_log.started_at,
                    "search_status": search_log.status,
                })

            return searches
        except Exception as e:
            print(f"[get_searches_for_page] Erreur: {e}")
            return []


def get_search_history_stats(
    db: DatabaseManager,
    search_log_id: int
) -> Dict:
    """
    Récupère les statistiques d'historique pour une recherche.
    """
    with db.get_session() as session:
        try:
            # Compter les pages
            total_pages = session.query(PageSearchHistory).filter(
                PageSearchHistory.search_log_id == search_log_id
            ).count()

            new_pages = session.query(PageSearchHistory).filter(
                PageSearchHistory.search_log_id == search_log_id,
                PageSearchHistory.was_new == True
            ).count()

            # Compter les winning ads
            total_winning = session.query(WinningAdSearchHistory).filter(
                WinningAdSearchHistory.search_log_id == search_log_id
            ).count()

            new_winning = session.query(WinningAdSearchHistory).filter(
                WinningAdSearchHistory.search_log_id == search_log_id,
                WinningAdSearchHistory.was_new == True
            ).count()

            return {
                "total_pages": total_pages,
                "new_pages": new_pages,
                "existing_pages": total_pages - new_pages,
                "total_winning_ads": total_winning,
                "new_winning_ads": new_winning,
                "existing_winning_ads": total_winning - new_winning,
            }
        except Exception as e:
            print(f"[get_search_history_stats] Erreur: {e}")
            return {
                "total_pages": 0, "new_pages": 0, "existing_pages": 0,
                "total_winning_ads": 0, "new_winning_ads": 0, "existing_winning_ads": 0
            }


def get_winning_ads(
    db: DatabaseManager,
    page_id: str = None,
    ad_id: str = None,
    limit: int = 100,
    days: int = None
) -> List[Dict]:
    """
    Récupère les winning ads depuis la base de données

    Args:
        db: Instance DatabaseManager
        page_id: Filtrer par page (optionnel)
        ad_id: Filtrer par ad_id (optionnel)
        limit: Nombre max de résultats
        days: Filtrer par période en jours (optionnel)

    Returns:
        Liste des winning ads
    """
    from datetime import timedelta

    with db.get_session() as session:
        query = session.query(WinningAds).order_by(
            WinningAds.date_scan.desc(),
            WinningAds.eu_total_reach.desc()
        )

        if page_id:
            query = query.filter(WinningAds.page_id == page_id)

        if ad_id:
            query = query.filter(WinningAds.ad_id == ad_id)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(WinningAds.date_scan >= cutoff)

        entries = query.limit(limit).all()

        return [
            {
                "ad_id": e.ad_id,
                "page_id": e.page_id,
                "page_name": e.page_name,
                "ad_creation_time": e.ad_creation_time,
                "ad_age_days": e.ad_age_days,
                "eu_total_reach": e.eu_total_reach,
                "matched_criteria": e.matched_criteria,
                "ad_creative_bodies": e.ad_creative_bodies,
                "ad_creative_link_captions": e.ad_creative_link_captions,
                "ad_creative_link_titles": e.ad_creative_link_titles,
                "ad_snapshot_url": e.ad_snapshot_url,
                "lien_site": e.lien_site,
                "date_scan": e.date_scan
            }
            for e in entries
        ]


def get_winning_ads_filtered(
    db: DatabaseManager,
    page_id: str = None,
    ad_id: str = None,
    limit: int = 100,
    days: int = None,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None
) -> List[Dict]:
    """
    Récupère les winning ads avec filtres de classification.

    Args:
        db: Instance DatabaseManager
        page_id: Filtrer par page (optionnel)
        ad_id: Filtrer par ad_id (optionnel)
        limit: Nombre max de résultats
        days: Filtrer par période en jours (optionnel)
        thematique: Filtrer par catégorie de la page
        subcategory: Filtrer par sous-catégorie de la page
        pays: Filtrer par pays de la page

    Returns:
        Liste des winning ads filtrées
    """
    from datetime import timedelta

    with db.get_session() as session:
        # Si des filtres de classification sont actifs, joindre avec PageRecherche
        if thematique or subcategory or pays:
            query = session.query(WinningAds).join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            )

            if thematique:
                query = query.filter(PageRecherche.thematique == thematique)
            if subcategory:
                query = query.filter(PageRecherche.subcategory == subcategory)
            if pays:
                query = query.filter(PageRecherche.pays.ilike(f"%{pays}%"))
        else:
            query = session.query(WinningAds)

        query = query.order_by(
            WinningAds.date_scan.desc(),
            WinningAds.eu_total_reach.desc()
        )

        if page_id:
            query = query.filter(WinningAds.page_id == page_id)

        if ad_id:
            query = query.filter(WinningAds.ad_id == ad_id)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(WinningAds.date_scan >= cutoff)

        entries = query.limit(limit).all()

        return [
            {
                "ad_id": e.ad_id,
                "page_id": e.page_id,
                "page_name": e.page_name,
                "ad_creation_time": e.ad_creation_time,
                "ad_age_days": e.ad_age_days,
                "eu_total_reach": e.eu_total_reach,
                "matched_criteria": e.matched_criteria,
                "ad_creative_bodies": e.ad_creative_bodies,
                "ad_creative_link_captions": e.ad_creative_link_captions,
                "ad_creative_link_titles": e.ad_creative_link_titles,
                "ad_snapshot_url": e.ad_snapshot_url,
                "lien_site": e.lien_site,
                "date_scan": e.date_scan
            }
            for e in entries
        ]


def get_winning_ads_stats_filtered(
    db: DatabaseManager,
    days: int = 30,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None
) -> Dict:
    """
    Récupère les statistiques des winning ads avec filtres.

    Args:
        db: DatabaseManager
        days: Période en jours
        thematique: Filtrer par catégorie
        subcategory: Filtrer par sous-catégorie
        pays: Filtrer par pays

    Returns:
        Dict avec les statistiques
    """
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Base query avec ou sans jointure
        if thematique or subcategory or pays:
            base_query = session.query(WinningAds).join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            ).filter(WinningAds.date_scan >= cutoff)

            if thematique:
                base_query = base_query.filter(PageRecherche.thematique == thematique)
            if subcategory:
                base_query = base_query.filter(PageRecherche.subcategory == subcategory)
            if pays:
                base_query = base_query.filter(PageRecherche.pays.ilike(f"%{pays}%"))

            total = base_query.count()

            # Unique pages
            unique_pages_count = session.query(
                func.count(func.distinct(WinningAds.page_id))
            ).join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            ).filter(WinningAds.date_scan >= cutoff)

            if thematique:
                unique_pages_count = unique_pages_count.filter(PageRecherche.thematique == thematique)
            if subcategory:
                unique_pages_count = unique_pages_count.filter(PageRecherche.subcategory == subcategory)
            if pays:
                unique_pages_count = unique_pages_count.filter(PageRecherche.pays.ilike(f"%{pays}%"))

            unique_pages_count = unique_pages_count.scalar() or 0

            # Average reach
            avg_reach = session.query(
                func.avg(WinningAds.eu_total_reach)
            ).join(
                PageRecherche,
                WinningAds.page_id == PageRecherche.page_id
            ).filter(WinningAds.date_scan >= cutoff)

            if thematique:
                avg_reach = avg_reach.filter(PageRecherche.thematique == thematique)
            if subcategory:
                avg_reach = avg_reach.filter(PageRecherche.subcategory == subcategory)
            if pays:
                avg_reach = avg_reach.filter(PageRecherche.pays.ilike(f"%{pays}%"))

            avg_reach = avg_reach.scalar() or 0
        else:
            # Sans filtres - utiliser la requête simple
            total = session.query(WinningAds).filter(
                WinningAds.date_scan >= cutoff
            ).count()

            unique_pages_count = session.query(
                func.count(func.distinct(WinningAds.page_id))
            ).filter(
                WinningAds.date_scan >= cutoff
            ).scalar() or 0

            avg_reach = session.query(
                func.avg(WinningAds.eu_total_reach)
            ).filter(
                WinningAds.date_scan >= cutoff
            ).scalar() or 0

        return {
            "total": total,
            "unique_pages": unique_pages_count,
            "avg_reach": int(avg_reach)
        }


@cached(ttl=30, key_prefix="winning_stats_")
def get_winning_ads_stats(db: DatabaseManager, days: int = 30) -> Dict:
    """
    Récupère les statistiques des winning ads (cached 30s)

    Args:
        db: Instance DatabaseManager
        days: Période en jours pour les stats

    Returns:
        Dictionnaire avec les statistiques
    """
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Total winning ads
        total = session.query(WinningAds).filter(
            WinningAds.date_scan >= cutoff
        ).count()

        # Nombre total de pages distinctes avec winning ads
        unique_pages_count = session.query(
            func.count(func.distinct(WinningAds.page_id))
        ).filter(
            WinningAds.date_scan >= cutoff
        ).scalar() or 0

        # Par page (top 10 pour affichage)
        by_page = session.query(
            WinningAds.page_id,
            WinningAds.page_name,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.page_id, WinningAds.page_name
        ).order_by(
            func.count(WinningAds.id).desc()
        ).limit(10).all()

        # Par critère
        by_criteria = session.query(
            WinningAds.matched_criteria,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.matched_criteria
        ).all()

        # Reach moyen
        avg_reach = session.query(
            func.avg(WinningAds.eu_total_reach)
        ).filter(
            WinningAds.date_scan >= cutoff
        ).scalar()

        return {
            "total": total,
            "unique_pages": unique_pages_count,  # Nombre total de pages distinctes
            "by_page": [{"page_id": p[0], "page_name": p[1], "count": p[2]} for p in by_page],
            "by_criteria": {c[0]: c[1] for c in by_criteria if c[0]},
            "avg_reach": int(avg_reach) if avg_reach else 0
        }


def get_winning_ads_by_page(
    db: DatabaseManager,
    days: int = 30
) -> Dict[str, int]:
    """
    Récupère le nombre de winning ads par page

    Args:
        db: Instance DatabaseManager
        days: Période en jours

    Returns:
        Dict {page_id: count}
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        results = session.query(
            WinningAds.page_id,
            func.count(WinningAds.id).label('count')
        ).filter(
            WinningAds.date_scan >= cutoff
        ).group_by(
            WinningAds.page_id
        ).all()

        return {r[0]: r[1] for r in results}


# ═══════════════════════════════════════════════════════════════════════════════
# TAGS - Gestion des tags personnalisés
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_tags(db: DatabaseManager) -> List[Dict]:
    """Récupère tous les tags"""
    with db.get_session() as session:
        tags = session.query(Tag).order_by(Tag.name).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]


def create_tag(db: DatabaseManager, name: str, color: str = "#3B82F6") -> Optional[int]:
    """Crée un nouveau tag"""
    with db.get_session() as session:
        existing = session.query(Tag).filter(Tag.name == name).first()
        if existing:
            return None
        tag = Tag(name=name, color=color)
        session.add(tag)
        session.flush()
        return tag.id


def delete_tag(db: DatabaseManager, tag_id: int) -> bool:
    """Supprime un tag et ses associations"""
    with db.get_session() as session:
        # Supprimer les associations
        session.query(PageTag).filter(PageTag.tag_id == tag_id).delete()
        # Supprimer le tag
        deleted = session.query(Tag).filter(Tag.id == tag_id).delete()
        return deleted > 0


def add_tag_to_page(db: DatabaseManager, page_id: str, tag_id: int) -> bool:
    """Ajoute un tag à une page"""
    with db.get_session() as session:
        existing = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).first()
        if existing:
            return False
        pt = PageTag(page_id=page_id, tag_id=tag_id)
        session.add(pt)
        return True


def remove_tag_from_page(db: DatabaseManager, page_id: str, tag_id: int) -> bool:
    """Retire un tag d'une page"""
    with db.get_session() as session:
        deleted = session.query(PageTag).filter(
            PageTag.page_id == page_id,
            PageTag.tag_id == tag_id
        ).delete()
        return deleted > 0


def get_page_tags(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les tags d'une page"""
    with db.get_session() as session:
        results = session.query(Tag).join(
            PageTag, Tag.id == PageTag.tag_id
        ).filter(PageTag.page_id == page_id).all()
        return [{"id": t.id, "name": t.name, "color": t.color} for t in results]


def get_pages_by_tag(db: DatabaseManager, tag_id: int) -> List[str]:
    """Récupère les page_ids ayant un tag spécifique"""
    with db.get_session() as session:
        results = session.query(PageTag.page_id).filter(PageTag.tag_id == tag_id).all()
        return [r[0] for r in results]


# ═══════════════════════════════════════════════════════════════════════════════
# NOTES - Gestion des notes sur les pages
# ═══════════════════════════════════════════════════════════════════════════════

def get_page_notes(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les notes d'une page"""
    with db.get_session() as session:
        notes = session.query(PageNote).filter(
            PageNote.page_id == page_id
        ).order_by(PageNote.created_at.desc()).all()
        return [{
            "id": n.id,
            "content": n.content,
            "created_at": n.created_at,
            "updated_at": n.updated_at
        } for n in notes]


def add_page_note(db: DatabaseManager, page_id: str, content: str) -> int:
    """Ajoute une note à une page"""
    with db.get_session() as session:
        note = PageNote(page_id=page_id, content=content)
        session.add(note)
        session.flush()
        return note.id


def update_page_note(db: DatabaseManager, note_id: int, content: str) -> bool:
    """Met à jour une note"""
    with db.get_session() as session:
        note = session.query(PageNote).filter(PageNote.id == note_id).first()
        if note:
            note.content = content
            note.updated_at = datetime.utcnow()
            return True
        return False


def delete_page_note(db: DatabaseManager, note_id: int) -> bool:
    """Supprime une note"""
    with db.get_session() as session:
        deleted = session.query(PageNote).filter(PageNote.id == note_id).delete()
        return deleted > 0


# ═══════════════════════════════════════════════════════════════════════════════
# FAVORITES - Gestion des favoris
# ═══════════════════════════════════════════════════════════════════════════════

def get_favorites(db: DatabaseManager) -> List[str]:
    """Récupère tous les page_ids favoris"""
    with db.get_session() as session:
        favs = session.query(Favorite.page_id).order_by(Favorite.added_at.desc()).all()
        return [f[0] for f in favs]


def is_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Vérifie si une page est en favori"""
    with db.get_session() as session:
        return session.query(Favorite).filter(Favorite.page_id == page_id).first() is not None


def add_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Ajoute une page aux favoris"""
    with db.get_session() as session:
        existing = session.query(Favorite).filter(Favorite.page_id == page_id).first()
        if existing:
            return False
        fav = Favorite(page_id=page_id)
        session.add(fav)
        return True


def remove_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Retire une page des favoris"""
    with db.get_session() as session:
        deleted = session.query(Favorite).filter(Favorite.page_id == page_id).delete()
        return deleted > 0


def toggle_favorite(db: DatabaseManager, page_id: str) -> bool:
    """Bascule le statut favori d'une page. Retourne True si maintenant favori."""
    if is_favorite(db, page_id):
        remove_favorite(db, page_id)
        return False
    else:
        add_favorite(db, page_id)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# COLLECTIONS - Gestion des dossiers/collections
# ═══════════════════════════════════════════════════════════════════════════════

def get_collections(db: DatabaseManager) -> List[Dict]:
    """Récupère toutes les collections avec le nombre de pages"""
    from sqlalchemy import func

    with db.get_session() as session:
        collections = session.query(Collection).order_by(Collection.name).all()
        result = []
        for c in collections:
            count = session.query(func.count(CollectionPage.id)).filter(
                CollectionPage.collection_id == c.id
            ).scalar()
            result.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "color": c.color,
                "icon": c.icon,
                "page_count": count or 0,
                "created_at": c.created_at
            })
        return result


def create_collection(
    db: DatabaseManager,
    name: str,
    description: str = "",
    color: str = "#6366F1",
    icon: str = "📁"
) -> int:
    """Crée une nouvelle collection"""
    with db.get_session() as session:
        coll = Collection(name=name, description=description, color=color, icon=icon)
        session.add(coll)
        session.flush()
        return coll.id


def update_collection(
    db: DatabaseManager,
    collection_id: int,
    name: str = None,
    description: str = None,
    color: str = None,
    icon: str = None
) -> bool:
    """Met à jour une collection"""
    with db.get_session() as session:
        coll = session.query(Collection).filter(Collection.id == collection_id).first()
        if not coll:
            return False
        if name is not None:
            coll.name = name
        if description is not None:
            coll.description = description
        if color is not None:
            coll.color = color
        if icon is not None:
            coll.icon = icon
        coll.updated_at = datetime.utcnow()
        return True


def delete_collection(db: DatabaseManager, collection_id: int) -> bool:
    """Supprime une collection et ses associations"""
    with db.get_session() as session:
        session.query(CollectionPage).filter(CollectionPage.collection_id == collection_id).delete()
        deleted = session.query(Collection).filter(Collection.id == collection_id).delete()
        return deleted > 0


def add_page_to_collection(db: DatabaseManager, collection_id: int, page_id: str) -> bool:
    """Ajoute une page à une collection"""
    with db.get_session() as session:
        existing = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).first()
        if existing:
            return False
        cp = CollectionPage(collection_id=collection_id, page_id=page_id)
        session.add(cp)
        return True


def remove_page_from_collection(db: DatabaseManager, collection_id: int, page_id: str) -> bool:
    """Retire une page d'une collection"""
    with db.get_session() as session:
        deleted = session.query(CollectionPage).filter(
            CollectionPage.collection_id == collection_id,
            CollectionPage.page_id == page_id
        ).delete()
        return deleted > 0


def get_collection_pages(db: DatabaseManager, collection_id: int) -> List[str]:
    """Récupère les page_ids d'une collection"""
    with db.get_session() as session:
        results = session.query(CollectionPage.page_id).filter(
            CollectionPage.collection_id == collection_id
        ).all()
        return [r[0] for r in results]


def get_page_collections(db: DatabaseManager, page_id: str) -> List[Dict]:
    """Récupère les collections d'une page"""
    with db.get_session() as session:
        results = session.query(Collection).join(
            CollectionPage, Collection.id == CollectionPage.collection_id
        ).filter(CollectionPage.page_id == page_id).all()
        return [{"id": c.id, "name": c.name, "color": c.color, "icon": c.icon} for c in results]


# ═══════════════════════════════════════════════════════════════════════════════
# SAVED FILTERS - Filtres sauvegardés
# ═══════════════════════════════════════════════════════════════════════════════

def get_saved_filters(db: DatabaseManager, filter_type: str = None) -> List[Dict]:
    """Récupère les filtres sauvegardés"""
    import json

    with db.get_session() as session:
        query = session.query(SavedFilter)
        if filter_type:
            query = query.filter(SavedFilter.filter_type == filter_type)
        filters = query.order_by(SavedFilter.name).all()
        return [{
            "id": f.id,
            "name": f.name,
            "filter_type": f.filter_type,
            "filters": json.loads(f.filters_json) if f.filters_json else {},
            "created_at": f.created_at
        } for f in filters]


def save_filter(
    db: DatabaseManager,
    name: str,
    filters: Dict,
    filter_type: str = "pages"
) -> int:
    """Sauvegarde un filtre"""
    import json

    with db.get_session() as session:
        sf = SavedFilter(
            name=name,
            filter_type=filter_type,
            filters_json=json.dumps(filters)
        )
        session.add(sf)
        session.flush()
        return sf.id


def delete_saved_filter(db: DatabaseManager, filter_id: int) -> bool:
    """Supprime un filtre sauvegardé"""
    with db.get_session() as session:
        deleted = session.query(SavedFilter).filter(SavedFilter.id == filter_id).delete()
        return deleted > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULED SCANS - Scans programmés
# ═══════════════════════════════════════════════════════════════════════════════

def get_scheduled_scans(db: DatabaseManager, active_only: bool = False) -> List[Dict]:
    """Récupère les scans programmés"""
    with db.get_session() as session:
        query = session.query(ScheduledScan)
        if active_only:
            query = query.filter(ScheduledScan.is_active == 1)
        scans = query.order_by(ScheduledScan.name).all()
        return [{
            "id": s.id,
            "name": s.name,
            "keywords": s.keywords,
            "countries": s.countries,
            "languages": s.languages,
            "frequency": s.frequency,
            "is_active": s.is_active == 1,
            "last_run": s.last_run,
            "next_run": s.next_run,
            "created_at": s.created_at
        } for s in scans]


def create_scheduled_scan(
    db: DatabaseManager,
    name: str,
    keywords: str,
    countries: str = "FR",
    languages: str = "fr",
    frequency: str = "daily"
) -> int:
    """Crée un nouveau scan programmé"""
    from datetime import timedelta

    # Calculer next_run
    now = datetime.utcnow()
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    elif frequency == "weekly":
        next_run = now + timedelta(weeks=1)
    else:  # monthly
        next_run = now + timedelta(days=30)

    with db.get_session() as session:
        scan = ScheduledScan(
            name=name,
            keywords=keywords,
            countries=countries,
            languages=languages,
            frequency=frequency,
            next_run=next_run
        )
        session.add(scan)
        session.flush()
        return scan.id


def update_scheduled_scan(
    db: DatabaseManager,
    scan_id: int,
    name: str = None,
    keywords: str = None,
    countries: str = None,
    languages: str = None,
    frequency: str = None,
    is_active: bool = None
) -> bool:
    """Met à jour un scan programmé"""
    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False
        if name is not None:
            scan.name = name
        if keywords is not None:
            scan.keywords = keywords
        if countries is not None:
            scan.countries = countries
        if languages is not None:
            scan.languages = languages
        if frequency is not None:
            scan.frequency = frequency
        if is_active is not None:
            scan.is_active = 1 if is_active else 0
        return True


def delete_scheduled_scan(db: DatabaseManager, scan_id: int) -> bool:
    """Supprime un scan programmé"""
    with db.get_session() as session:
        deleted = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).delete()
        return deleted > 0


def mark_scan_executed(db: DatabaseManager, scan_id: int) -> bool:
    """Marque un scan comme exécuté et calcule le prochain run"""
    from datetime import timedelta

    with db.get_session() as session:
        scan = session.query(ScheduledScan).filter(ScheduledScan.id == scan_id).first()
        if not scan:
            return False

        now = datetime.utcnow()
        scan.last_run = now

        if scan.frequency == "daily":
            scan.next_run = now + timedelta(days=1)
        elif scan.frequency == "weekly":
            scan.next_run = now + timedelta(weeks=1)
        else:
            scan.next_run = now + timedelta(days=30)

        return True


# ═══════════════════════════════════════════════════════════════════════════════
# USER SETTINGS - Paramètres utilisateur
# ═══════════════════════════════════════════════════════════════════════════════

def get_setting(db: DatabaseManager, key: str, default: str = None) -> Optional[str]:
    """Récupère un paramètre utilisateur"""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        return setting.setting_value if setting else default


def set_setting(db: DatabaseManager, key: str, value: str) -> bool:
    """Définit un paramètre utilisateur"""
    with db.get_session() as session:
        setting = session.query(UserSettings).filter(UserSettings.setting_key == key).first()
        if setting:
            setting.setting_value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = UserSettings(setting_key=key, setting_value=value)
            session.add(setting)
        return True


def get_all_settings(db: DatabaseManager) -> Dict[str, str]:
    """Récupère tous les paramètres"""
    with db.get_session() as session:
        settings = session.query(UserSettings).all()
        return {s.setting_key: s.setting_value for s in settings}


# ═══════════════════════════════════════════════════════════════════════════════
# BULK ACTIONS - Actions groupées
# ═══════════════════════════════════════════════════════════════════════════════

def bulk_add_to_blacklist(db: DatabaseManager, page_ids: List[str], raison: str = "") -> int:
    """Ajoute plusieurs pages à la blacklist"""
    count = 0
    for pid in page_ids:
        if add_to_blacklist(db, pid, raison=raison):
            count += 1
    return count


def bulk_add_to_collection(db: DatabaseManager, collection_id: int, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages à une collection"""
    count = 0
    for pid in page_ids:
        if add_page_to_collection(db, collection_id, pid):
            count += 1
    return count


def bulk_add_tag(db: DatabaseManager, tag_id: int, page_ids: List[str]) -> int:
    """Ajoute un tag à plusieurs pages"""
    count = 0
    for pid in page_ids:
        if add_tag_to_page(db, pid, tag_id):
            count += 1
    return count


def bulk_add_to_favorites(db: DatabaseManager, page_ids: List[str]) -> int:
    """Ajoute plusieurs pages aux favoris"""
    count = 0
    for pid in page_ids:
        if add_favorite(db, pid):
            count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH LOGS - Historique des recherches
# ═══════════════════════════════════════════════════════════════════════════════

def create_search_log(
    db: DatabaseManager,
    keywords: List[str],
    countries: List[str],
    languages: List[str],
    min_ads: int = 1,
    selected_cms: List[str] = None
) -> int:
    """
    Crée un nouveau log de recherche

    Returns:
        ID du log créé
    """
    # S'assurer que les paramètres sont des listes et non des strings
    if isinstance(countries, str):
        countries = [countries] if countries else []
    if isinstance(languages, str):
        languages = [languages] if languages else []
    if isinstance(keywords, str):
        keywords = [keywords] if keywords else []
    if isinstance(selected_cms, str):
        selected_cms = [selected_cms] if selected_cms else []

    with db.get_session() as session:
        log = SearchLog(
            keywords=" | ".join(keywords) if keywords else "",
            countries=",".join(countries) if countries else "",
            languages=",".join(languages) if languages else "",
            min_ads=min_ads,
            selected_cms=",".join(selected_cms) if selected_cms else "",
            started_at=datetime.utcnow(),
            status="running",
            phases_data="[]"
        )
        session.add(log)
        session.flush()
        return log.id


def update_search_log_phases(
    db: DatabaseManager,
    log_id: int,
    phases_data: List[Dict]
) -> bool:
    """Met à jour les données de phases d'un log"""
    import json

    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False
        log.phases_data = json.dumps(phases_data, ensure_ascii=False, default=str)
        return True


def complete_search_log(
    db: DatabaseManager,
    log_id: int,
    status: str = "completed",
    error_message: str = None,
    metrics: Dict = None,
    api_metrics: Dict = None
) -> bool:
    """
    Finalise un log de recherche (wrapper pour update_search_log).

    Args:
        db: Instance DatabaseManager
        log_id: ID du log
        status: completed, failed, cancelled
        error_message: Message d'erreur si failed
        metrics: Dictionnaire avec les métriques finales
        api_metrics: Dictionnaire avec les métriques API
    """
    # Extraire les métriques des dicts
    kwargs = {}
    if metrics:
        kwargs.update({
            "total_ads_found": metrics.get("total_ads_found"),
            "total_pages_found": metrics.get("total_pages_found"),
            "pages_after_filter": metrics.get("pages_after_filter"),
            "pages_shopify": metrics.get("pages_shopify"),
            "pages_other_cms": metrics.get("pages_other_cms"),
            "winning_ads_count": metrics.get("winning_ads_count"),
            "blacklisted_ads_skipped": metrics.get("blacklisted_ads_skipped"),
            "pages_saved": metrics.get("pages_saved"),
            "ads_saved": metrics.get("ads_saved"),
        })
    if api_metrics:
        kwargs.update(api_metrics)

    return update_search_log(
        db, log_id,
        status=status,
        error_message=error_message,
        **kwargs
    )


def update_search_log(
    db: DatabaseManager,
    log_id: int,
    status: str = None,
    error_message: str = None,
    total_ads_found: int = None,
    total_pages_found: int = None,
    pages_after_filter: int = None,
    pages_shopify: int = None,
    pages_other_cms: int = None,
    winning_ads_count: int = None,
    blacklisted_ads_skipped: int = None,
    pages_saved: int = None,
    ads_saved: int = None,
    phases_data: list = None,
    **api_metrics
) -> bool:
    """
    Met à jour un log de recherche avec les métriques.
    Wrapper pour complete_search_log avec signature simplifiée.

    Args:
        db: Instance DatabaseManager
        log_id: ID du log
        status: completed, failed, cancelled, no_results
        error_message: Message d'erreur si failed
        total_ads_found: Total d'ads trouvées
        total_pages_found: Total de pages trouvées
        pages_after_filter: Pages après filtrage
        pages_shopify: Pages Shopify détectées
        pages_other_cms: Pages autres CMS
        winning_ads_count: Nombre d'ads gagnantes
        blacklisted_ads_skipped: Ads blacklistées ignorées
        pages_saved: Pages sauvegardées
        ads_saved: Ads sauvegardées
        phases_data: Liste des phases pour le log
        **api_metrics: Métriques API additionnelles
    """
    import json

    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return False

        # Status et timing
        if status:
            log.status = status
            if status in ("completed", "failed", "cancelled", "no_results"):
                log.ended_at = datetime.utcnow()
                if log.started_at:
                    log.duration_seconds = (log.ended_at - log.started_at).total_seconds()

        if error_message:
            log.error_message = error_message

        # Métriques principales
        if total_ads_found is not None:
            log.total_ads_found = total_ads_found
        if total_pages_found is not None:
            log.total_pages_found = total_pages_found
        if pages_after_filter is not None:
            log.pages_after_filter = pages_after_filter
        if pages_shopify is not None:
            log.pages_shopify = pages_shopify
        if pages_other_cms is not None:
            log.pages_other_cms = pages_other_cms
        if winning_ads_count is not None:
            log.winning_ads_count = winning_ads_count
        if blacklisted_ads_skipped is not None:
            log.blacklisted_ads_skipped = blacklisted_ads_skipped
        if pages_saved is not None:
            log.pages_saved = pages_saved
        if ads_saved is not None:
            log.ads_saved = ads_saved

        # Phases data
        if phases_data is not None:
            log.phases_data = json.dumps(phases_data, ensure_ascii=False, default=str)

        # Métriques API
        if api_metrics:
            if "meta_api_calls" in api_metrics:
                log.meta_api_calls = api_metrics.get("meta_api_calls", 0)
            if "scraper_api_calls" in api_metrics:
                log.scraper_api_calls = api_metrics.get("scraper_api_calls", 0)
            if "web_requests" in api_metrics:
                log.web_requests = api_metrics.get("web_requests", 0)
            if "meta_api_errors" in api_metrics:
                log.meta_api_errors = api_metrics.get("meta_api_errors", 0)
            if "scraper_api_errors" in api_metrics:
                log.scraper_api_errors = api_metrics.get("scraper_api_errors", 0)
            if "web_errors" in api_metrics:
                log.web_errors = api_metrics.get("web_errors", 0)
            if "rate_limit_hits" in api_metrics:
                log.rate_limit_hits = api_metrics.get("rate_limit_hits", 0)
            if "meta_api_avg_time" in api_metrics:
                log.meta_api_avg_time = api_metrics.get("meta_api_avg_time", 0)
            if "scraper_api_avg_time" in api_metrics:
                log.scraper_api_avg_time = api_metrics.get("scraper_api_avg_time", 0)
            if "web_avg_time" in api_metrics:
                log.web_avg_time = api_metrics.get("web_avg_time", 0)
            if "scraper_api_cost" in api_metrics:
                log.scraper_api_cost = api_metrics.get("scraper_api_cost", 0)

            # API details
            api_details_data = {}
            if api_metrics.get("api_details"):
                api_details_data["keyword_stats"] = api_metrics["api_details"]
            if api_metrics.get("scraper_errors_by_type"):
                api_details_data["scraper_errors_by_type"] = api_metrics["scraper_errors_by_type"]
                # Aussi stocker dans le champ dédié
                log.scraper_errors_by_type = json.dumps(api_metrics["scraper_errors_by_type"], ensure_ascii=False)
            if api_details_data:
                log.api_details = json.dumps(api_details_data, ensure_ascii=False)

            # Liste des erreurs détaillées
            if api_metrics.get("errors_list"):
                log.errors_list = json.dumps(api_metrics["errors_list"], ensure_ascii=False, default=str)

        return True


def save_api_calls(db: DatabaseManager, search_log_id: int, calls: list) -> int:
    """
    Sauvegarde les appels API en base de données

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du SearchLog associé
        calls: Liste d'objets APICall

    Returns:
        Nombre d'appels sauvegardés
    """
    count = 0
    with db.get_session() as session:
        for call in calls:
            api_call = APICallLog(
                search_log_id=search_log_id,
                api_type=call.api_type,
                endpoint=call.endpoint[:500] if call.endpoint else "",
                method=call.method,
                keyword=call.keyword[:200] if call.keyword else "",
                page_id=call.page_id[:50] if call.page_id else "",
                site_url=call.site_url[:500] if call.site_url else "",
                status_code=call.status_code,
                success=call.success,
                error_type=call.error_type[:100] if call.error_type else "",
                error_message=call.error_message[:500] if call.error_message else "",
                response_time_ms=call.response_time_ms,
                response_size=call.response_size,
                items_returned=call.items_returned,
                called_at=call.called_at
            )
            session.add(api_call)
            count += 1
    return count


def get_api_calls_for_search(db: DatabaseManager, search_log_id: int) -> List[Dict]:
    """Récupère les appels API pour une recherche"""
    with db.get_session() as session:
        calls = session.query(APICallLog).filter(
            APICallLog.search_log_id == search_log_id
        ).order_by(APICallLog.called_at).all()

        return [{
            "id": c.id,
            "api_type": c.api_type,
            "endpoint": c.endpoint,
            "keyword": c.keyword,
            "site_url": c.site_url,
            "status_code": c.status_code,
            "success": c.success,
            "error_type": c.error_type,
            "error_message": c.error_message,
            "response_time_ms": c.response_time_ms,
            "items_returned": c.items_returned,
            "called_at": c.called_at
        } for c in calls]


def get_search_logs(
    db: DatabaseManager,
    limit: int = 50,
    status: str = None
) -> List[Dict]:
    """
    Récupère les logs de recherche

    Args:
        db: Instance DatabaseManager
        limit: Nombre max de résultats
        status: Filtrer par statut (running, completed, failed)

    Returns:
        Liste des logs
    """
    import json

    with db.get_session() as session:
        query = session.query(SearchLog).order_by(SearchLog.started_at.desc())

        if status:
            query = query.filter(SearchLog.status == status)

        logs = query.limit(limit).all()

        return [{
            "id": l.id,
            "keywords": l.keywords,
            "countries": l.countries,
            "languages": l.languages,
            "min_ads": l.min_ads,
            "selected_cms": l.selected_cms,
            "started_at": l.started_at,
            "ended_at": l.ended_at,
            "duration_seconds": l.duration_seconds,
            "status": l.status,
            "error_message": l.error_message,
            "phases_data": json.loads(l.phases_data) if l.phases_data else [],
            "total_ads_found": l.total_ads_found,
            "total_pages_found": l.total_pages_found,
            "pages_after_filter": l.pages_after_filter,
            "pages_shopify": l.pages_shopify,
            "pages_other_cms": l.pages_other_cms,
            "winning_ads_count": l.winning_ads_count,
            "blacklisted_ads_skipped": l.blacklisted_ads_skipped,
            "pages_saved": l.pages_saved,
            "ads_saved": l.ads_saved,
            # Stats API
            "meta_api_calls": getattr(l, 'meta_api_calls', 0) or 0,
            "scraper_api_calls": getattr(l, 'scraper_api_calls', 0) or 0,
            "web_requests": getattr(l, 'web_requests', 0) or 0,
            "meta_api_errors": getattr(l, 'meta_api_errors', 0) or 0,
            "scraper_api_errors": getattr(l, 'scraper_api_errors', 0) or 0,
            "web_errors": getattr(l, 'web_errors', 0) or 0,
            "rate_limit_hits": getattr(l, 'rate_limit_hits', 0) or 0,
            "meta_api_avg_time": getattr(l, 'meta_api_avg_time', 0) or 0,
            "scraper_api_avg_time": getattr(l, 'scraper_api_avg_time', 0) or 0,
            "web_avg_time": getattr(l, 'web_avg_time', 0) or 0,
            "scraper_api_cost": getattr(l, 'scraper_api_cost', 0) or 0,
            "errors_list": json.loads(getattr(l, 'errors_list', None) or '[]'),
            **_parse_api_details(getattr(l, 'api_details', None)),
            **_parse_scraper_errors(getattr(l, 'scraper_errors_by_type', None))
        } for l in logs]


def _parse_scraper_errors(scraper_errors_json: str) -> Dict:
    """Parse le JSON scraper_errors_by_type"""
    import json
    if not scraper_errors_json:
        return {}
    try:
        data = json.loads(scraper_errors_json)
        if isinstance(data, dict):
            return {"scraper_errors_by_type": data}
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _parse_api_details(api_details_json: str) -> Dict:
    """Parse le JSON api_details et extrait les champs"""
    import json
    result = {"api_details": {}, "scraper_errors_by_type": {}}
    if not api_details_json:
        return result
    try:
        data = json.loads(api_details_json)
        if isinstance(data, dict):
            # Nouveau format avec keyword_stats et scraper_errors_by_type
            if "keyword_stats" in data:
                result["api_details"] = data.get("keyword_stats", {})
                result["scraper_errors_by_type"] = data.get("scraper_errors_by_type", {})
            else:
                # Ancien format: tout est keyword_stats
                result["api_details"] = data
    except (json.JSONDecodeError, TypeError):
        pass
    return result


def get_search_log_detail(db: DatabaseManager, log_id: int) -> Optional[Dict]:
    """Récupère les détails complets d'un log"""
    import json

    with db.get_session() as session:
        log = session.query(SearchLog).filter(SearchLog.id == log_id).first()
        if not log:
            return None

        return {
            "id": log.id,
            "keywords": log.keywords,
            "countries": log.countries,
            "languages": log.languages,
            "min_ads": log.min_ads,
            "selected_cms": log.selected_cms,
            "started_at": log.started_at,
            "ended_at": log.ended_at,
            "duration_seconds": log.duration_seconds,
            "status": log.status,
            "error_message": log.error_message,
            "phases_data": json.loads(log.phases_data) if log.phases_data else [],
            "total_ads_found": log.total_ads_found,
            "total_pages_found": log.total_pages_found,
            "pages_after_filter": log.pages_after_filter,
            "pages_shopify": log.pages_shopify,
            "pages_other_cms": log.pages_other_cms,
            "winning_ads_count": log.winning_ads_count,
            "blacklisted_ads_skipped": log.blacklisted_ads_skipped,
            "pages_saved": log.pages_saved,
            "ads_saved": log.ads_saved
        }


def delete_search_log(db: DatabaseManager, log_id: int) -> bool:
    """Supprime un log de recherche"""
    with db.get_session() as session:
        deleted = session.query(SearchLog).filter(SearchLog.id == log_id).delete()
        return deleted > 0


def get_pages_by_search_log(db: DatabaseManager, search_log_id: int, limit: int = 100) -> List[Dict]:
    """
    Récupère les pages associées à une recherche (créées ou mises à jour).

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du SearchLog
        limit: Nombre max de pages à retourner

    Returns:
        Liste de dictionnaires avec les données des pages
    """
    with db.get_session() as session:
        pages = session.query(PageRecherche).filter(
            PageRecherche.last_search_log_id == search_log_id
        ).order_by(PageRecherche.nombre_ads_active.desc()).limit(limit).all()

        return [{
            "id": p.id,
            "page_id": p.page_id,
            "page_name": p.page_name,
            "lien_site": p.lien_site,
            "cms": p.cms,
            "etat": p.etat,
            "nombre_ads_active": p.nombre_ads_active,
            "nombre_produits": p.nombre_produits,
            "thematique": p.thematique,
            "is_new": p.was_created_in_last_search,
            "keywords": p.keywords
        } for p in pages]


def get_winning_ads_by_search_log(db: DatabaseManager, search_log_id: int, limit: int = 100) -> List[Dict]:
    """
    Récupère les winning ads associées à une recherche.

    Args:
        db: Instance DatabaseManager
        search_log_id: ID du SearchLog
        limit: Nombre max de winning ads à retourner

    Returns:
        Liste de dictionnaires avec les données des winning ads
    """
    with db.get_session() as session:
        ads = session.query(WinningAds).filter(
            WinningAds.search_log_id == search_log_id
        ).order_by(WinningAds.eu_total_reach.desc().nullslast()).limit(limit).all()

        return [{
            "id": a.id,
            "ad_id": a.ad_id,
            "page_id": a.page_id,
            "page_name": a.page_name,
            "ad_creation_time": a.ad_creation_time,
            "ad_age_days": a.ad_age_days,
            "eu_total_reach": a.eu_total_reach,
            "matched_criteria": a.matched_criteria,
            "ad_snapshot_url": a.ad_snapshot_url,
            "lien_site": a.lien_site,
            "is_new": a.is_new
        } for a in ads]


def get_search_logs_stats(db: DatabaseManager, days: int = 30) -> Dict:
    """
    Récupère les statistiques des recherches

    Returns:
        Dict avec stats globales
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Total de recherches
        total = session.query(SearchLog).filter(
            SearchLog.started_at >= cutoff
        ).count()

        # Par statut
        by_status = session.query(
            SearchLog.status,
            func.count(SearchLog.id)
        ).filter(
            SearchLog.started_at >= cutoff
        ).group_by(SearchLog.status).all()

        # Durée moyenne
        avg_duration = session.query(
            func.avg(SearchLog.duration_seconds)
        ).filter(
            SearchLog.started_at >= cutoff,
            SearchLog.status == "completed"
        ).scalar()

        # Total pages/ads trouvés
        totals = session.query(
            func.sum(SearchLog.total_ads_found),
            func.sum(SearchLog.total_pages_found),
            func.sum(SearchLog.winning_ads_count)
        ).filter(
            SearchLog.started_at >= cutoff,
            SearchLog.status == "completed"
        ).first()

        # Stats API
        api_stats = session.query(
            func.sum(SearchLog.meta_api_calls),
            func.sum(SearchLog.scraper_api_calls),
            func.sum(SearchLog.web_requests),
            func.sum(SearchLog.meta_api_errors),
            func.sum(SearchLog.scraper_api_errors),
            func.sum(SearchLog.web_errors),
            func.sum(SearchLog.rate_limit_hits),
            func.sum(SearchLog.scraper_api_cost)
        ).filter(
            SearchLog.started_at >= cutoff
        ).first()

        return {
            "total_searches": total,
            "by_status": {s[0]: s[1] for s in by_status},
            "avg_duration_seconds": round(avg_duration, 1) if avg_duration else 0,
            "total_ads_found": totals[0] or 0,
            "total_pages_found": totals[1] or 0,
            "total_winning_ads": totals[2] or 0,
            # Stats API
            "total_meta_api_calls": api_stats[0] or 0,
            "total_scraper_api_calls": api_stats[1] or 0,
            "total_web_requests": api_stats[2] or 0,
            "total_meta_api_errors": api_stats[3] or 0,
            "total_scraper_api_errors": api_stats[4] or 0,
            "total_web_errors": api_stats[5] or 0,
            "total_rate_limit_hits": api_stats[6] or 0,
            "total_scraper_api_cost": api_stats[7] or 0
        }


# ═══════════════════════════════════════════════════════════════════════════════
# META TOKENS - Gestion des tokens Meta API
# ═══════════════════════════════════════════════════════════════════════════════

def add_meta_token(
    db: DatabaseManager,
    token: str,
    name: str = None,
    proxy_url: str = None
) -> int:
    """
    Ajoute un nouveau token Meta API

    Args:
        db: Instance DatabaseManager
        token: Le token Meta API
        name: Nom descriptif (optionnel)
        proxy_url: URL du proxy associé (optionnel, ex: "http://user:pass@ip:port")

    Returns:
        ID du token créé
    """
    with db.get_session() as session:
        # Vérifier si le token existe déjà
        existing = session.query(MetaToken).filter(MetaToken.token == token).first()
        if existing:
            return existing.id

        # Générer un nom si non fourni
        if not name:
            count = session.query(MetaToken).count()
            name = f"Token #{count + 1}"

        meta_token = MetaToken(
            token=token,
            name=name,
            proxy_url=proxy_url,
            is_active=True
        )
        session.add(meta_token)
        session.flush()
        return meta_token.id


def get_all_meta_tokens(db: DatabaseManager, active_only: bool = False) -> List[Dict]:
    """
    Récupère tous les tokens Meta API

    Args:
        db: Instance DatabaseManager
        active_only: Si True, ne retourne que les tokens actifs

    Returns:
        Liste des tokens avec leurs stats
    """
    with db.get_session() as session:
        query = session.query(MetaToken).order_by(MetaToken.id)

        if active_only:
            query = query.filter(MetaToken.is_active == True)

        tokens = query.all()

        now = datetime.utcnow()
        return [{
            "id": t.id,
            "name": t.name,
            "token_masked": f"{t.token[:8]}...{t.token[-4:]}" if len(t.token) > 12 else "***",
            "token": t.token,  # Inclus pour utilisation interne
            "proxy_url": t.proxy_url,  # Proxy associé
            "is_active": t.is_active,
            "total_calls": t.total_calls or 0,
            "total_errors": t.total_errors or 0,
            "rate_limit_hits": t.rate_limit_hits or 0,
            "last_used_at": t.last_used_at,
            "last_error_at": t.last_error_at,
            "last_error_message": t.last_error_message,
            "rate_limited_until": t.rate_limited_until,
            "is_rate_limited": t.rate_limited_until and t.rate_limited_until > now,
            "created_at": t.created_at
        } for t in tokens]


def get_active_meta_tokens(db: DatabaseManager) -> List[str]:
    """
    Récupère uniquement les tokens actifs (pour le TokenRotator)

    Returns:
        Liste des tokens (strings)
    """
    with db.get_session() as session:
        now = datetime.utcnow()
        tokens = session.query(MetaToken).filter(
            MetaToken.is_active == True
        ).order_by(MetaToken.id).all()

        # Filtrer les tokens rate-limited
        return [t.token for t in tokens
                if not t.rate_limited_until or t.rate_limited_until <= now]


def get_active_meta_tokens_with_proxies(db: DatabaseManager) -> List[Dict]:
    """
    Récupère les tokens actifs avec leurs proxies associés.

    Returns:
        Liste de dicts: [{"id": 1, "token": "...", "proxy": "http://...", "name": "..."}]
    """
    with db.get_session() as session:
        now = datetime.utcnow()
        tokens = session.query(MetaToken).filter(
            MetaToken.is_active == True
        ).order_by(MetaToken.id).all()

        # Filtrer les tokens rate-limited et retourner id + token + proxy
        result = []
        for t in tokens:
            if not t.rate_limited_until or t.rate_limited_until <= now:
                result.append({
                    "id": t.id,
                    "token": t.token,
                    "proxy": t.proxy_url,
                    "name": t.name or f"Token #{t.id}"
                })
        return result


def update_meta_token(
    db: DatabaseManager,
    token_id: int,
    name: str = None,
    is_active: bool = None,
    proxy_url: str = None,
    token_value: str = None
) -> bool:
    """Met à jour un token (nom, statut actif, proxy, valeur du token)"""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False

        if name is not None:
            token.name = name
        if is_active is not None:
            token.is_active = is_active
        if proxy_url is not None:
            token.proxy_url = proxy_url if proxy_url.strip() else None
        if token_value is not None and token_value.strip():
            token.token = token_value.strip()

        return True


def delete_meta_token(db: DatabaseManager, token_id: int) -> bool:
    """Supprime un token"""
    with db.get_session() as session:
        deleted = session.query(MetaToken).filter(MetaToken.id == token_id).delete()
        return deleted > 0


def record_token_usage(
    db: DatabaseManager,
    token: str,
    success: bool = True,
    error_message: str = None,
    is_rate_limit: bool = False,
    rate_limit_seconds: int = 60
):
    """
    Enregistre une utilisation de token

    Args:
        db: Instance DatabaseManager
        token: Le token utilisé
        success: Si l'appel a réussi
        error_message: Message d'erreur si échec
        is_rate_limit: Si c'est une erreur de rate limit
        rate_limit_seconds: Durée du rate limit en secondes
    """
    from datetime import timedelta

    with db.get_session() as session:
        meta_token = session.query(MetaToken).filter(MetaToken.token == token).first()
        if not meta_token:
            return

        meta_token.total_calls = (meta_token.total_calls or 0) + 1
        meta_token.last_used_at = datetime.utcnow()

        if not success:
            meta_token.total_errors = (meta_token.total_errors or 0) + 1
            meta_token.last_error_at = datetime.utcnow()
            meta_token.last_error_message = error_message[:500] if error_message else None

            if is_rate_limit:
                meta_token.rate_limit_hits = (meta_token.rate_limit_hits or 0) + 1
                meta_token.rate_limited_until = datetime.utcnow() + timedelta(seconds=rate_limit_seconds)


def clear_rate_limit(db: DatabaseManager, token_id: int) -> bool:
    """Efface le rate limit d'un token"""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False
        token.rate_limited_until = None
        return True


def reset_token_stats(db: DatabaseManager, token_id: int) -> bool:
    """Réinitialise les statistiques d'un token"""
    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return False

        token.total_calls = 0
        token.total_errors = 0
        token.rate_limit_hits = 0
        token.last_used_at = None
        token.last_error_at = None
        token.last_error_message = None
        token.rate_limited_until = None
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# LOGS DETAILLES DES TOKENS
# ═══════════════════════════════════════════════════════════════════════════════

def log_token_usage(
    db: DatabaseManager,
    token_id: int,
    token_name: str,
    action_type: str,
    keyword: str = None,
    countries: str = None,
    page_id: str = None,
    success: bool = True,
    ads_count: int = 0,
    error_message: str = None,
    response_time_ms: int = None
) -> int:
    """
    Enregistre une utilisation de token dans les logs.

    Args:
        token_id: ID du token
        token_name: Nom du token
        action_type: Type d'action (search, page_fetch, verification, rate_limit)
        keyword: Mot-cle recherche (optionnel)
        countries: Pays (optionnel)
        page_id: ID de page (optionnel)
        success: Succes ou echec
        ads_count: Nombre d'ads trouvees
        error_message: Message d'erreur (optionnel)
        response_time_ms: Temps de reponse en ms

    Returns:
        ID du log cree
    """
    with db.get_session() as session:
        log_entry = TokenUsageLog(
            token_id=token_id,
            token_name=token_name,
            action_type=action_type,
            keyword=keyword[:255] if keyword else None,
            countries=countries[:100] if countries else None,
            page_id=page_id,
            success=success,
            ads_count=ads_count,
            error_message=error_message,
            response_time_ms=response_time_ms
        )
        session.add(log_entry)
        session.flush()
        return log_entry.id


def get_token_usage_logs(
    db: DatabaseManager,
    token_id: int = None,
    days: int = 7,
    limit: int = 100,
    action_type: str = None
) -> List[Dict]:
    """
    Recupere les logs d'utilisation des tokens.

    Args:
        token_id: Filtrer par token (optionnel)
        days: Nombre de jours a recuperer
        limit: Nombre max de logs
        action_type: Filtrer par type d'action

    Returns:
        Liste des logs
    """
    from sqlalchemy import desc

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        query = session.query(TokenUsageLog).filter(
            TokenUsageLog.created_at >= cutoff
        )

        if token_id:
            query = query.filter(TokenUsageLog.token_id == token_id)

        if action_type:
            query = query.filter(TokenUsageLog.action_type == action_type)

        logs = query.order_by(desc(TokenUsageLog.created_at)).limit(limit).all()

        return [
            {
                "id": log.id,
                "token_id": log.token_id,
                "token_name": log.token_name,
                "action_type": log.action_type,
                "keyword": log.keyword,
                "countries": log.countries,
                "page_id": log.page_id,
                "success": log.success,
                "ads_count": log.ads_count,
                "error_message": log.error_message,
                "response_time_ms": log.response_time_ms,
                "created_at": log.created_at
            }
            for log in logs
        ]


def get_token_stats_detailed(db: DatabaseManager, token_id: int, days: int = 30) -> Dict:
    """
    Recupere les statistiques detaillees d'un token.

    Args:
        token_id: ID du token
        days: Periode en jours

    Returns:
        Dict avec stats detaillees
    """
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        # Stats globales
        total_calls = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        successful = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff,
            TokenUsageLog.success == True
        ).scalar() or 0

        total_ads = session.query(func.sum(TokenUsageLog.ads_count)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        avg_response = session.query(func.avg(TokenUsageLog.response_time_ms)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff,
            TokenUsageLog.response_time_ms != None
        ).scalar() or 0

        # Stats par type d'action
        by_action = session.query(
            TokenUsageLog.action_type,
            func.count(TokenUsageLog.id),
            func.sum(TokenUsageLog.ads_count)
        ).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.created_at >= cutoff
        ).group_by(TokenUsageLog.action_type).all()

        # Derniers mots-cles recherches
        recent_keywords = session.query(
            TokenUsageLog.keyword,
            TokenUsageLog.created_at,
            TokenUsageLog.ads_count,
            TokenUsageLog.success
        ).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.keyword != None,
            TokenUsageLog.created_at >= cutoff
        ).order_by(TokenUsageLog.created_at.desc()).limit(20).all()

        # Rate limits
        rate_limits = session.query(func.count(TokenUsageLog.id)).filter(
            TokenUsageLog.token_id == token_id,
            TokenUsageLog.action_type == "rate_limit",
            TokenUsageLog.created_at >= cutoff
        ).scalar() or 0

        return {
            "total_calls": total_calls,
            "successful": successful,
            "failed": total_calls - successful,
            "success_rate": (successful / total_calls * 100) if total_calls > 0 else 0,
            "total_ads_found": total_ads,
            "avg_response_ms": round(avg_response, 0),
            "rate_limits": rate_limits,
            "by_action": [
                {"action": a[0], "count": a[1], "ads": a[2] or 0}
                for a in by_action
            ],
            "recent_keywords": [
                {
                    "keyword": k[0],
                    "date": k[1],
                    "ads": k[2],
                    "success": k[3]
                }
                for k in recent_keywords
            ]
        }


def verify_meta_token(db: DatabaseManager, token_id: int) -> Dict:
    """
    Verifie si un token Meta est toujours valide en faisant un appel test.

    Args:
        token_id: ID du token a verifier

    Returns:
        Dict avec resultat de la verification
    """
    import requests
    import time

    with db.get_session() as session:
        token = session.query(MetaToken).filter(MetaToken.id == token_id).first()
        if not token:
            return {"valid": False, "error": "Token non trouve"}

        token_value = token.token
        token_name = token.name
        proxy_url = token.proxy_url

    # Preparer le proxy si present
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Appel test simple - compter les ads pour une recherche vide
    test_url = "https://graph.facebook.com/v21.0/ads_archive"
    params = {
        "access_token": token_value,
        "search_terms": "test",
        "ad_reached_countries": '["FR"]',
        "ad_active_status": "ACTIVE",
        "limit": 1,
        "fields": "id"
    }

    start_time = time.time()
    result = {
        "valid": False,
        "token_id": token_id,
        "token_name": token_name,
        "response_time_ms": 0,
        "error": None
    }

    try:
        response = requests.get(
            test_url,
            params=params,
            proxies=proxies,
            timeout=30,
            verify=False
        )
        response_time = int((time.time() - start_time) * 1000)
        result["response_time_ms"] = response_time

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                result["valid"] = True
                result["message"] = "Token valide et fonctionnel"

                # Logger la verification reussie
                log_token_usage(
                    db, token_id, token_name, "verification",
                    success=True, response_time_ms=response_time
                )
            else:
                result["error"] = data.get("error", {}).get("message", "Reponse invalide")

                log_token_usage(
                    db, token_id, token_name, "verification",
                    success=False, error_message=result["error"], response_time_ms=response_time
                )
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
            result["error"] = error_msg

            # Detecter les erreurs specifiques
            if "OAuth" in error_msg or "token" in error_msg.lower():
                result["error_type"] = "token_expired"
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                result["error_type"] = "rate_limited"
            else:
                result["error_type"] = "unknown"

            log_token_usage(
                db, token_id, token_name, "verification",
                success=False, error_message=error_msg, response_time_ms=response_time
            )

    except requests.exceptions.Timeout:
        result["error"] = "Timeout - pas de reponse"
        result["error_type"] = "timeout"
    except requests.exceptions.ProxyError:
        result["error"] = "Erreur proxy - verifiez la configuration"
        result["error_type"] = "proxy_error"
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = "exception"

    return result


def verify_all_tokens(db: DatabaseManager) -> List[Dict]:
    """
    Verifie tous les tokens actifs.

    Returns:
        Liste des resultats de verification
    """
    tokens = get_all_meta_tokens(db, active_only=True)
    results = []

    for token in tokens:
        result = verify_meta_token(db, token["id"])
        results.append(result)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE AUTOMATIQUE DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

def cleanup_old_data(
    db: DatabaseManager,
    winning_ads_days: int = 90,
    search_logs_days: int = 30,
    api_logs_days: int = 7,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Nettoie les anciennes données pour maintenir les performances de la DB.

    Args:
        db: Instance DatabaseManager
        winning_ads_days: Supprimer les winning ads plus vieilles que X jours
        search_logs_days: Supprimer les logs de recherche plus vieux que X jours
        api_logs_days: Supprimer les logs API plus vieux que X jours
        dry_run: Si True, compte seulement sans supprimer

    Returns:
        Dict avec le nombre d'entrées supprimées par table
    """
    results = {
        "winning_ads": 0,
        "search_logs": 0,
        "api_call_logs": 0,
        "suivi_page": 0
    }

    with db.get_session() as session:
        # 1. Winning Ads anciennes
        cutoff_winning = datetime.utcnow() - timedelta(days=winning_ads_days)
        query_winning = session.query(WinningAds).filter(
            WinningAds.date_scan < cutoff_winning
        )
        if dry_run:
            results["winning_ads"] = query_winning.count()
        else:
            results["winning_ads"] = query_winning.delete(synchronize_session=False)

        # 2. Search Logs anciens
        cutoff_logs = datetime.utcnow() - timedelta(days=search_logs_days)
        query_logs = session.query(SearchLog).filter(
            SearchLog.started_at < cutoff_logs
        )
        if dry_run:
            results["search_logs"] = query_logs.count()
        else:
            results["search_logs"] = query_logs.delete(synchronize_session=False)

        # 3. API Call Logs anciens
        cutoff_api = datetime.utcnow() - timedelta(days=api_logs_days)
        query_api = session.query(APICallLog).filter(
            APICallLog.called_at < cutoff_api
        )
        if dry_run:
            results["api_call_logs"] = query_api.count()
        else:
            results["api_call_logs"] = query_api.delete(synchronize_session=False)

        # 4. Suivi Page ancien (garder seulement les 30 derniers jours par page)
        cutoff_suivi = datetime.utcnow() - timedelta(days=60)
        query_suivi = session.query(SuiviPage).filter(
            SuiviPage.date_scan < cutoff_suivi
        )
        if dry_run:
            results["suivi_page"] = query_suivi.count()
        else:
            results["suivi_page"] = query_suivi.delete(synchronize_session=False)

    # Invalider le cache après nettoyage
    if not dry_run and CACHE_ENABLED:
        invalidate_stats_cache()

    return results


def vacuum_database(db: DatabaseManager) -> bool:
    """
    Exécute un VACUUM ANALYZE sur la base pour récupérer l'espace et mettre à jour les stats.
    Note: Nécessite autocommit=True, donc on utilise une connexion directe.

    Returns:
        True si succès
    """
    try:
        from sqlalchemy import text
        # VACUUM ne peut pas être exécuté dans une transaction
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM ANALYZE"))
        return True
    except Exception as e:
        print(f"Erreur VACUUM: {e}")
        return False


def get_database_stats(db: DatabaseManager) -> Dict:
    """
    Retourne des statistiques sur la base de données.

    Returns:
        Dict avec les statistiques de chaque table
    """
    from sqlalchemy import func, text

    stats = {}

    with db.get_session() as session:
        # Compter les entrées par table
        stats["tables"] = {
            "pages": session.query(PageRecherche).count(),
            "suivi": session.query(SuiviPage).count(),
            "ads": session.query(AdsRecherche).count(),
            "winning_ads": session.query(WinningAds).count(),
            "blacklist": session.query(Blacklist).count(),
            "search_logs": session.query(SearchLog).count(),
            "api_logs": session.query(APICallLog).count(),
            "favorites": session.query(Favorite).count(),
            "collections": session.query(Collection).count(),
            "tags": session.query(Tag).count(),
        }

        # Dates extrêmes
        oldest_page = session.query(func.min(PageRecherche.created_at)).scalar()
        newest_page = session.query(func.max(PageRecherche.created_at)).scalar()
        oldest_winning = session.query(func.min(WinningAds.date_scan)).scalar()
        newest_winning = session.query(func.max(WinningAds.date_scan)).scalar()

        stats["dates"] = {
            "oldest_page": oldest_page.isoformat() if oldest_page else None,
            "newest_page": newest_page.isoformat() if newest_page else None,
            "oldest_winning_ad": oldest_winning.isoformat() if oldest_winning else None,
            "newest_winning_ad": newest_winning.isoformat() if newest_winning else None,
        }

        # Pool de connexions
        stats["pool"] = db.get_pool_status()

    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def health_check(db: DatabaseManager) -> Dict:
    """
    Vérifie la santé de la base de données.

    Returns:
        Dict avec le statut et les détails
    """
    from sqlalchemy import text

    result = {
        "status": "healthy",
        "database": "unknown",
        "pool": None,
        "tables_exist": False,
        "errors": []
    }

    try:
        # 1. Test de connexion basique
        with db.get_session() as session:
            session.execute(text("SELECT 1"))
        result["database"] = "connected"

        # 2. Vérifier que les tables existent
        with db.get_session() as session:
            # Tester une requête simple sur chaque table principale
            session.query(PageRecherche).limit(1).all()
            session.query(WinningAds).limit(1).all()
            session.query(SearchLog).limit(1).all()
        result["tables_exist"] = True

        # 3. Stats du pool
        result["pool"] = db.get_pool_status()

        # 4. Vérifier l'espace (estimation basée sur le nombre de lignes)
        with db.get_session() as session:
            total_rows = (
                session.query(PageRecherche).count() +
                session.query(WinningAds).count() +
                session.query(SearchLog).count() +
                session.query(APICallLog).count()
            )
            if total_rows > 1000000:  # Plus d'1M de lignes
                result["warnings"] = ["Database has over 1M rows, consider cleanup"]

    except Exception as e:
        result["status"] = "unhealthy"
        result["errors"].append(str(e))

    return result


def batch_insert_pages(
    db: DatabaseManager,
    pages_data: List[Dict],
    batch_size: int = 100
) -> int:
    """
    Insertion en batch optimisée pour les nouvelles pages.
    Utilise INSERT ... ON CONFLICT DO UPDATE pour gérer les doublons.

    Args:
        db: Instance DatabaseManager
        pages_data: Liste de dictionnaires avec les données des pages
        batch_size: Taille des batches

    Returns:
        Nombre de pages insérées/mises à jour
    """
    if not pages_data:
        return 0

    total = 0
    scan_time = datetime.utcnow()

    with db.get_session() as session:
        for i in range(0, len(pages_data), batch_size):
            batch = pages_data[i:i + batch_size]

            for data in batch:
                stmt = insert(PageRecherche).values(
                    page_id=str(data.get("page_id", "")),
                    page_name=data.get("page_name", ""),
                    lien_site=data.get("website", ""),
                    lien_fb_ad_library=data.get("fb_link", ""),
                    keywords=data.get("keywords", ""),
                    cms=data.get("cms", "Unknown"),
                    etat=data.get("etat", "XS"),
                    nombre_ads_active=data.get("ads_count", 0),
                    nombre_produits=data.get("product_count", 0),
                    dernier_scan=scan_time,
                    created_at=scan_time,
                    updated_at=scan_time,
                ).on_conflict_do_update(
                    index_elements=['page_id'],
                    set_={
                        'page_name': data.get("page_name", ""),
                        'lien_site': data.get("website", ""),
                        'nombre_ads_active': data.get("ads_count", 0),
                        'nombre_produits': data.get("product_count", 0),
                        'dernier_scan': scan_time,
                        'updated_at': scan_time,
                    }
                )
                session.execute(stmt)
                total += 1

    # Invalider le cache
    if CACHE_ENABLED:
        invalidate_stats_cache()

    return total


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA FILE D'ATTENTE (SEARCH QUEUE)
# ═══════════════════════════════════════════════════════════════════════════════

def create_search_queue(
    db: DatabaseManager,
    keywords: List[str],
    cms_filter: List[str],
    ads_min: int = 3,
    countries: str = "FR",
    languages: str = "fr",
    user_session: str = None,
    priority: int = 0
) -> int:
    """
    Crée une nouvelle entrée dans la file d'attente.

    Args:
        db: Instance DatabaseManager
        keywords: Liste des mots-clés
        cms_filter: Liste des CMS à inclure
        ads_min: Nombre minimum d'ads
        countries: Pays (défaut FR)
        languages: Langues (défaut fr)
        user_session: ID de session utilisateur
        priority: Priorité (0 = normale)

    Returns:
        ID de la recherche créée
    """
    import json

    with db.get_session() as session:
        queue_entry = SearchQueue(
            keywords=json.dumps(keywords),
            cms_filter=json.dumps(cms_filter),
            ads_min=ads_min,
            countries=countries,
            languages=languages,
            user_session=user_session,
            priority=priority,
            status="pending",
            phases_data=json.dumps([])
        )
        session.add(queue_entry)
        session.flush()
        return queue_entry.id


def get_search_queue(db: DatabaseManager, search_id: int) -> Optional[SearchQueue]:
    """Récupère une entrée de la queue par son ID"""
    with db.get_session() as session:
        return session.query(SearchQueue).filter(SearchQueue.id == search_id).first()


def get_pending_searches(db: DatabaseManager, limit: int = 5) -> List[SearchQueue]:
    """
    Récupère les recherches en attente, triées par priorité et date.

    Args:
        db: Instance DatabaseManager
        limit: Nombre maximum de recherches à retourner

    Returns:
        Liste des recherches en attente
    """
    with db.get_session() as session:
        return session.query(SearchQueue).filter(
            SearchQueue.status == "pending"
        ).order_by(
            SearchQueue.priority.desc(),
            SearchQueue.created_at.asc()
        ).limit(limit).all()


def get_user_searches(
    db: DatabaseManager,
    user_session: str = None,
    include_completed: bool = True,
    limit: int = 20
) -> List[SearchQueue]:
    """
    Récupère les recherches d'un utilisateur.

    Args:
        db: Instance DatabaseManager
        user_session: ID de session (si None, retourne toutes)
        include_completed: Inclure les recherches terminées
        limit: Nombre maximum

    Returns:
        Liste des recherches
    """
    with db.get_session() as session:
        query = session.query(SearchQueue)

        if user_session:
            query = query.filter(SearchQueue.user_session == user_session)

        if not include_completed:
            query = query.filter(SearchQueue.status.in_(["pending", "running"]))

        return query.order_by(SearchQueue.created_at.desc()).limit(limit).all()


def get_active_searches(db: DatabaseManager) -> List[SearchQueue]:
    """Récupère toutes les recherches actives (pending ou running)"""
    with db.get_session() as session:
        return session.query(SearchQueue).filter(
            SearchQueue.status.in_(["pending", "running"])
        ).order_by(SearchQueue.created_at.asc()).all()


def get_interrupted_searches(db: DatabaseManager, user_session: str = None) -> List[SearchQueue]:
    """Récupère les recherches interrompues"""
    with db.get_session() as session:
        query = session.query(SearchQueue).filter(SearchQueue.status == "interrupted")
        if user_session:
            query = query.filter(SearchQueue.user_session == user_session)
        return query.order_by(SearchQueue.created_at.desc()).all()


def update_search_queue_status(
    db: DatabaseManager,
    search_id: int,
    status: str,
    search_log_id: int = None,
    error: str = None
):
    """
    Met à jour le statut d'une recherche.

    Args:
        db: Instance DatabaseManager
        search_id: ID de la recherche
        status: Nouveau statut
        search_log_id: ID du SearchLog si terminée
        error: Message d'erreur si échec
    """
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if search:
            search.status = status

            if status == "running" and not search.started_at:
                search.started_at = datetime.utcnow()

            if status in ("completed", "failed", "cancelled"):
                search.completed_at = datetime.utcnow()

            if search_log_id:
                search.search_log_id = search_log_id

            if error:
                search.error_message = error


def update_search_queue_progress(
    db: DatabaseManager,
    search_id: int,
    phase: int,
    phase_name: str,
    percent: int,
    message: str,
    stats: Dict = None,
    phases_data: List = None
):
    """
    Met à jour la progression d'une recherche.

    Args:
        db: Instance DatabaseManager
        search_id: ID de la recherche
        phase: Numéro de phase actuelle
        phase_name: Nom de la phase
        percent: Pourcentage de progression globale
        message: Message de progression
        stats: Stats de la phase actuelle
        phases_data: Données complètes des phases
    """
    import json

    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if search:
            search.current_phase = phase
            search.current_phase_name = phase_name
            search.progress_percent = percent
            search.progress_message = message
            search.updated_at = datetime.utcnow()  # Marquer comme mis à jour

            if phases_data is not None:
                search.phases_data = json.dumps(phases_data)


def cancel_search_queue(db: DatabaseManager, search_id: int) -> bool:
    """
    Annule une recherche en attente.

    Args:
        db: Instance DatabaseManager
        search_id: ID de la recherche

    Returns:
        True si annulée, False sinon
    """
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if search and search.status == "pending":
            search.status = "cancelled"
            search.completed_at = datetime.utcnow()
            return True
        return False


def restart_search_queue(db: DatabaseManager, search_id: int) -> bool:
    """
    Relance une recherche interrompue ou échouée.

    Args:
        db: Instance DatabaseManager
        search_id: ID de la recherche

    Returns:
        True si relancée, False sinon
    """
    with db.get_session() as session:
        search = session.query(SearchQueue).filter(SearchQueue.id == search_id).first()
        if search and search.status in ("interrupted", "failed"):
            search.status = "pending"
            search.started_at = None
            search.completed_at = None
            search.error_message = None
            search.current_phase = 0
            search.progress_percent = 0
            search.progress_message = None
            return True
        return False


def recover_interrupted_searches(db: DatabaseManager) -> int:
    """
    Marque les recherches 'running' comme 'interrupted' si elles n'ont pas été
    mises à jour récemment (plus de 2 minutes).
    Appelé au démarrage de l'application.

    Returns:
        Nombre de recherches interrompues
    """
    from datetime import timedelta

    # Seuil: une recherche non mise à jour depuis 2 minutes est considérée comme morte
    threshold = datetime.utcnow() - timedelta(minutes=2)

    with db.get_session() as session:
        running = session.query(SearchQueue).filter(
            SearchQueue.status == "running"
        ).all()

        count = 0
        for search in running:
            # Utiliser updated_at si disponible, sinon started_at
            last_activity = search.updated_at or search.started_at or search.created_at

            # Ne marquer comme interrompue que si pas d'activité récente
            if last_activity and last_activity < threshold:
                search.status = "interrupted"
                search.error_message = "Service redémarré - recherche interrompue"
                count += 1
                print(f"[DB] Recherche #{search.id} marquée comme interrompue (dernière activité: {last_activity})")
            else:
                print(f"[DB] Recherche #{search.id} toujours active (dernière activité: {last_activity})")

        return count


def cleanup_old_queue_entries(db: DatabaseManager, days: int = 30) -> int:
    """
    Supprime les anciennes entrées de la queue.

    Args:
        db: Instance DatabaseManager
        days: Âge maximum en jours

    Returns:
        Nombre d'entrées supprimées
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with db.get_session() as session:
        deleted = session.query(SearchQueue).filter(
            SearchQueue.status.in_(["completed", "failed", "cancelled"]),
            SearchQueue.created_at < cutoff
        ).delete(synchronize_session='fetch')

        return deleted


def get_queue_stats(db: DatabaseManager) -> Dict:
    """Retourne les statistiques de la queue"""
    from sqlalchemy import func

    with db.get_session() as session:
        stats = session.query(
            SearchQueue.status,
            func.count(SearchQueue.id)
        ).group_by(SearchQueue.status).all()

        result = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "interrupted": 0
        }

        for status, count in stats:
            result[status] = count

        result["total"] = sum(result.values())
        result["active"] = result["pending"] + result["running"]

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA TAXONOMIE DE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_taxonomy(db: DatabaseManager, active_only: bool = True) -> List[ClassificationTaxonomy]:
    """Récupère toute la taxonomie"""
    with db.get_session() as session:
        query = session.query(ClassificationTaxonomy)
        if active_only:
            query = query.filter(ClassificationTaxonomy.is_active == True)
        return query.order_by(
            ClassificationTaxonomy.sort_order,
            ClassificationTaxonomy.category,
            ClassificationTaxonomy.subcategory
        ).all()


def get_taxonomy_by_category(db: DatabaseManager, category: str) -> List[ClassificationTaxonomy]:
    """Récupère les sous-catégories d'une catégorie"""
    with db.get_session() as session:
        return session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.category == category,
            ClassificationTaxonomy.is_active == True
        ).order_by(ClassificationTaxonomy.sort_order).all()


def get_taxonomy_categories(db: DatabaseManager) -> List[str]:
    """Récupère la liste unique des catégories"""
    with db.get_session() as session:
        results = session.query(ClassificationTaxonomy.category).filter(
            ClassificationTaxonomy.is_active == True
        ).distinct().order_by(ClassificationTaxonomy.category).all()
        return [r[0] for r in results]


def add_taxonomy_entry(
    db: DatabaseManager,
    category: str,
    subcategory: str,
    description: str = None,
    sort_order: int = 0
) -> int:
    """Ajoute une entrée à la taxonomie"""
    with db.get_session() as session:
        entry = ClassificationTaxonomy(
            category=category,
            subcategory=subcategory,
            description=description,
            sort_order=sort_order,
            is_active=True
        )
        session.add(entry)
        session.flush()
        return entry.id


def update_taxonomy_entry(
    db: DatabaseManager,
    entry_id: int,
    category: str = None,
    subcategory: str = None,
    description: str = None,
    sort_order: int = None,
    is_active: bool = None
) -> bool:
    """Met à jour une entrée de la taxonomie"""
    with db.get_session() as session:
        entry = session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.id == entry_id
        ).first()
        if not entry:
            return False

        if category is not None:
            entry.category = category
        if subcategory is not None:
            entry.subcategory = subcategory
        if description is not None:
            entry.description = description
        if sort_order is not None:
            entry.sort_order = sort_order
        if is_active is not None:
            entry.is_active = is_active

        return True


def delete_taxonomy_entry(db: DatabaseManager, entry_id: int) -> bool:
    """Supprime une entrée de la taxonomie"""
    with db.get_session() as session:
        deleted = session.query(ClassificationTaxonomy).filter(
            ClassificationTaxonomy.id == entry_id
        ).delete()
        return deleted > 0


def init_default_taxonomy(db: DatabaseManager) -> int:
    """Initialise la taxonomie par défaut si vide"""
    with db.get_session() as session:
        count = session.query(ClassificationTaxonomy).count()
        if count > 0:
            return 0  # Déjà initialisée

    # Taxonomie par défaut
    default_taxonomy = [
        # Mode & Accessoires
        ("Mode & Accessoires", "Vêtements Femme", "Robes, tops, bas, lingerie, manteaux"),
        ("Mode & Accessoires", "Vêtements Homme", "Costumes, casual, sportswear, sous-vêtements"),
        ("Mode & Accessoires", "Mode Enfant & Bébé", "Vêtements fille/garçon, layette, chaussures enfant"),
        ("Mode & Accessoires", "Chaussures", "Sneakers, ville, bottes, sandales, sport"),
        ("Mode & Accessoires", "Maroquinerie & Bagagerie", "Sacs à main, valises, sacs à dos, portefeuilles"),
        ("Mode & Accessoires", "Accessoires de mode", "Chapeaux, écharpes, ceintures, gants, cravates"),
        ("Mode & Accessoires", "Bijoux & Joaillerie", "Montres, bagues, colliers, bijoux fantaisie"),

        # High-Tech & Électronique
        ("High-Tech & Électronique", "Téléphonie", "Smartphones, reconditionné, coques, chargeurs"),
        ("High-Tech & Électronique", "Informatique", "Ordinateurs portables, PC fixes, tablettes, moniteurs"),
        ("High-Tech & Électronique", "Composants & Périphériques", "Cartes graphiques, disques durs, claviers/souris, imprimantes"),
        ("High-Tech & Électronique", "Image & Son", "Téléviseurs, vidéoprojecteurs, enceintes, casques audio, Hi-Fi"),
        ("High-Tech & Électronique", "Photo & Vidéo", "Appareils photo, objectifs, drones, caméras sport"),
        ("High-Tech & Électronique", "Gaming", "Consoles (PS5/Xbox/Switch), jeux vidéo, accessoires gaming"),
        ("High-Tech & Électronique", "Maison Connectée", "Assistants vocaux, sécurité, éclairage connecté"),

        # Maison, Jardin & Bricolage
        ("Maison, Jardin & Bricolage", "Mobilier", "Canapés, lits, tables, chaises, rangements"),
        ("Maison, Jardin & Bricolage", "Décoration & Linge", "Luminaires, tapis, rideaux, linge de lit, objets déco"),
        ("Maison, Jardin & Bricolage", "Cuisine & Art de la table", "Ustensiles, poêles/casseroles, vaisselle, verres"),
        ("Maison, Jardin & Bricolage", "Gros Électroménager", "Lave-linge, frigo, four, lave-vaisselle"),
        ("Maison, Jardin & Bricolage", "Petit Électroménager", "Aspirateurs, cafetières, robots cuisine, fers à repasser"),
        ("Maison, Jardin & Bricolage", "Bricolage & Outillage", "Outillage électroportatif, plomberie, électricité"),
        ("Maison, Jardin & Bricolage", "Jardin & Piscine", "Mobilier de jardin, barbecues, tondeuses, piscines"),

        # Beauté, Santé & Bien-être
        ("Beauté, Santé & Bien-être", "Maquillage", "Teint, yeux, lèvres, ongles"),
        ("Beauté, Santé & Bien-être", "Soins Visage & Corps", "Crèmes, sérums, nettoyants, solaires"),
        ("Beauté, Santé & Bien-être", "Capillaire", "Shampoings, colorations, lisseurs/sèche-cheveux"),
        ("Beauté, Santé & Bien-être", "Parfums", "Femme, Homme, Enfant, bougies parfumées"),
        ("Beauté, Santé & Bien-être", "Santé & Parapharmacie", "Premiers secours, vitamines, hygiène dentaire"),
        ("Beauté, Santé & Bien-être", "Bien-être & Naturel", "Huiles essentielles, CBD, compléments alimentaires"),
        ("Beauté, Santé & Bien-être", "Hygiène & Soin Bébé", "Couches, soins bébé, maternité"),

        # Sports & Loisirs
        ("Sports & Loisirs", "Vêtements & Chaussures de Sport", "Running, fitness, maillots, thermique"),
        ("Sports & Loisirs", "Matériel de Fitness", "Musculation, tapis de course, yoga"),
        ("Sports & Loisirs", "Sports d'Extérieur", "Randonnée, camping, escalade, ski"),
        ("Sports & Loisirs", "Sports d'Équipe & Raquettes", "Football, tennis, basket, rugby"),
        ("Sports & Loisirs", "Cycles & Glisse", "Vélos, trottinettes, skate, surf"),
        ("Sports & Loisirs", "Nutrition Sportive", "Protéines, barres énergétiques, boissons"),

        # Culture, Jeux & Divertissement
        ("Culture, Jeux & Divertissement", "Livres & Presse", "Romans, BD/Manga, scolaire, ebooks"),
        ("Culture, Jeux & Divertissement", "Musique & Instruments", "Guitares, pianos, DJ, partitions, vinyles"),
        ("Culture, Jeux & Divertissement", "Jeux & Jouets", "Jeux de société, poupées, construction, éducatif"),
        ("Culture, Jeux & Divertissement", "Cinéma & Séries", "DVD, Blu-Ray, produits dérivés"),
        ("Culture, Jeux & Divertissement", "Loisirs Créatifs", "Beaux-arts, mercerie, scrapbooking, papeterie"),

        # Alimentation & Boissons
        ("Alimentation & Boissons", "Épicerie Salée & Sucrée", "Conserves, pâtes, chocolats, biscuits"),
        ("Alimentation & Boissons", "Boissons & Cave", "Vins, spiritueux, bières, sodas, café/thé"),
        ("Alimentation & Boissons", "Produits Frais", "Boucherie, fromagerie, fruits & légumes"),
        ("Alimentation & Boissons", "Spécialisé / Gourmet", "Bio, sans gluten, produits régionaux, épicerie fine"),

        # Animaux
        ("Animaux", "Chiens", "Croquettes, laisses, couchages, jouets"),
        ("Animaux", "Chats", "Arbres à chat, litière, nourriture"),
        ("Animaux", "NAC & Autres", "Rongeurs, oiseaux, aquariophilie, reptiles"),

        # Auto, Moto & Industrie
        ("Auto, Moto & Industrie", "Pièces Auto/Moto", "Pneus, batteries, pièces mécaniques, huiles"),
        ("Auto, Moto & Industrie", "Équipement & Accessoires", "Casques moto, nettoyage, audio embarqué"),
        ("Auto, Moto & Industrie", "Industrie & Bureau", "Fournitures de bureau, mobilier pro, emballage"),

        # Divers & Spécialisé
        ("Divers & Spécialisé", "Adulte / Charme", "Lovestore, lingerie sexy"),
        ("Divers & Spécialisé", "Cadeaux & Gadgets", "Box mensuelles, gadgets humoristiques, personnalisation"),
        ("Divers & Spécialisé", "Services", "Billetterie, voyage, impression photo, formations"),
        ("Divers & Spécialisé", "Généraliste", "Marketplaces vendant de tout sans dominante"),
    ]

    added = 0
    for i, (cat, subcat, desc) in enumerate(default_taxonomy):
        add_taxonomy_entry(db, cat, subcat, desc, sort_order=i)
        added += 1

    return added


def build_taxonomy_prompt(db: DatabaseManager) -> str:
    """Construit le prompt de taxonomie à partir de la base de données"""
    taxonomy = get_all_taxonomy(db, active_only=True)

    if not taxonomy:
        return ""

    # Grouper par catégorie
    categories = {}
    for entry in taxonomy:
        if entry.category not in categories:
            categories[entry.category] = []
        categories[entry.category].append(entry)

    # Construire le texte
    lines = []
    for i, (cat_name, entries) in enumerate(categories.items(), 1):
        lines.append(f"\n{i}. {cat_name}")
        for entry in entries:
            desc = f": {entry.description}" if entry.description else ""
            lines.append(f"   - {entry.subcategory}{desc}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DE LA CLASSIFICATION DES PAGES
# ═══════════════════════════════════════════════════════════════════════════════

def get_unclassified_pages(
    db: DatabaseManager,
    limit: int = 100,
    with_website_only: bool = True
) -> List[PageRecherche]:
    """Récupère les pages non classifiées"""
    with db.get_session() as session:
        query = session.query(PageRecherche).filter(
            (PageRecherche.thematique == None) | (PageRecherche.thematique == "")
        )
        if with_website_only:
            query = query.filter(
                PageRecherche.lien_site != None,
                PageRecherche.lien_site != ""
            )
        return query.order_by(PageRecherche.created_at.desc()).limit(limit).all()


def get_pages_for_classification(
    db: DatabaseManager,
    page_ids: List[str] = None,
    limit: int = 100
) -> List[Dict]:
    """Récupère les pages à classifier avec leurs URLs"""
    with db.get_session() as session:
        query = session.query(PageRecherche)

        if page_ids:
            query = query.filter(PageRecherche.page_id.in_(page_ids))
        else:
            # Pages non classifiées avec URL
            query = query.filter(
                (PageRecherche.thematique == None) | (PageRecherche.thematique == ""),
                PageRecherche.lien_site != None,
                PageRecherche.lien_site != ""
            )

        pages = query.limit(limit).all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "url": p.lien_site,
                "cms": p.cms
            }
            for p in pages
        ]


def update_page_classification(
    db: DatabaseManager,
    page_id: str,
    category: str,
    subcategory: str,
    confidence: float
) -> bool:
    """Met à jour la classification d'une page"""
    with db.get_session() as session:
        page = session.query(PageRecherche).filter(
            PageRecherche.page_id == page_id
        ).first()

        if not page:
            return False

        page.thematique = category
        page.subcategory = subcategory
        page.classification_confidence = confidence
        page.classified_at = datetime.utcnow()

        return True


def update_pages_classification_batch(
    db: DatabaseManager,
    classifications: List[Dict]
) -> int:
    """
    Met à jour plusieurs classifications en batch.

    Args:
        db: DatabaseManager
        classifications: Liste de dicts avec page_id, category, subcategory, confidence

    Returns:
        Nombre de pages mises à jour
    """
    updated = 0
    with db.get_session() as session:
        for c in classifications:
            page = session.query(PageRecherche).filter(
                PageRecherche.page_id == c["page_id"]
            ).first()

            if page:
                page.thematique = c.get("category", "")
                page.subcategory = c.get("subcategory", "")
                page.classification_confidence = c.get("confidence", 0.0)
                page.classified_at = datetime.utcnow()
                updated += 1

    return updated


def get_classification_stats(db: DatabaseManager) -> Dict:
    """Statistiques de classification"""
    from sqlalchemy import func

    with db.get_session() as session:
        total = session.query(func.count(PageRecherche.id)).scalar() or 0

        classified = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.thematique != None,
            PageRecherche.thematique != ""
        ).scalar() or 0

        unclassified = total - classified

        # Top catégories
        top_categories = session.query(
            PageRecherche.thematique,
            func.count(PageRecherche.id).label('count')
        ).filter(
            PageRecherche.thematique != None,
            PageRecherche.thematique != ""
        ).group_by(
            PageRecherche.thematique
        ).order_by(
            func.count(PageRecherche.id).desc()
        ).limit(10).all()

        return {
            "total": total,
            "classified": classified,
            "unclassified": unclassified,
            "classification_rate": round(classified / total * 100, 1) if total > 0 else 0,
            "top_categories": [{"category": c, "count": n} for c, n in top_categories]
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS DE MIGRATION BATCH
# ═══════════════════════════════════════════════════════════════════════════════

def migration_add_country_to_all_pages(db: DatabaseManager, country: str = "FR") -> int:
    """
    Ajoute un pays à toutes les pages existantes (si pas déjà présent).

    Args:
        db: DatabaseManager
        country: Code pays (défaut: "FR")

    Returns:
        Nombre de pages mises à jour
    """
    country = country.upper().strip()
    updated = 0

    with db.get_session() as session:
        # Récupérer toutes les pages
        pages = session.query(PageRecherche).all()

        for page in pages:
            existing_countries = []
            if page.pays:
                existing_countries = [c.strip().upper() for c in page.pays.split(",") if c.strip()]

            if country not in existing_countries:
                existing_countries.append(country)
                page.pays = ",".join(existing_countries)
                updated += 1

    return updated


def get_all_pages_for_classification(
    db: DatabaseManager,
    include_classified: bool = True,
    limit: int = None
) -> List[Dict]:
    """
    Récupère toutes les pages pour classification (y compris déjà classifiées).

    Args:
        db: DatabaseManager
        include_classified: Inclure les pages déjà classifiées
        limit: Limite de pages (None = toutes)

    Returns:
        Liste de pages avec page_id et url
    """
    with db.get_session() as session:
        query = session.query(PageRecherche).filter(
            PageRecherche.lien_site != None,
            PageRecherche.lien_site != ""
        )

        if not include_classified:
            query = query.filter(
                (PageRecherche.thematique == None) | (PageRecherche.thematique == "")
            )

        if limit:
            query = query.limit(limit)

        pages = query.all()

        return [
            {
                "page_id": p.page_id,
                "page_name": p.page_name,
                "url": p.lien_site,
                "cms": p.cms,
                "current_thematique": p.thematique,
                "current_subcategory": p.subcategory
            }
            for p in pages
        ]


def get_pages_count(db: DatabaseManager) -> Dict:
    """
    Compte les pages par statut de classification et pays.

    Returns:
        Dict avec les comptages
    """
    from sqlalchemy import func

    with db.get_session() as session:
        total = session.query(func.count(PageRecherche.id)).scalar() or 0

        with_url = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.lien_site != None,
            PageRecherche.lien_site != ""
        ).scalar() or 0

        classified = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.thematique != None,
            PageRecherche.thematique != ""
        ).scalar() or 0

        with_fr = session.query(func.count(PageRecherche.id)).filter(
            PageRecherche.pays.ilike("%FR%")
        ).scalar() or 0

        return {
            "total": total,
            "with_url": with_url,
            "classified": classified,
            "unclassified": with_url - classified,
            "with_fr": with_fr,
            "without_fr": total - with_fr
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS D'ARCHIVAGE
# ═══════════════════════════════════════════════════════════════════════════════

def get_archive_stats(db: DatabaseManager) -> Dict:
    """
    Recupere les statistiques des tables principales et archives.

    Returns:
        Dict avec comptages pour chaque table
    """
    from sqlalchemy import func

    stats = {}

    with db.get_session() as session:
        # Tables principales
        stats["suivi_page"] = session.query(func.count(SuiviPage.id)).scalar() or 0
        stats["liste_ads_recherche"] = session.query(func.count(AdsRecherche.id)).scalar() or 0
        stats["winning_ads"] = session.query(func.count(WinningAds.id)).scalar() or 0

        # Tables d'archive
        stats["suivi_page_archive"] = session.query(func.count(SuiviPageArchive.id)).scalar() or 0
        stats["liste_ads_recherche_archive"] = session.query(func.count(AdsRechercheArchive.id)).scalar() or 0
        stats["winning_ads_archive"] = session.query(func.count(WinningAdsArchive.id)).scalar() or 0

        # Donnees archivables (>90 jours par defaut)
        threshold = datetime.utcnow() - timedelta(days=90)
        stats["suivi_page_archivable"] = session.query(func.count(SuiviPage.id)).filter(
            SuiviPage.date_scan < threshold
        ).scalar() or 0
        stats["liste_ads_recherche_archivable"] = session.query(func.count(AdsRecherche.id)).filter(
            AdsRecherche.date_scan < threshold
        ).scalar() or 0
        stats["winning_ads_archivable"] = session.query(func.count(WinningAds.id)).filter(
            WinningAds.date_scan < threshold
        ).scalar() or 0

    return stats


def archive_old_data(
    db: DatabaseManager,
    days_threshold: int = 90,
    batch_size: int = 1000
) -> Dict:
    """
    Archive les donnees plus vieilles que le seuil specifie.

    Args:
        db: DatabaseManager
        days_threshold: Nombre de jours (defaut: 90)
        batch_size: Taille des batches pour eviter les timeouts

    Returns:
        Dict avec comptages des entrees archivees
    """
    threshold = datetime.utcnow() - timedelta(days=days_threshold)
    archived = {"suivi_page": 0, "liste_ads_recherche": 0, "winning_ads": 0}

    # Archive suivi_page
    with db.get_session() as session:
        while True:
            old_entries = session.query(SuiviPage).filter(
                SuiviPage.date_scan < threshold
            ).limit(batch_size).all()

            if not old_entries:
                break

            for entry in old_entries:
                archive_entry = SuiviPageArchive(
                    original_id=entry.id,
                    cle_suivi=entry.cle_suivi,
                    page_id=entry.page_id,
                    nom_site=entry.nom_site,
                    nombre_ads_active=entry.nombre_ads_active,
                    nombre_produits=entry.nombre_produits,
                    date_scan=entry.date_scan
                )
                session.add(archive_entry)
                session.delete(entry)
                archived["suivi_page"] += 1

            session.commit()

    # Archive liste_ads_recherche
    with db.get_session() as session:
        while True:
            old_entries = session.query(AdsRecherche).filter(
                AdsRecherche.date_scan < threshold
            ).limit(batch_size).all()

            if not old_entries:
                break

            for entry in old_entries:
                archive_entry = AdsRechercheArchive(
                    original_id=entry.id,
                    ad_id=entry.ad_id,
                    page_id=entry.page_id,
                    page_name=entry.page_name,
                    ad_creation_time=entry.ad_creation_time,
                    ad_creative_bodies=entry.ad_creative_bodies,
                    ad_creative_link_captions=entry.ad_creative_link_captions,
                    ad_creative_link_titles=entry.ad_creative_link_titles,
                    ad_snapshot_url=entry.ad_snapshot_url,
                    eu_total_reach=entry.eu_total_reach,
                    languages=entry.languages,
                    country=entry.country,
                    publisher_platforms=entry.publisher_platforms,
                    target_ages=entry.target_ages,
                    target_gender=entry.target_gender,
                    beneficiary_payers=entry.beneficiary_payers,
                    date_scan=entry.date_scan
                )
                session.add(archive_entry)
                session.delete(entry)
                archived["liste_ads_recherche"] += 1

            session.commit()

    # Archive winning_ads
    with db.get_session() as session:
        while True:
            old_entries = session.query(WinningAds).filter(
                WinningAds.date_scan < threshold
            ).limit(batch_size).all()

            if not old_entries:
                break

            for entry in old_entries:
                archive_entry = WinningAdsArchive(
                    original_id=entry.id,
                    ad_id=entry.ad_id,
                    page_id=entry.page_id,
                    page_name=entry.page_name,
                    ad_creation_time=entry.ad_creation_time,
                    ad_age_days=entry.ad_age_days,
                    eu_total_reach=entry.eu_total_reach,
                    matched_criteria=entry.matched_criteria,
                    ad_creative_bodies=entry.ad_creative_bodies,
                    ad_creative_link_captions=entry.ad_creative_link_captions,
                    ad_creative_link_titles=entry.ad_creative_link_titles,
                    ad_snapshot_url=entry.ad_snapshot_url,
                    lien_site=entry.lien_site,
                    date_scan=entry.date_scan
                )
                session.add(archive_entry)
                session.delete(entry)
                archived["winning_ads"] += 1

            session.commit()

    return archived


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS DE CACHE API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_cache_key(cache_type: str, **params) -> str:
    """
    Genere une cle de cache unique basee sur les parametres.

    Args:
        cache_type: Type de cache (search_ads, page_info, etc.)
        **params: Parametres de la requete

    Returns:
        Cle de cache unique
    """
    import hashlib
    import json

    # Trier les params pour avoir une cle consistante
    sorted_params = sorted(params.items())
    param_str = json.dumps(sorted_params, sort_keys=True)
    hash_str = hashlib.md5(param_str.encode()).hexdigest()[:16]

    return f"{cache_type}:{hash_str}"


def get_cached_response(
    db: DatabaseManager,
    cache_key: str
) -> Optional[Dict]:
    """
    Recupere une reponse du cache si elle existe et n'est pas expiree.

    Args:
        db: DatabaseManager
        cache_key: Cle de cache

    Returns:
        Donnees cachees ou None si cache miss
    """
    import json

    with db.get_session() as session:
        cache_entry = session.query(APICache).filter(
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.utcnow()
        ).first()

        if cache_entry:
            # Incrementer le hit count
            cache_entry.hit_count = (cache_entry.hit_count or 0) + 1
            session.commit()

            try:
                return json.loads(cache_entry.response_data)
            except:
                return None

    return None


def set_cached_response(
    db: DatabaseManager,
    cache_key: str,
    cache_type: str,
    response_data: Dict,
    ttl_hours: int = 6
) -> bool:
    """
    Stocke une reponse dans le cache.

    Args:
        db: DatabaseManager
        cache_key: Cle de cache
        cache_type: Type de cache
        response_data: Donnees a cacher
        ttl_hours: Duree de vie en heures (defaut: 6h)

    Returns:
        True si succes
    """
    import json

    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    with db.get_session() as session:
        # Verifier si existe deja
        existing = session.query(APICache).filter(
            APICache.cache_key == cache_key
        ).first()

        if existing:
            existing.response_data = json.dumps(response_data)
            existing.expires_at = expires_at
            existing.created_at = datetime.utcnow()
        else:
            cache_entry = APICache(
                cache_key=cache_key,
                cache_type=cache_type,
                response_data=json.dumps(response_data),
                expires_at=expires_at
            )
            session.add(cache_entry)

        session.commit()

    return True


def get_cache_stats(db: DatabaseManager) -> Dict:
    """
    Recupere les statistiques du cache.

    Returns:
        Dict avec stats du cache
    """
    from sqlalchemy import func

    with db.get_session() as session:
        total_entries = session.query(func.count(APICache.id)).scalar() or 0

        valid_entries = session.query(func.count(APICache.id)).filter(
            APICache.expires_at > datetime.utcnow()
        ).scalar() or 0

        expired_entries = total_entries - valid_entries

        total_hits = session.query(func.sum(APICache.hit_count)).scalar() or 0

        # Stats par type
        by_type = session.query(
            APICache.cache_type,
            func.count(APICache.id),
            func.sum(APICache.hit_count)
        ).group_by(APICache.cache_type).all()

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "total_hits": total_hits,
            "by_type": [
                {"type": t[0], "count": t[1], "hits": t[2] or 0}
                for t in by_type
            ]
        }


def clear_expired_cache(db: DatabaseManager) -> int:
    """
    Supprime les entrees de cache expirees.

    Returns:
        Nombre d'entrees supprimees
    """
    with db.get_session() as session:
        deleted = session.query(APICache).filter(
            APICache.expires_at < datetime.utcnow()
        ).delete()
        session.commit()

    return deleted


def clear_all_cache(db: DatabaseManager) -> int:
    """
    Supprime tout le cache.

    Returns:
        Nombre d'entrees supprimees
    """
    with db.get_session() as session:
        deleted = session.query(APICache).delete()
        session.commit()

    return deleted
