"""
Dashboard Streamlit pour Meta Ads Analyzer.

Design moderne avec navigation latérale.
Module principal de l'interface utilisateur.
"""
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import os
import sys
import time
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter la racine du projet au path pour les imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Import des composants UI
from src.presentation.streamlit.components import (
    # Charts
    CHART_COLORS, CHART_LAYOUT,
    info_card, chart_header,
    create_horizontal_bar_chart, create_donut_chart,
    create_trend_chart, create_gauge_chart,
    create_metric_card, create_comparison_bars,
    # Badges
    STATE_COLORS, CMS_COLORS,
    get_state_badge, get_cms_badge, format_state_for_df,
    apply_custom_css,
    # Utils
    calculate_page_score, get_score_color, get_score_level,
    export_to_csv, df_to_csv, format_number, format_percentage,
    format_time_elapsed, truncate_text, get_delta_indicator,
)

# Import des pages extraites
from src.presentation.streamlit.pages import (
    render_blacklist,
    render_favorites,
    render_collections,
    render_tags,
    render_scheduled_scans,
    render_settings,
    render_winning_ads,
    render_analytics,
    render_search_logs,
)

# Import du module d'authentification
from src.presentation.streamlit.auth import (
    render_login_page,
    require_auth,
    can_access_page,
    get_current_user,
    logout,
    is_authenticated,
    render_user_management,
)
from src.presentation.streamlit.auth.login_page import render_logout_button

# Infrastructure imports
from src.infrastructure.config import (
    AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES,
    MIN_ADS_INITIAL,
    DEFAULT_COUNTRIES,
    DATABASE_URL, MIN_ADS_SUIVI, MIN_ADS_LISTE,
    DEFAULT_STATE_THRESHOLDS, WINNING_AD_CRITERIA,
    META_DELAY_BETWEEN_KEYWORDS, META_DELAY_BETWEEN_BATCHES,
    WEB_DELAY_CMS_CHECK
)
from src.infrastructure.external_services.meta_api import (
    MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
)
from src.infrastructure.scrapers.web_analyzer import (
    analyze_website_complete,
    detect_cms_from_url,
)
from src.infrastructure.persistence.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, get_suivi_stats_filtered, search_pages,
    get_evolution_stats, get_page_evolution_history, get_etat_from_ads_count,
    add_to_blacklist, remove_from_blacklist, get_blacklist, get_blacklist_ids,
    is_winning_ad, save_winning_ads, get_winning_ads, get_winning_ads_stats,
    get_winning_ads_filtered, get_winning_ads_stats_filtered,
    get_winning_ads_by_page, get_cached_pages_info, get_dashboard_trends,
    # Tags
    get_all_tags, create_tag, delete_tag, add_tag_to_page,
    get_page_tags, get_pages_by_tag,
    # Notes
    get_page_notes, add_page_note,
    # Favorites
    get_favorites, is_favorite, add_favorite, remove_favorite, toggle_favorite,
    # Collections
    get_collections, create_collection, delete_collection,
    add_page_to_collection, remove_page_from_collection, get_collection_pages,
    # Saved Filters
    get_saved_filters, save_filter, delete_saved_filter,
    # Scheduled Scans
    get_scheduled_scans, create_scheduled_scan, update_scheduled_scan,
    delete_scheduled_scan,
    # Bulk actions
    bulk_add_to_blacklist, bulk_add_to_collection, bulk_add_tag, bulk_add_to_favorites,
    # Classification & Filtering
    get_taxonomy_categories, get_all_subcategories, get_all_countries
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_session_state():
    """Initialise le state de la session Streamlit"""
    defaults = {
        'search_results': None,
        'pages_final': {},
        'web_results': {},
        'page_ads': {},
        'search_running': False,
        'stats': {},
        'db': None,
        'container': None,  # Container hexagonal architecture
        'current_page': 'Dashboard',
        'countries': ['FR'],
        'languages': ['fr'],
        'state_thresholds': DEFAULT_STATE_THRESHOLDS.copy(),
        # Seuils de détection
        'detection_thresholds': {
            'min_ads_suivi': MIN_ADS_SUIVI,
            'min_ads_liste': MIN_ADS_LISTE,
        },
        # Nouvelles fonctionnalités
        'dark_mode': False,
        'selected_pages': [],  # Pour les actions groupées
        'bulk_mode': False,
        # Historique des recherches (max 10)
        'search_history': [],
        # Authentification
        'authenticated': False,
        'user': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_dark_mode():
    """Applique le thème sombre si activé"""
    if st.session_state.get('dark_mode', False):
        st.markdown("""
        <style>
            /* Dark mode styles */
            .stApp {
                background-color: #1a1a2e;
                color: #eaeaea;
            }
            .stSidebar {
                background-color: #16213e;
            }
            .stButton>button {
                background-color: #0f3460;
                color: white;
                border: 1px solid #1a1a2e;
            }
            .stButton>button:hover {
                background-color: #1a1a2e;
                border-color: #e94560;
            }
            .stTextInput>div>div>input {
                background-color: #16213e;
                color: #eaeaea;
            }
            .stSelectbox>div>div {
                background-color: #16213e;
            }
            div[data-testid="stMetricValue"] {
                color: #eaeaea;
            }
            .stExpander {
                background-color: #16213e;
                border-color: #0f3460;
            }
            .stDataFrame {
                background-color: #16213e;
            }
            div[data-testid="stMarkdownContainer"] p {
                color: #eaeaea;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #eaeaea !important;
            }
            .stAlert {
                background-color: #16213e;
            }
        </style>
        """, unsafe_allow_html=True)


def get_database() -> DatabaseManager:
    """Récupère ou initialise la connexion à la base de données"""
    if st.session_state.db is None:
        try:
            st.session_state.db = DatabaseManager(DATABASE_URL)
            st.session_state.db.create_tables()
            # Initialiser le container hexagonal avec le db_manager
            _init_hexagonal_container(st.session_state.db)
        except Exception as e:
            return None
    return st.session_state.db


def _init_hexagonal_container(db_manager: DatabaseManager) -> None:
    """Initialise le container d'architecture hexagonale."""
    if st.session_state.container is None:
        try:
            from src.infrastructure import Container
            st.session_state.container = Container.create(db_manager=db_manager)
        except Exception:
            # Fallback silencieux si l'import échoue
            pass


def get_hexagonal_container():
    """
    Récupère le container d'architecture hexagonale.

    Returns:
        Container ou None si non initialisé.

    Example:
        >>> container = get_hexagonal_container()
        >>> if container:
        ...     stats = container.page_view_model.get_statistics()
    """
    return st.session_state.get('container')


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT CSV HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def df_to_csv(df: pd.DataFrame) -> bytes:
    """Convertit un DataFrame en CSV bytes pour le téléchargement"""
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')


def render_csv_download(df: pd.DataFrame, filename: str, label: str = "📥 Exporter CSV"):
    """Affiche un bouton de téléchargement CSV pour un DataFrame"""
    if df is not None and len(df) > 0:
        csv_data = df_to_csv(df)
        st.download_button(
            label=label,
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key=f"download_{filename}_{hash(str(df.columns.tolist()))}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

def add_to_search_history(search_type: str, params: dict, results_count: int = 0):
    """Ajoute une recherche à l'historique"""
    from datetime import datetime

    history = st.session_state.get('search_history', [])

    entry = {
        'type': search_type,  # 'keywords' ou 'page_ids'
        'params': params,
        'results_count': results_count,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'display': _format_search_display(search_type, params)
    }

    # Éviter les doublons consécutifs
    if history and history[0].get('display') == entry['display']:
        history[0] = entry  # Mettre à jour le timestamp
    else:
        history.insert(0, entry)

    # Garder seulement les 10 dernières
    st.session_state.search_history = history[:10]


def _format_search_display(search_type: str, params: dict) -> str:
    """Formate l'affichage d'une recherche dans l'historique"""
    if search_type == 'keywords':
        keywords = params.get('keywords', [])
        kw_preview = ', '.join(keywords[:3])
        if len(keywords) > 3:
            kw_preview += f" +{len(keywords) - 3}"
        countries = ', '.join(params.get('countries', []))
        return f"🔤 {kw_preview} ({countries})"
    else:  # page_ids
        page_ids = params.get('page_ids', [])
        return f"🆔 {len(page_ids)} Page IDs"


def get_search_history() -> list:
    """Récupère l'historique des recherches"""
    return st.session_state.get('search_history', [])


def render_search_history_selector(key_prefix: str = ""):
    """Affiche un sélecteur pour les recherches récentes"""
    history = get_search_history()

    if not history:
        return None

    options = ["-- Recherches récentes --"] + [
        f"{h['display']} • {h['timestamp']}" for h in history
    ]

    selected = st.selectbox(
        "📜 Historique",
        options,
        index=0,
        key=f"history_select_{key_prefix}",
        label_visibility="collapsed"
    )

    if selected != options[0]:
        idx = options.index(selected) - 1
        return history[idx]

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSANT FILTRES RÉUTILISABLE (Thématique, Classification, Pays)
# ═══════════════════════════════════════════════════════════════════════════════

def render_classification_filters(
    db,
    key_prefix: str = "",
    show_thematique: bool = True,
    show_subcategory: bool = True,
    show_pays: bool = True,
    columns: int = 3
) -> dict:
    """
    Affiche les filtres de classification réutilisables.

    Args:
        db: DatabaseManager
        key_prefix: Préfixe pour les clés Streamlit (éviter conflits)
        show_thematique: Afficher le filtre thématique
        show_subcategory: Afficher le filtre classification
        show_pays: Afficher le filtre pays
        columns: Nombre de colonnes pour l'affichage

    Returns:
        Dict avec les valeurs sélectionnées:
        {
            "thematique": str or None,
            "subcategory": str or None,
            "pays": str or None
        }
    """
    result = {
        "thematique": None,
        "subcategory": None,
        "pays": None
    }

    # Déterminer les colonnes actives
    active_filters = []
    if show_thematique:
        active_filters.append("thematique")
    if show_subcategory:
        active_filters.append("subcategory")
    if show_pays:
        active_filters.append("pays")

    if not active_filters:
        return result

    # Créer les colonnes
    cols = st.columns(min(len(active_filters), columns))
    col_idx = 0

    # Récupérer les options
    categories = get_taxonomy_categories(db) if show_thematique else []
    countries = get_all_countries(db) if show_pays else []

    # Filtre Thématique (catégorie principale)
    selected_thematique = "Toutes"
    if show_thematique:
        with cols[col_idx % len(cols)]:
            thematique_options = ["Toutes"] + categories
            selected_thematique = st.selectbox(
                "Thématique",
                thematique_options,
                index=0,
                key=f"{key_prefix}_thematique"
            )
            if selected_thematique != "Toutes":
                result["thematique"] = selected_thematique
        col_idx += 1

    # Filtre Classification (dépend de la thématique sélectionnée)
    if show_subcategory:
        with cols[col_idx % len(cols)]:
            # Filtrer les classifications selon la thématique choisie
            if selected_thematique != "Toutes":
                subcategories = get_all_subcategories(db, category=selected_thematique)
            else:
                subcategories = get_all_subcategories(db)

            subcategory_options = ["Toutes"] + subcategories
            selected_subcategory = st.selectbox(
                "Classification",
                subcategory_options,
                index=0,
                key=f"{key_prefix}_subcategory"
            )
            if selected_subcategory != "Toutes":
                result["subcategory"] = selected_subcategory
        col_idx += 1

    # Filtre Pays
    if show_pays:
        with cols[col_idx % len(cols)]:
            # Noms lisibles pour les pays
            country_names = {
                "FR": "🇫🇷 France",
                "DE": "🇩🇪 Allemagne",
                "ES": "🇪🇸 Espagne",
                "IT": "🇮🇹 Italie",
                "GB": "🇬🇧 Royaume-Uni",
                "US": "🇺🇸 États-Unis",
                "BE": "🇧🇪 Belgique",
                "CH": "🇨🇭 Suisse",
                "NL": "🇳🇱 Pays-Bas",
                "PT": "🇵🇹 Portugal",
                "AT": "🇦🇹 Autriche",
                "CA": "🇨🇦 Canada",
                "AU": "🇦🇺 Australie",
                "LU": "🇱🇺 Luxembourg",
                "PL": "🇵🇱 Pologne",
            }
            pays_display = ["Tous"] + [country_names.get(c, c) for c in countries]
            pays_values = [None] + countries

            selected_pays_idx = st.selectbox(
                "🌍 Pays",
                range(len(pays_display)),
                format_func=lambda i: pays_display[i],
                index=0,
                key=f"{key_prefix}_pays"
            )
            if selected_pays_idx > 0:
                result["pays"] = pays_values[selected_pays_idx]

    return result


def render_date_filter(key_prefix: str = "") -> int:
    """
    Affiche un filtre de période réutilisable.

    Args:
        key_prefix: Préfixe pour les clés Streamlit

    Returns:
        Nombre de jours (0 = tous, sinon 1, 7, 30, 90)
    """
    options = {
        "Toutes les données": 0,
        "Dernières 24h": 1,
        "7 derniers jours": 7,
        "30 derniers jours": 30,
        "90 derniers jours": 90
    }

    selected = st.selectbox(
        "📅 Période",
        options=list(options.keys()),
        index=2,  # Par défaut: 30 derniers jours
        key=f"{key_prefix}_date_filter"
    )

    return options[selected]


def apply_classification_filters(query, filters: dict, model_class):
    """
    Applique les filtres de classification à une requête SQLAlchemy.

    Args:
        query: Requête SQLAlchemy
        filters: Dict retourné par render_classification_filters
        model_class: Classe du modèle (PageRecherche)

    Returns:
        Requête filtrée
    """
    if filters.get("thematique"):
        query = query.filter(model_class.thematique == filters["thematique"])

    if filters.get("subcategory"):
        query = query.filter(model_class.subcategory == filters["subcategory"])

    if filters.get("pays"):
        # Le champ pays est multi-valeurs "FR,DE,ES"
        query = query.filter(model_class.pays.ilike(f"%{filters['pays']}%"))

    return query


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH PROGRESS TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

class SearchProgressTracker:
    """
    Gestionnaire de progression pour les recherches avec timers détaillés.
    Affiche le temps écoulé par phase et sous-étape avec interface visuelle.
    Enregistre également l'historique complet en base de données.
    """

    def __init__(self, container, db=None, log_id: int = None, api_tracker=None):
        """
        Args:
            container: Streamlit container pour l'affichage
            db: DatabaseManager pour le logging (optionnel)
            log_id: ID du log de recherche créé
            api_tracker: APITracker pour le suivi des appels API (optionnel)
        """
        self.container = container
        self.db = db
        self.log_id = log_id
        self.api_tracker = api_tracker
        self.start_time = time.time()
        self.phase_start = None
        self.step_start = None
        self.phases_completed = []
        self.current_phase = 0
        self.current_phase_name = ""
        self.total_phases = 9

        # Métriques globales pour le log
        self.metrics = {
            "total_ads_found": 0,
            "total_pages_found": 0,
            "pages_after_filter": 0,
            "pages_shopify": 0,
            "pages_other_cms": 0,
            "winning_ads_count": 0,
            "blacklisted_ads_skipped": 0,
            "pages_saved": 0,
            "ads_saved": 0
        }

        # Stats détaillées par phase (pour affichage en temps réel)
        self.phase_stats = {
            1: {"name": "🔍 Recherche Meta API", "stats": {}},
            2: {"name": "📋 Regroupement", "stats": {}},
            3: {"name": "🌐 Sites web", "stats": {}},
            4: {"name": "🔍 Détection CMS", "stats": {}},
            5: {"name": "📊 Comptage ads", "stats": {}},
            6: {"name": "🔬 Analyse web", "stats": {}},
            7: {"name": "🏆 Winning Ads", "stats": {}},
            8: {"name": "💾 Sauvegarde", "stats": {}},
            9: {"name": "🏷️ Classification", "stats": {}},
        }

        # Log détaillé des étapes
        self.detail_logs = []

        # Placeholders pour mise à jour dynamique
        with self.container:
            # Layout: Progress à gauche, Stats à droite
            self.col_progress, self.col_stats = st.columns([3, 2])

            with self.col_progress:
                self.status_box = st.empty()
                self.progress_bar = st.progress(0)
                self.detail_log_box = st.empty()

            with self.col_stats:
                self.stats_panel = st.empty()

            self.summary_box = st.empty()

    def format_time(self, seconds: float) -> str:
        """Formate le temps en format lisible"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        else:
            mins = int(seconds // 60)
            secs = seconds % 60
            return f"{mins}m {secs:.0f}s"

    def _render_status_box(self, step_info: str = "", extra_info: str = "", eta_str: str = ""):
        """Affiche la boîte de statut avec toutes les infos"""
        total_elapsed = time.time() - self.start_time
        phase_elapsed = time.time() - self.phase_start if self.phase_start else 0

        # Construire le contenu
        with self.status_box.container():
            # Header avec temps total
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### ⏱️ Phase {self.current_phase}/{self.total_phases}: {self.current_phase_name}")
            with col2:
                st.markdown(f"**⏱ {self.format_time(total_elapsed)}**")

            # Métriques en ligne
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Phase", f"{self.current_phase}/{self.total_phases}")
            with m2:
                st.metric("Temps total", self.format_time(total_elapsed))
            with m3:
                st.metric("Temps phase", self.format_time(phase_elapsed))
            with m4:
                if eta_str:
                    st.metric("ETA", eta_str)
                else:
                    st.metric("ETA", "-")

            # Info sur l'étape courante
            if step_info:
                st.info(f"🔄 {step_info}")

            # Détail de l'élément en cours
            if extra_info:
                st.caption(f"📍 {extra_info}")

    def start_phase(self, phase_num: int, phase_name: str, total_phases: int = 8):
        """Démarre une nouvelle phase"""
        self.phase_start = time.time()
        self.current_phase = phase_num
        self.current_phase_name = phase_name
        self.total_phases = total_phases

        self._render_status_box()
        self.progress_bar.progress(0)

    def update_step(self, step_name: str, current: int, total: int, extra_info: str = None):
        """Met à jour la sous-étape courante"""
        self.step_start = time.time() if current == 1 else self.step_start

        # Calcul du temps estimé restant
        eta_str = ""
        if current > 0 and self.phase_start:
            elapsed_phase = time.time() - self.phase_start
            avg_per_item = elapsed_phase / current
            remaining_items = total - current
            eta = avg_per_item * remaining_items
            if eta > 1:
                eta_str = self.format_time(eta)

        # Progress bar
        progress = current / total if total > 0 else 0
        self.progress_bar.progress(progress)

        # Statut
        step_info = f"{step_name}: {current}/{total} ({int(progress * 100)}%)"
        self._render_status_box(step_info, extra_info or "", eta_str)

    def update_phase_stats(self, stats: dict):
        """Met à jour les stats de la phase courante"""
        if self.current_phase in self.phase_stats:
            self.phase_stats[self.current_phase]["stats"] = stats
            self._render_stats_panel()

    def _render_stats_panel(self):
        """Affiche le panneau de statistiques en temps réel"""
        with self.stats_panel.container():
            st.markdown("### 📊 Résumé en temps réel")

            # Afficher les stats de chaque phase complétée
            for phase_num, phase_info in self.phase_stats.items():
                stats = phase_info.get("stats", {})
                if not stats:
                    continue

                phase_name = phase_info.get("name", f"Phase {phase_num}")

                # Trouver le temps de cette phase
                phase_time = ""
                for p in self.phases_completed:
                    if p.get("num") == phase_num:
                        phase_time = f" ({p.get('time_formatted', '')})"
                        break

                with st.expander(f"{phase_name}{phase_time}", expanded=(phase_num == self.current_phase)):
                    # Afficher les stats sous forme de métriques
                    stat_items = list(stats.items())

                    # Grouper par 2 colonnes
                    for i in range(0, len(stat_items), 2):
                        cols = st.columns(2)
                        for j, col in enumerate(cols):
                            if i + j < len(stat_items):
                                key, value = stat_items[i + j]
                                with col:
                                    # Formater la valeur
                                    if isinstance(value, int) and value >= 1000:
                                        display_val = f"{value:,}".replace(",", " ")
                                    elif isinstance(value, float):
                                        display_val = f"{value:.1f}"
                                    elif isinstance(value, dict):
                                        # Pour les sous-dictionnaires (ex: CMS breakdown)
                                        display_val = ", ".join(f"{k}: {v}" for k, v in value.items())
                                    elif isinstance(value, list):
                                        display_val = ", ".join(str(v) for v in value[:5])
                                        if len(value) > 5:
                                            display_val += f" (+{len(value)-5})"
                                    else:
                                        display_val = str(value)

                                    st.metric(key, display_val)

    def complete_phase(self, result_summary: str, details: dict = None, stats: dict = None):
        """Marque une phase comme terminée avec ses statistiques"""
        phase_elapsed = time.time() - self.phase_start

        # Mettre à jour les stats de la phase
        if stats:
            self.phase_stats[self.current_phase]["stats"] = stats

        phase_data = {
            "num": self.current_phase,
            "name": self.current_phase_name,
            "time": phase_elapsed,
            "time_formatted": self.format_time(phase_elapsed),
            "result": result_summary,
            "details": details or {},
            "stats": stats or {}
        }
        self.phases_completed.append(phase_data)

        self.progress_bar.progress(1.0)

        # Afficher phase terminée
        with self.status_box.container():
            st.success(f"✅ **Phase {self.current_phase}:** {self.current_phase_name} — {result_summary} ({self.format_time(phase_elapsed)})")

        # Mettre à jour le panneau de stats
        self._render_stats_panel()

        # Sauvegarder en base de données
        self._save_phases_to_db()

    def update_metric(self, key: str, value: int):
        """Met à jour une métrique globale"""
        if key in self.metrics:
            self.metrics[key] = value

    def add_to_metric(self, key: str, value: int):
        """Ajoute à une métrique globale"""
        if key in self.metrics:
            self.metrics[key] += value

    def log_detail(self, icon: str, message: str, count: int = None, total_so_far: int = None, replace: bool = False):
        """
        Ajoute une entrée au log détaillé en temps réel.

        Args:
            icon: Emoji pour l'entrée
            message: Message descriptif
            count: Nombre d'items pour cette étape (optionnel)
            total_so_far: Total cumulé jusqu'à présent (optionnel)
            replace: Si True, remplace la dernière entrée au lieu d'en ajouter une nouvelle
        """
        timestamp = self.format_time(time.time() - self.start_time)
        log_entry = {
            "time": timestamp,
            "icon": icon,
            "message": message,
            "count": count,
            "total": total_so_far
        }

        if replace and self.detail_logs:
            self.detail_logs[-1] = log_entry
        else:
            self.detail_logs.append(log_entry)

        self._render_detail_logs()

    def _render_detail_logs(self):
        """Affiche le log détaillé avec les dernières entrées"""
        with self.detail_log_box.container():
            # Afficher les 5 dernières entrées
            recent_logs = self.detail_logs[-5:]

            if recent_logs:
                st.markdown("##### 📋 Progression")
                log_text = ""
                for log in recent_logs:
                    line = f"`{log['time']}` {log['icon']} {log['message']}"
                    if log.get('count') is not None:
                        line += f" → **{log['count']}**"
                    if log.get('total') is not None:
                        line += f" (total: {log['total']})"
                    log_text += line + "  \n"  # Deux espaces + \n pour retour à la ligne en markdown

                st.markdown(log_text)

    def clear_detail_logs(self):
        """Efface le log détaillé (entre les phases)"""
        self.detail_logs = []
        self.detail_log_box.empty()

    def _save_phases_to_db(self):
        """Sauvegarde les phases en base de données"""
        if self.db and self.log_id:
            try:
                from src.infrastructure.persistence.database import update_search_log_phases
                update_search_log_phases(self.db, self.log_id, self.phases_completed)
            except Exception:
                pass  # Ne pas bloquer si erreur de sauvegarde

    def finalize_log(self, status: str = "completed", error_message: str = None):
        """Finalise le log de recherche en base de données avec métriques API"""
        # Récupérer les métriques API
        api_metrics = None
        if self.api_tracker:
            try:
                api_metrics = self.api_tracker.get_api_metrics_for_log()
                # Sauvegarder les appels API détaillés
                self.api_tracker.save_calls_to_db()
            except Exception:
                pass

        # Finaliser le log
        if self.db and self.log_id:
            try:
                from src.infrastructure.persistence.database import complete_search_log
                complete_search_log(
                    self.db,
                    self.log_id,
                    status=status,
                    error_message=error_message,
                    metrics=self.metrics,
                    api_metrics=api_metrics
                )
            except Exception:
                pass  # Ne pas bloquer si erreur

        # Nettoyer le tracker global
        try:
            from src.infrastructure.api_tracker import clear_current_tracker
            clear_current_tracker()
        except Exception:
            pass

    def show_summary(self):
        """Affiche le résumé final avec tous les temps et stats API"""
        total_time = time.time() - self.start_time

        # Clear status box
        self.status_box.empty()

        # Afficher le résumé
        with self.summary_box.container():
            st.markdown(f"### ✅ Recherche terminée en {self.format_time(total_time)}")

            # Tableau récapitulatif des phases
            summary_data = []
            for p in self.phases_completed:
                summary_data.append({
                    "Phase": f"{p['num']}. {p['name']}",
                    "Durée": self.format_time(p['time']),
                    "Résultat": p['result']
                })

            if summary_data:
                df = pd.DataFrame(summary_data)
                st.dataframe(df, hide_index=True, width="stretch")

            # Stats API si disponibles
            if self.api_tracker:
                try:
                    api_summary = self.api_tracker.get_summary()
                    st.markdown("#### 📊 Statistiques API")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Meta API", api_summary.get("meta_api_calls", 0))
                    with col2:
                        st.metric("ScraperAPI", api_summary.get("scraper_api_calls", 0))
                    with col3:
                        st.metric("Web Requests", api_summary.get("web_requests", 0))
                    with col4:
                        errors = (api_summary.get("meta_api_errors", 0) +
                                 api_summary.get("scraper_api_errors", 0) +
                                 api_summary.get("web_errors", 0))
                        st.metric("Erreurs", errors, delta=None if errors == 0 else f"-{errors}")

                    # Coût estimé si ScraperAPI utilisé
                    if api_summary.get("scraper_api_calls", 0) > 0:
                        cost = api_summary.get("scraper_api_cost", 0)
                        st.caption(f"💰 Coût ScraperAPI estimé: ${cost:.4f}")

                    # Rate limit hits
                    if api_summary.get("rate_limit_hits", 0) > 0:
                        st.warning(f"⚠️ {api_summary['rate_limit_hits']} rate limit(s) atteint(s)")

                except Exception:
                    pass

        return total_time


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal"""
    st.set_page_config(
        page_title="Meta Ads Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_session_state()

    # Verifier l'authentification
    if not require_auth():
        apply_custom_css()
        if render_login_page():
            st.rerun()
        st.stop()

    # Initialiser le worker de recherches en arrière-plan
    try:
        from src.infrastructure.background_worker import init_worker
        from src.infrastructure.persistence.database import recover_interrupted_searches, DatabaseManager, ensure_tables_exist

        # Initialiser les tables si nécessaire
        db = get_database()
        if db:
            ensure_tables_exist(db)
            # Récupérer les recherches interrompues au démarrage
            interrupted = recover_interrupted_searches(db)
            if interrupted > 0:
                st.toast(f"⚠️ {interrupted} recherche(s) interrompue(s) détectée(s)", icon="⚠️")

        # Démarrer le worker (singleton, ne démarre qu'une fois)
        init_worker(max_workers=2)
    except Exception as e:
        # Ne pas bloquer l'app si le worker échoue
        print(f"[Worker] Erreur initialisation: {e}")

    apply_dark_mode()  # Appliquer le thème sombre si activé
    apply_custom_css()  # Appliquer les styles personnalisés
    render_sidebar()

    # Bouton de deconnexion dans la sidebar
    if render_logout_button():
        st.rerun()

    # Router avec verification des permissions
    page = st.session_state.current_page

    # Verifier l'acces a la page
    if not can_access_page(page):
        st.error(f"Vous n'avez pas acces a cette page: {page}")
        user = get_current_user()
        if user:
            st.info(f"Votre role: {user.get('role', 'viewer').capitalize()}")
        st.stop()

    if page == "Dashboard":
        render_dashboard()
    elif page == "Search Ads":
        render_search_ads()
    elif page == "Pages / Shops":
        render_pages_shops()
    elif page == "Watchlists":
        render_watchlists()
    elif page == "Alerts":
        render_alerts()
    elif page == "Monitoring":
        render_monitoring()
    elif page == "Analytics":
        render_analytics()
    elif page == "Winning Ads":
        render_winning_ads()
    elif page == "Blacklist":
        render_blacklist()
    elif page == "Settings":
        render_settings()
    elif page == "Users":
        render_user_management()
    # Nouvelles pages
    elif page == "Favoris":
        render_favorites()
    elif page == "Collections":
        render_collections()
    elif page == "Tags":
        render_tags()
    elif page == "Creative Analysis":
        render_creative_analysis()
    elif page == "Scheduled Scans":
        render_scheduled_scans()
    elif page == "Historique":
        render_search_logs()
    elif page == "Background Searches":
        render_background_searches()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
