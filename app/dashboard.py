"""
Dashboard Streamlit pour Meta Ads Analyzer
Design moderne avec navigation latérale
"""
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import io
import os
import sys
import time
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import (
    AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES,
    MIN_ADS_INITIAL, MIN_ADS_FOR_EXPORT,
    DEFAULT_COUNTRIES, DEFAULT_LANGUAGES,
    DATABASE_URL, MIN_ADS_SUIVI, MIN_ADS_LISTE,
    DEFAULT_STATE_THRESHOLDS, WINNING_AD_CRITERIA,
    META_DELAY_BETWEEN_KEYWORDS, META_DELAY_BETWEEN_BATCHES,
    WEB_DELAY_CMS_CHECK, WORKERS_WEB_ANALYSIS
)
from app.meta_api import MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
from app.shopify_detector import detect_cms_from_url
from app.web_analyzer import analyze_website_complete
from app.utils import load_blacklist, is_blacklisted
from app.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, get_suivi_stats_filtered, search_pages, get_suivi_history,
    get_evolution_stats, get_page_evolution_history, get_etat_from_ads_count,
    add_to_blacklist, remove_from_blacklist, get_blacklist, get_blacklist_ids,
    is_winning_ad, save_winning_ads, get_winning_ads, get_winning_ads_stats,
    get_winning_ads_filtered, get_winning_ads_stats_filtered,
    get_all_pages, get_winning_ads_by_page, get_cached_pages_info, get_dashboard_trends,
    # Tags
    get_all_tags, create_tag, delete_tag, add_tag_to_page, remove_tag_from_page,
    get_page_tags, get_pages_by_tag,
    # Notes
    get_page_notes, add_page_note, update_page_note, delete_page_note,
    # Favorites
    get_favorites, is_favorite, add_favorite, remove_favorite, toggle_favorite,
    # Collections
    get_collections, create_collection, update_collection, delete_collection,
    add_page_to_collection, remove_page_from_collection, get_collection_pages, get_page_collections,
    # Saved Filters
    get_saved_filters, save_filter, delete_saved_filter,
    # Scheduled Scans
    get_scheduled_scans, create_scheduled_scan, update_scheduled_scan,
    delete_scheduled_scan, mark_scan_executed,
    # Settings
    get_setting, set_setting, get_all_settings,
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
        except Exception as e:
            return None
    return st.session_state.db


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
# UI HELPERS - Badges, Colors, Styles
# ═══════════════════════════════════════════════════════════════════════════════

# Couleurs pour les états
STATE_COLORS = {
    "XXL": {"bg": "#7c3aed", "text": "#fff"},  # Violet - Top performer
    "XL": {"bg": "#2563eb", "text": "#fff"},   # Bleu - Excellent
    "L": {"bg": "#0891b2", "text": "#fff"},    # Cyan - Très bien
    "M": {"bg": "#059669", "text": "#fff"},    # Vert - Bien
    "S": {"bg": "#d97706", "text": "#fff"},    # Orange - Moyen
    "XS": {"bg": "#dc2626", "text": "#fff"},   # Rouge - Faible
    "inactif": {"bg": "#6b7280", "text": "#fff"},  # Gris - Inactif
}

# Couleurs pour les CMS
CMS_COLORS = {
    "Shopify": {"bg": "#96bf48", "text": "#fff"},
    "WooCommerce": {"bg": "#7f54b3", "text": "#fff"},
    "PrestaShop": {"bg": "#df0067", "text": "#fff"},
    "Magento": {"bg": "#f46f25", "text": "#fff"},
    "Wix": {"bg": "#0c6efc", "text": "#fff"},
    "Squarespace": {"bg": "#000", "text": "#fff"},
    "BigCommerce": {"bg": "#121118", "text": "#fff"},
    "Webflow": {"bg": "#4353ff", "text": "#fff"},
    "Unknown": {"bg": "#9ca3af", "text": "#fff"},
}


def get_state_badge(etat: str) -> str:
    """Retourne un badge HTML coloré pour l'état"""
    colors = STATE_COLORS.get(etat, {"bg": "#6b7280", "text": "#fff"})
    return f'<span style="background-color:{colors["bg"]};color:{colors["text"]};padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">{etat}</span>'


def get_cms_badge(cms: str) -> str:
    """Retourne un badge HTML coloré pour le CMS"""
    colors = CMS_COLORS.get(cms, {"bg": "#9ca3af", "text": "#fff"})
    return f'<span style="background-color:{colors["bg"]};color:{colors["text"]};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;">{cms}</span>'


def format_state_for_df(etat: str) -> str:
    """Formate l'état avec un emoji indicateur pour les DataFrames"""
    indicators = {
        "XXL": "🟣 XXL",
        "XL": "🔵 XL",
        "L": "🔷 L",
        "M": "🟢 M",
        "S": "🟠 S",
        "XS": "🔴 XS",
        "inactif": "⚫ inactif"
    }
    return indicators.get(etat, etat)


def apply_custom_css():
    """Applique les styles CSS personnalisés"""
    st.markdown("""
    <style>
        /* Badges dans les tableaux */
        .state-badge {
            padding: 2px 10px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 12px;
            display: inline-block;
        }

        /* Amélioration des cartes métriques */
        div[data-testid="stMetricValue"] {
            font-size: 1.8rem;
        }

        /* Hover effect sur les expandeurs */
        .streamlit-expanderHeader:hover {
            background-color: rgba(151, 166, 195, 0.1);
        }

        /* Style pour les boutons d'action rapide */
        .quick-action-btn {
            padding: 5px 15px;
            border-radius: 20px;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }

        /* Amélioration de la sidebar */
        section[data-testid="stSidebar"] > div {
            padding-top: 1rem;
        }

        /* Progress bar améliorée */
        .stProgress > div > div {
            background-color: #10b981;
        }

        /* Tooltips personnalisés */
        .tooltip {
            position: relative;
            display: inline-block;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            background-color: #1f2937;
            color: #fff;
            text-align: center;
            padding: 8px 12px;
            border-radius: 6px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
            white-space: nowrap;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
    </style>
    """, unsafe_allow_html=True)


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
                from app.database import update_search_log_phases
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
                from app.database import complete_search_log
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
            from app.api_tracker import clear_current_tracker
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

def calculate_page_score(page_data: dict, winning_count: int = 0) -> int:
    """
    Calcule un score de performance pour une page (0-100)
    Basé sur: nombre d'ads, état, winning ads, produits
    """
    score = 0

    # Score basé sur le nombre d'ads (max 40 points)
    ads_count = page_data.get("nombre_ads_active", 0) or page_data.get("ads_active_total", 0)
    if ads_count >= 150:
        score += 40
    elif ads_count >= 80:
        score += 35
    elif ads_count >= 35:
        score += 25
    elif ads_count >= 20:
        score += 15
    elif ads_count >= 10:
        score += 10
    elif ads_count >= 1:
        score += 5

    # Score basé sur les winning ads (max 30 points)
    if winning_count >= 10:
        score += 30
    elif winning_count >= 5:
        score += 25
    elif winning_count >= 3:
        score += 20
    elif winning_count >= 1:
        score += 15

    # Score basé sur le nombre de produits (max 20 points)
    products = page_data.get("nombre_produits", 0) or 0
    if products >= 100:
        score += 20
    elif products >= 50:
        score += 15
    elif products >= 20:
        score += 10
    elif products >= 5:
        score += 5

    # Bonus CMS Shopify (10 points)
    cms = page_data.get("cms", "")
    if cms == "Shopify":
        score += 10

    return min(score, 100)


def export_to_csv(data: list, columns: list = None) -> str:
    """Convertit une liste de dictionnaires en CSV"""
    if not data:
        return ""

    df = pd.DataFrame(data)
    if columns:
        df = df[[c for c in columns if c in df.columns]]

    return df.to_csv(index=False, sep=";")


def get_score_color(score: int) -> str:
    """Retourne la couleur selon le score"""
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    else:
        return "🔴"


def detect_trends(db: DatabaseManager, days: int = 7) -> dict:
    """
    Détecte les tendances (pages en forte croissance/décroissance)

    Returns:
        Dict avec 'rising' et 'falling' lists
    """
    evolution = get_evolution_stats(db, period_days=days)

    rising = []
    falling = []

    for evo in evolution:
        delta_pct = evo.get("pct_ads", 0)

        if delta_pct >= 50:  # +50% ou plus
            rising.append({
                "page_id": evo["page_id"],
                "nom_site": evo["nom_site"],
                "delta_ads": evo["delta_ads"],
                "pct_ads": delta_pct,
                "ads_actuel": evo["ads_actuel"]
            })
        elif delta_pct <= -30:  # -30% ou moins
            falling.append({
                "page_id": evo["page_id"],
                "nom_site": evo["nom_site"],
                "delta_ads": evo["delta_ads"],
                "pct_ads": delta_pct,
                "ads_actuel": evo["ads_actuel"]
            })

    return {
        "rising": sorted(rising, key=lambda x: x["pct_ads"], reverse=True)[:10],
        "falling": sorted(falling, key=lambda x: x["pct_ads"])[:10]
    }


def generate_alerts(
    db: DatabaseManager,
    thematique: str = None,
    subcategory: str = None,
    pays: str = None
) -> list:
    """
    Génère des alertes basées sur les données

    Args:
        db: DatabaseManager
        thematique: Filtre par catégorie
        subcategory: Filtre par sous-catégorie
        pays: Filtre par pays

    Returns:
        Liste d'alertes avec type, message, data
    """
    alerts = []

    try:
        # Alerte: Nouvelles pages XXL
        xxl_pages = search_pages(
            db, etat="XXL", limit=50,
            thematique=thematique, subcategory=subcategory, pays=pays
        )
        recent_xxl = [p for p in xxl_pages if p.get("dernier_scan") and
                      (datetime.utcnow() - p["dernier_scan"]).days <= 1]
        if recent_xxl:
            alerts.append({
                "type": "success",
                "icon": "🚀",
                "title": f"{len(recent_xxl)} nouvelle(s) page(s) XXL",
                "message": f"Pages détectées avec ≥150 ads actives",
                "data": recent_xxl[:5]
            })

        # Alerte: Tendances à la hausse
        trends = detect_trends(db, days=7)
        # Filter trends if classification filters are active
        if thematique or subcategory or pays:
            # Get page IDs matching the filter
            filtered_pages = search_pages(
                db, limit=1000,
                thematique=thematique, subcategory=subcategory, pays=pays
            )
            filtered_ids = {p["page_id"] for p in filtered_pages}

            trends["rising"] = [t for t in trends.get("rising", []) if t.get("page_id") in filtered_ids]
            trends["falling"] = [t for t in trends.get("falling", []) if t.get("page_id") in filtered_ids]

        if trends["rising"]:
            alerts.append({
                "type": "info",
                "icon": "📈",
                "title": f"{len(trends['rising'])} page(s) en forte croissance",
                "message": "Pages avec +50% d'ads en 7 jours",
                "data": trends["rising"][:5]
            })

        # Alerte: Pages en chute
        if trends["falling"]:
            alerts.append({
                "type": "warning",
                "icon": "📉",
                "title": f"{len(trends['falling'])} page(s) en déclin",
                "message": "Pages avec -30% d'ads ou plus",
                "data": trends["falling"][:5]
            })

        # Alerte: Winning ads récentes (avec filtres si actifs)
        if thematique or subcategory or pays:
            winning_stats = get_winning_ads_stats_filtered(
                db, days=1,
                thematique=thematique, subcategory=subcategory, pays=pays
            )
        else:
            winning_stats = get_winning_ads_stats(db, days=1)

        if winning_stats.get("total", 0) > 0:
            alerts.append({
                "type": "success",
                "icon": "🏆",
                "title": f"{winning_stats['total']} winning ad(s) aujourd'hui",
                "message": f"Reach moyen: {winning_stats.get('avg_reach', 0):,}",
                "data": winning_stats.get("by_page", [])[:5]
            })

        # Alerte: Changements d'état
        from app.database import SuiviPage
        from sqlalchemy import func, desc

        state_changes = []
        state_order = {"inactif": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6}

        with db.get_session() as session:
            # Récupérer les pages avec plusieurs scans récents
            recent_scans = session.query(
                SuiviPage.page_id,
                SuiviPage.nom_site,
                SuiviPage.nombre_ads_active,
                SuiviPage.date_scan
            ).filter(
                SuiviPage.date_scan >= datetime.utcnow() - timedelta(days=7)
            ).order_by(
                SuiviPage.page_id,
                desc(SuiviPage.date_scan)
            ).all()

            # Grouper par page et détecter les changements
            from itertools import groupby
            for page_id, scans in groupby(recent_scans, key=lambda x: x.page_id):
                scans_list = list(scans)
                if len(scans_list) >= 2:
                    latest = scans_list[0]
                    previous = scans_list[1]

                    current_state = get_etat_from_ads_count(latest.nombre_ads_active)
                    prev_state = get_etat_from_ads_count(previous.nombre_ads_active)

                    if current_state != prev_state:
                        current_rank = state_order.get(current_state, 0)
                        prev_rank = state_order.get(prev_state, 0)

                        if current_rank > prev_rank:
                            # Promotion
                            state_changes.append({
                                "page_id": page_id,
                                "page_name": latest.nom_site,
                                "from_state": prev_state,
                                "to_state": current_state,
                                "direction": "up",
                                "ads": latest.nombre_ads_active
                            })
                        else:
                            # Dégradation
                            state_changes.append({
                                "page_id": page_id,
                                "page_name": latest.nom_site,
                                "from_state": prev_state,
                                "to_state": current_state,
                                "direction": "down",
                                "ads": latest.nombre_ads_active
                            })

        # Ajouter les alertes de changement d'état
        promotions = [s for s in state_changes if s["direction"] == "up"]
        degradations = [s for s in state_changes if s["direction"] == "down"]

        if promotions:
            alerts.append({
                "type": "success",
                "icon": "⬆️",
                "title": f"{len(promotions)} page(s) en progression",
                "message": "Pages ayant changé d'état vers le haut",
                "data": [{"page_name": p["page_name"], "pct_ads": 0, "change": f"{p['from_state']} → {p['to_state']}"} for p in promotions[:5]]
            })

        if degradations:
            alerts.append({
                "type": "warning",
                "icon": "⬇️",
                "title": f"{len(degradations)} page(s) en régression",
                "message": "Pages ayant changé d'état vers le bas",
                "data": [{"page_name": p["page_name"], "pct_ads": 0, "change": f"{p['from_state']} → {p['to_state']}"} for p in degradations[:5]]
            })

    except Exception as e:
        pass

    return alerts


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTÈME DE GRAPHIQUES AMÉLIORÉS
# ═══════════════════════════════════════════════════════════════════════════════

# Palette de couleurs cohérente
CHART_COLORS = {
    # États - du meilleur au moins bon
    "XXL": "#10B981",   # Vert émeraude
    "XL": "#34D399",    # Vert clair
    "L": "#60A5FA",     # Bleu
    "M": "#FBBF24",     # Jaune/Orange
    "S": "#F97316",     # Orange
    "XS": "#EF4444",    # Rouge
    "inactif": "#9CA3AF",  # Gris
    # CMS
    "Shopify": "#96BF48",
    "WooCommerce": "#7B5FC7",
    "PrestaShop": "#DF0067",
    "Magento": "#F46F25",
    "Wix": "#0C6EFC",
    "Unknown": "#9CA3AF",
    # Génériques
    "primary": "#3B82F6",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#06B6D4",
    "neutral": "#6B7280",
}

# Style commun pour tous les graphiques
CHART_LAYOUT = {
    "font": {"family": "Inter, sans-serif", "size": 12, "color": "#374151"},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
    "hoverlabel": {
        "bgcolor": "white",
        "font_size": 13,
        "font_family": "Inter, sans-serif"
    }
}


def info_card(title: str, explanation: str, icon: str = "💡"):
    """Affiche une carte d'explication pour les débutants"""
    with st.expander(f"{icon} {title}", expanded=False):
        st.markdown(f"<p style='color: #6B7280; font-size: 14px;'>{explanation}</p>", unsafe_allow_html=True)


def chart_header(title: str, subtitle: str = None, help_text: str = None):
    """Affiche un header de graphique avec titre, sous-titre et aide optionnelle"""
    if help_text:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"**{title}**")
            if subtitle:
                st.caption(subtitle)
        with col2:
            st.markdown(f"<span title='{help_text}' style='cursor: help; font-size: 18px;'>ℹ️</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"**{title}**")
        if subtitle:
            st.caption(subtitle)


def create_horizontal_bar_chart(
    labels: list,
    values: list,
    title: str = "",
    colors: list = None,
    show_values: bool = True,
    value_suffix: str = "",
    height: int = 300
) -> go.Figure:
    """
    Crée un graphique à barres horizontales clair et lisible.
    Idéal pour comparer des catégories.
    """
    if colors is None:
        colors = [CHART_COLORS.get(label, CHART_COLORS["primary"]) for label in labels]

    # Inverser pour afficher le plus grand en haut
    labels_rev = list(reversed(labels))
    values_rev = list(reversed(values))
    colors_rev = list(reversed(colors))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=labels_rev,
        x=values_rev,
        orientation='h',
        marker_color=colors_rev,
        text=[f"{v:,}{value_suffix}" for v in values_rev] if show_values else None,
        textposition='outside',
        textfont={"size": 12, "color": "#374151"},
        hovertemplate="<b>%{y}</b><br>%{x:,}" + value_suffix + "<extra></extra>"
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title={"text": title, "x": 0, "font": {"size": 14, "color": "#1F2937"}},
        height=height,
        showlegend=False,
        xaxis={"showgrid": True, "gridcolor": "#F3F4F6", "zeroline": False},
        yaxis={"showgrid": False},
        bargap=0.3
    )

    return fig


def create_donut_chart(
    labels: list,
    values: list,
    title: str = "",
    colors: list = None,
    show_percentages: bool = True,
    height: int = 300
) -> go.Figure:
    """
    Crée un graphique en anneau (donut) avec pourcentages clairs.
    Idéal pour montrer des proportions.
    """
    if colors is None:
        colors = [CHART_COLORS.get(label, CHART_COLORS["neutral"]) for label in labels]

    total = sum(values)
    percentages = [(v / total * 100) if total > 0 else 0 for v in values]

    # Créer les labels avec pourcentages
    text_labels = [f"{l}<br><b>{p:.0f}%</b>" for l, p in zip(labels, percentages)]

    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        marker_colors=colors,
        textinfo='label+percent' if show_percentages else 'label',
        textposition='outside',
        textfont={"size": 11},
        hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
        pull=[0.02] * len(labels)  # Légère séparation
    ))

    # Ajouter le total au centre
    fig.add_annotation(
        text=f"<b>{total:,}</b><br><span style='font-size:10px'>Total</span>",
        x=0.5, y=0.5,
        font={"size": 16, "color": "#1F2937"},
        showarrow=False
    )

    fig.update_layout(
        **CHART_LAYOUT,
        title={"text": title, "x": 0, "font": {"size": 14, "color": "#1F2937"}},
        height=height,
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.2, "xanchor": "center", "x": 0.5}
    )

    return fig


def create_trend_chart(
    dates: list,
    values: list,
    title: str = "",
    value_name: str = "Valeur",
    color: str = None,
    show_trend: bool = True,
    height: int = 300,
    secondary_values: list = None,
    secondary_name: str = None
) -> go.Figure:
    """
    Crée un graphique de tendance (ligne) avec zone colorée.
    Idéal pour montrer l'évolution dans le temps.
    """
    if color is None:
        color = CHART_COLORS["primary"]

    fig = go.Figure()

    # Zone sous la courbe
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        fill='tozeroy',
        fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}",
        line={"color": color, "width": 3},
        mode='lines+markers',
        name=value_name,
        marker={"size": 8, "color": color},
        hovertemplate=f"<b>{value_name}</b>: %{{y:,}}<br>%{{x|%d/%m/%Y}}<extra></extra>"
    ))

    # Courbe secondaire optionnelle
    if secondary_values and secondary_name:
        secondary_color = CHART_COLORS["success"]
        fig.add_trace(go.Scatter(
            x=dates,
            y=secondary_values,
            line={"color": secondary_color, "width": 2, "dash": "dot"},
            mode='lines+markers',
            name=secondary_name,
            marker={"size": 6, "color": secondary_color},
            hovertemplate=f"<b>{secondary_name}</b>: %{{y:,}}<br>%{{x|%d/%m/%Y}}<extra></extra>"
        ))

    # Ligne de tendance
    if show_trend and len(values) > 1:
        import numpy as np
        x_numeric = list(range(len(values)))
        z = np.polyfit(x_numeric, values, 1)
        p = np.poly1d(z)
        trend_values = [p(i) for i in x_numeric]

        trend_color = CHART_COLORS["success"] if z[0] > 0 else CHART_COLORS["danger"]
        fig.add_trace(go.Scatter(
            x=dates,
            y=trend_values,
            line={"color": trend_color, "width": 2, "dash": "dash"},
            mode='lines',
            name="Tendance",
            hoverinfo='skip'
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title={"text": title, "x": 0, "font": {"size": 14, "color": "#1F2937"}},
        height=height,
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "xanchor": "center", "x": 0.5},
        xaxis={"showgrid": True, "gridcolor": "#F3F4F6", "tickformat": "%d/%m"},
        yaxis={"showgrid": True, "gridcolor": "#F3F4F6", "zeroline": False},
        hovermode='x unified'
    )

    return fig


def create_gauge_chart(
    value: int,
    max_value: int = 100,
    title: str = "",
    thresholds: list = None,
    height: int = 200
) -> go.Figure:
    """
    Crée une jauge de progression.
    Idéal pour montrer un score ou un pourcentage.
    """
    if thresholds is None:
        thresholds = [
            {"range": [0, 40], "color": CHART_COLORS["danger"]},
            {"range": [40, 60], "color": CHART_COLORS["warning"]},
            {"range": [60, 80], "color": "#FBBF24"},
            {"range": [80, 100], "color": CHART_COLORS["success"]},
        ]

    fig = go.Figure()

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14, "color": "#1F2937"}},
        number={"font": {"size": 32, "color": "#1F2937"}, "suffix": f"/{max_value}"},
        gauge={
            "axis": {"range": [0, max_value], "tickcolor": "#9CA3AF"},
            "bar": {"color": "#3B82F6", "thickness": 0.3},
            "bgcolor": "#F3F4F6",
            "borderwidth": 0,
            "steps": thresholds,
            "threshold": {
                "line": {"color": "#1F2937", "width": 2},
                "thickness": 0.8,
                "value": value
            }
        }
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
    )

    return fig


def create_metric_card(
    value: str,
    label: str,
    delta: str = None,
    delta_color: str = "normal",
    icon: str = ""
):
    """
    Affiche une métrique stylisée avec delta optionnel.
    """
    st.metric(
        label=f"{icon} {label}" if icon else label,
        value=value,
        delta=delta,
        delta_color=delta_color
    )


def create_comparison_bars(
    categories: list,
    series1_values: list,
    series2_values: list,
    series1_name: str = "Actuel",
    series2_name: str = "Précédent",
    title: str = "",
    height: int = 300
) -> go.Figure:
    """
    Crée un graphique de comparaison avec deux séries.
    Idéal pour comparer deux périodes.
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=series1_name,
        x=categories,
        y=series1_values,
        marker_color=CHART_COLORS["primary"],
        text=[f"{v:,}" for v in series1_values],
        textposition='outside',
        textfont={"size": 10}
    ))

    fig.add_trace(go.Bar(
        name=series2_name,
        x=categories,
        y=series2_values,
        marker_color=CHART_COLORS["neutral"],
        text=[f"{v:,}" for v in series2_values],
        textposition='outside',
        textfont={"size": 10}
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title={"text": title, "x": 0, "font": {"size": 14, "color": "#1F2937"}},
        height=height,
        barmode='group',
        bargap=0.3,
        bargroupgap=0.1,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "xanchor": "center", "x": 0.5},
        xaxis={"showgrid": False},
        yaxis={"showgrid": True, "gridcolor": "#F3F4F6"}
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    """Affiche la sidebar avec navigation"""
    with st.sidebar:
        # Header avec dark mode toggle
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("## 📊 Meta Ads")
        with col2:
            dark_mode = st.toggle("🌙", value=st.session_state.get('dark_mode', False), key="dark_toggle")
            if dark_mode != st.session_state.get('dark_mode', False):
                st.session_state.dark_mode = dark_mode
                st.rerun()

        st.markdown("---")

        # ═══ RECHERCHE RAPIDE GLOBALE ═══
        global_search = st.text_input("🔍", placeholder="Recherche rapide...", key="global_search", label_visibility="collapsed")

        if global_search and len(global_search) >= 2:
            db = get_database()
            if db:
                # Rechercher dans les pages
                results = search_pages(db, search_term=global_search, limit=10)
                if results:
                    st.markdown(f"**{len(results)} page(s) trouvée(s)**")
                    for page in results[:5]:
                        page_name = page.get("page_name", "")[:25]
                        if st.button(f"📄 {page_name}", key=f"quick_{page.get('page_id')}", use_container_width=True):
                            st.session_state.selected_page_id = page.get("page_id")
                            st.session_state.current_page = "Pages / Shops"
                            st.rerun()
                else:
                    st.caption("Aucun résultat")

        st.markdown("---")

        # Main Navigation
        st.markdown("### Main")

        if st.button("🏠 Dashboard", width="stretch",
                     type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
            st.session_state.current_page = "Dashboard"
            st.rerun()

        if st.button("🔍 Search Ads", width="stretch",
                     type="primary" if st.session_state.current_page == "Search Ads" else "secondary"):
            st.session_state.current_page = "Search Ads"
            st.rerun()

        if st.button("📜 Historique", width="stretch",
                     type="primary" if st.session_state.current_page == "Historique" else "secondary"):
            st.session_state.current_page = "Historique"
            st.rerun()

        # Indicateur de recherches en arrière-plan
        try:
            from app.background_worker import get_worker
            worker = get_worker()
            active = worker.get_active_searches()
            count = len(active) if active else 0
            btn_label = f"⏳ Recherches en cours ({count})"
            btn_type = "primary" if st.session_state.current_page == "Background Searches" else "secondary"

            if st.button(btn_label, width="stretch", type=btn_type):
                st.session_state.current_page = "Background Searches"
                st.rerun()
        except Exception:
            pass  # Worker non initialisé

        if st.button("🏪 Pages / Shops", width="stretch",
                     type="primary" if st.session_state.current_page == "Pages / Shops" else "secondary"):
            st.session_state.current_page = "Pages / Shops"
            st.rerun()

        if st.button("📋 Watchlists", width="stretch",
                     type="primary" if st.session_state.current_page == "Watchlists" else "secondary"):
            st.session_state.current_page = "Watchlists"
            st.rerun()

        if st.button("🔔 Alerts", width="stretch",
                     type="primary" if st.session_state.current_page == "Alerts" else "secondary"):
            st.session_state.current_page = "Alerts"
            st.rerun()

        st.markdown("---")
        st.markdown("### Organisation")

        if st.button("⭐ Favoris", width="stretch",
                     type="primary" if st.session_state.current_page == "Favoris" else "secondary"):
            st.session_state.current_page = "Favoris"
            st.rerun()

        if st.button("📁 Collections", width="stretch",
                     type="primary" if st.session_state.current_page == "Collections" else "secondary"):
            st.session_state.current_page = "Collections"
            st.rerun()

        if st.button("🏷️ Tags", width="stretch",
                     type="primary" if st.session_state.current_page == "Tags" else "secondary"):
            st.session_state.current_page = "Tags"
            st.rerun()

        st.markdown("---")
        st.markdown("### Analyse")

        if st.button("📈 Monitoring", width="stretch",
                     type="primary" if st.session_state.current_page == "Monitoring" else "secondary"):
            st.session_state.current_page = "Monitoring"
            st.rerun()

        if st.button("📊 Analytics", width="stretch",
                     type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
            st.session_state.current_page = "Analytics"
            st.rerun()

        if st.button("🏆 Winning Ads", width="stretch",
                     type="primary" if st.session_state.current_page == "Winning Ads" else "secondary"):
            st.session_state.current_page = "Winning Ads"
            st.rerun()

        if st.button("🎨 Creative Analysis", width="stretch",
                     type="primary" if st.session_state.current_page == "Creative Analysis" else "secondary"):
            st.session_state.current_page = "Creative Analysis"
            st.rerun()

        st.markdown("---")
        st.markdown("### Automation")

        if st.button("🕐 Scans Programmés", width="stretch",
                     type="primary" if st.session_state.current_page == "Scheduled Scans" else "secondary"):
            st.session_state.current_page = "Scheduled Scans"
            st.rerun()

        st.markdown("---")
        st.markdown("### Config")

        if st.button("🚫 Blacklist", width="stretch",
                     type="primary" if st.session_state.current_page == "Blacklist" else "secondary"):
            st.session_state.current_page = "Blacklist"
            st.rerun()

        if st.button("⚙️ Settings", width="stretch",
                     type="primary" if st.session_state.current_page == "Settings" else "secondary"):
            st.session_state.current_page = "Settings"
            st.rerun()

        # Database status
        st.markdown("---")
        db = get_database()
        if db:
            st.success("🟢 DB OK")
        else:
            st.error("🔴 DB offline")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def render_dashboard():
    """Page Dashboard - Vue d'ensemble"""
    st.title("🏠 Dashboard")
    st.markdown("Vue d'ensemble de vos données")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Filtres de classification
    st.markdown("#### 🔍 Filtres")
    filters = render_classification_filters(db, key_prefix="dashboard", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"🏷️ {filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"📂 {filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"🌍 {filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' • '.join(active_filters)}")

    st.markdown("---")

    try:
        # Utiliser les stats filtrées si des filtres sont actifs
        if any(filters.values()):
            stats = get_suivi_stats_filtered(
                db,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays")
            )
        else:
            stats = get_suivi_stats(db)

        winning_stats = get_winning_ads_stats(db, days=7)
        winning_by_page = get_winning_ads_by_page(db, days=30)

        # Récupérer les tendances (7 jours vs 7 jours précédents)
        trends = get_dashboard_trends(db, days=7)

        # KPIs principaux avec trends
        col1, col2, col3, col4, col5 = st.columns(5)

        total_pages = stats.get("total_pages", 0)
        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})

        actives = sum(v for k, v in etats.items() if k != "inactif")
        shopify_count = cms_stats.get("Shopify", 0)
        xxl_count = etats.get("XXL", 0)
        winning_total = winning_stats.get("total", 0)

        # Formater les deltas pour affichage
        pages_delta = trends.get("pages", {}).get("delta", 0)
        winning_delta = trends.get("winning_ads", {}).get("delta", 0)
        rising = trends.get("evolution", {}).get("rising", 0)
        falling = trends.get("evolution", {}).get("falling", 0)

        col1.metric(
            "📄 Total Pages",
            total_pages,
            delta=f"+{pages_delta} (7j)" if pages_delta > 0 else f"{pages_delta} (7j)" if pages_delta < 0 else None,
            delta_color="normal"
        )
        col2.metric(
            "✅ Actives",
            actives,
            delta=f"📈 {rising} montantes" if rising > 0 else None,
            delta_color="normal"
        )
        col3.metric("🚀 XXL (≥150)", xxl_count)
        col4.metric("🛒 Shopify", shopify_count)
        col5.metric(
            "🏆 Winning (7j)",
            winning_total,
            delta=f"+{winning_delta} vs sem. préc." if winning_delta > 0 else f"{winning_delta} vs sem. préc." if winning_delta < 0 else None,
            delta_color="normal" if winning_delta >= 0 else "inverse"
        )

        # Encart Tendances (7 jours)
        if rising > 0 or falling > 0 or pages_delta != 0 or winning_delta != 0:
            with st.expander("📈 Tendances (7 derniers jours)", expanded=False):
                trend_cols = st.columns(4)
                with trend_cols[0]:
                    st.metric(
                        "Nouvelles pages",
                        trends.get("pages", {}).get("current", 0),
                        delta=f"+{pages_delta}" if pages_delta > 0 else str(pages_delta) if pages_delta < 0 else "stable"
                    )
                with trend_cols[1]:
                    st.metric(
                        "Winning ads",
                        trends.get("winning_ads", {}).get("current", 0),
                        delta=f"+{winning_delta}" if winning_delta > 0 else str(winning_delta) if winning_delta < 0 else "stable"
                    )
                with trend_cols[2]:
                    searches_delta = trends.get("searches", {}).get("delta", 0)
                    st.metric(
                        "Recherches",
                        trends.get("searches", {}).get("current", 0),
                        delta=f"+{searches_delta}" if searches_delta > 0 else str(searches_delta) if searches_delta < 0 else "stable"
                    )
                with trend_cols[3]:
                    net_evolution = rising - falling
                    st.metric(
                        "Balance évolution",
                        f"📈 {rising} / 📉 {falling}",
                        delta=f"+{net_evolution} net" if net_evolution > 0 else f"{net_evolution} net" if net_evolution < 0 else "équilibré",
                        delta_color="normal" if net_evolution >= 0 else "inverse"
                    )

        # Quick Alerts
        alerts = generate_alerts(db)
        if alerts:
            st.markdown("---")
            st.subheader("🔔 Alertes")
            alert_cols = st.columns(min(len(alerts), 4))
            for i, alert in enumerate(alerts[:4]):
                with alert_cols[i]:
                    if alert["type"] == "success":
                        st.success(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")
                    elif alert["type"] == "warning":
                        st.warning(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")
                    else:
                        st.info(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")

        st.markdown("---")

        # Info card pour débutants
        info_card(
            "Comment lire ces graphiques ?",
            """
            <b>États des pages</b> : Classement basé sur le nombre d'annonces actives.<br>
            • <b>XXL</b> (≥150 ads) = Pages très actives, probablement rentables<br>
            • <b>XL</b> (80-149) = Pages performantes<br>
            • <b>L</b> (35-79) = Bonne activité<br>
            • <b>M/S/XS</b> = Activité modérée à faible<br><br>
            <b>CMS</b> : La technologie utilisée par le site (Shopify est le plus courant en e-commerce).
            """,
            "📚"
        )

        # Graphiques améliorés
        col1, col2 = st.columns(2)

        with col1:
            chart_header(
                "📊 Répartition par État",
                "Classement des pages selon leur nombre d'annonces actives",
                "XXL = ≥150 ads, XL = 80-149, L = 35-79, M = 20-34, S = 10-19, XS = 1-9"
            )
            if etats:
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = [(k, etats.get(k, 0)) for k in ordre_etats if etats.get(k, 0) > 0]
                if etats_ordonne:
                    labels = [e[0] for e in etats_ordonne]
                    values = [e[1] for e in etats_ordonne]
                    fig = create_horizontal_bar_chart(
                        labels=labels,
                        values=values,
                        value_suffix=" pages",
                        height=280
                    )
                    st.plotly_chart(fig, key="dash_etats", width="stretch")
            else:
                st.info("Aucune donnée disponible")

        with col2:
            chart_header(
                "🛒 Répartition par CMS",
                "Technologie e-commerce utilisée par les sites",
                "Shopify est la plateforme la plus populaire pour le dropshipping"
            )
            if cms_stats:
                # Trier par valeur décroissante
                sorted_cms = sorted(cms_stats.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_cms]
                values = [c[1] for c in sorted_cms]
                fig = create_donut_chart(
                    labels=labels,
                    values=values,
                    height=280
                )
                st.plotly_chart(fig, key="dash_cms", width="stretch")
            else:
                st.info("Aucune donnée disponible")

        # Top performers avec score
        st.markdown("---")
        st.subheader("🌟 Top Performers (avec Score)")

        top_pages = search_pages(db, limit=15)
        if top_pages:
            # Calculer les scores
            for page in top_pages:
                winning_count = winning_by_page.get(page["page_id"], 0)
                page["score"] = calculate_page_score(page, winning_count)
                page["winning_count"] = winning_count
                page["score_display"] = f"{get_score_color(page['score'])} {page['score']}"

            # Trier par score
            top_pages = sorted(top_pages, key=lambda x: x["score"], reverse=True)[:10]

            # Formater états avec badges
            for p in top_pages:
                p["etat_display"] = format_state_for_df(p.get("etat", ""))

            df = pd.DataFrame(top_pages)
            cols_to_show = ["page_name", "cms", "etat_display", "nombre_ads_active", "winning_count", "score_display"]
            col_names = ["Nom", "CMS", "État", "Ads", "🏆 Winning", "Score"]
            df_display = df[[c for c in cols_to_show if c in df.columns]]
            df_display.columns = col_names[:len(df_display.columns)]
            st.dataframe(df_display, width="stretch", hide_index=True)

            # Export button
            csv_data = export_to_csv(top_pages)
            st.download_button(
                "📥 Exporter en CSV",
                csv_data,
                "top_performers.csv",
                "text/csv",
                key="export_top"
            )
        else:
            st.info("Aucune page en base. Lancez une recherche pour commencer.")

        # Tendances
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📈 En forte croissance (7j)")
            trends = detect_trends(db, days=7)
            if trends["rising"]:
                for t in trends["rising"][:5]:
                    st.write(f"🚀 **{t['nom_site']}** +{t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune tendance détectée")

        with col2:
            st.subheader("📉 En déclin")
            if trends.get("falling"):
                for t in trends["falling"][:5]:
                    st.write(f"⚠️ **{t['nom_site']}** {t['pct_ads']:.0f}% ({t['ads_actuel']} ads)")
            else:
                st.caption("Aucune page en déclin")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SEARCH ADS
# ═══════════════════════════════════════════════════════════════════════════════

def render_search_ads():
    """Page Search Ads - Recherche d'annonces"""
    st.title("🔍 Search Ads")

    # Vérifier si on a des résultats en aperçu à afficher
    if st.session_state.get("show_preview_results", False):
        render_preview_results()
        return

    # Header avec historique
    col_title, col_history = st.columns([2, 1])
    with col_title:
        st.markdown("Rechercher et analyser des annonces Meta")
    with col_history:
        # Sélecteur d'historique
        history = get_search_history()
        if history:
            selected_history = render_search_history_selector("search")
            if selected_history:
                st.session_state['_prefill_search'] = selected_history

    # Sélection du mode de recherche
    search_mode = st.radio(
        "Mode de recherche",
        ["🔤 Par mots-clés", "🆔 Par Page IDs"],
        horizontal=True,
        help="Choisissez entre recherche par mots-clés ou directement par Page IDs"
    )

    if search_mode == "🔤 Par mots-clés":
        render_keyword_search()
    else:
        render_page_id_search()


def render_keyword_search():
    """Recherche par mots-clés"""

    # ═══ CHAMPS ESSENTIELS (toujours visibles) ═══
    st.subheader("🎯 Recherche rapide")

    col1, col2 = st.columns([2, 1])

    with col1:
        keywords_input = st.text_area(
            "Mots-clés (un par ligne)",
            placeholder="dropshipping\necommerce\nboutique en ligne",
            height=100,
            help="Entrez vos mots-clés de recherche, un par ligne"
        )
        keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

    with col2:
        countries = st.multiselect(
            "🌍 Pays",
            options=list(AVAILABLE_COUNTRIES.keys()),
            default=DEFAULT_COUNTRIES,
            format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
            key="countries_keyword"
        )

        # Indicateur rapide
        if keywords:
            st.info(f"🔍 {len(keywords)} mot(s)-clé(s)")

    # ═══ OPTIONS AVANCÉES (dans expander) ═══
    with st.expander("⚙️ Options avancées", expanded=False):
        adv_col1, adv_col2, adv_col3 = st.columns(3)

        with adv_col1:
            languages = st.multiselect(
                "Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=[],  # Vide par défaut
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_keyword"
            )

        with adv_col2:
            min_ads = st.slider("Min. ads pour inclusion", 1, 50, MIN_ADS_INITIAL, key="min_ads_keyword")

        with adv_col3:
            cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
            selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=["Shopify"], key="cms_keyword")

    # Options de mode
    opt_col1, opt_col2 = st.columns(2)

    with opt_col1:
        background_mode = st.checkbox(
            "⏳ Lancer en arrière-plan",
            help="La recherche continue même si vous quittez la page. Résultats disponibles dans 'Background Searches'.",
            key="background_keyword"
        )

    with opt_col2:
        preview_mode = st.checkbox(
            "📋 Mode aperçu",
            help="Voir les résultats avant de les enregistrer en base de données",
            key="preview_keyword",
            disabled=background_mode  # Désactivé si arrière-plan
        )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", width="stretch", key="btn_keyword"):
        if not keywords:
            st.error("Au moins un mot-clé requis !")
            return

        if background_mode:
            # Mode arrière-plan: ajouter à la file d'attente
            from app.background_worker import get_worker
            worker = get_worker()

            search_id = worker.submit_search(
                keywords=keywords,
                cms_filter=selected_cms if selected_cms else ["Shopify"],
                ads_min=min_ads,
                countries=",".join(countries) if countries else "FR",
                languages=",".join(languages) if languages else ""  # Vide si pas de langues
            )

            st.success(f"✅ Tâche #{search_id} ajoutée à la file d'attente!")
            st.info("💡 Vous pouvez quitter cette page, la recherche continuera en arrière-plan. Consultez les résultats dans **Recherches en cours**.")

            # Proposer d'aller voir les recherches en arrière-plan
            if st.button("📋 Voir les recherches en arrière-plan", key="goto_bg"):
                st.session_state.current_page = "Background Searches"
                st.rerun()
        else:
            # Mode direct: exécution synchrone
            run_search_process(keywords, countries, languages, min_ads, selected_cms, preview_mode)


def render_page_id_search():
    """Recherche par Page IDs (optimisée par batch de 10)"""

    # ═══ CHAMPS ESSENTIELS ═══
    st.subheader("🆔 Recherche par Page IDs")

    col1, col2 = st.columns([2, 1])

    with col1:
        page_ids_input = st.text_area(
            "Page IDs (un par ligne)",
            placeholder="123456789\n987654321\n456789123",
            height=120,
            help="Entrez les Page IDs Facebook, un par ligne"
        )
        page_ids = [pid.strip() for pid in page_ids_input.split("\n") if pid.strip()]

    with col2:
        countries = st.multiselect(
            "🌍 Pays",
            options=list(AVAILABLE_COUNTRIES.keys()),
            default=DEFAULT_COUNTRIES,
            format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
            key="countries_pageid"
        )

        # Indicateur rapide
        if page_ids:
            batch_count = (len(page_ids) + 9) // 10
            st.info(f"📊 {len(page_ids)} IDs → {batch_count} requêtes")

    # ═══ OPTIONS AVANCÉES ═══
    with st.expander("⚙️ Options avancées", expanded=False):
        adv_col1, adv_col2 = st.columns(2)

        with adv_col1:
            languages = st.multiselect(
                "Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=[],  # Vide par défaut
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_pageid"
            )

        with adv_col2:
            cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
            selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=["Shopify"], key="cms_pageid")

    # Mode aperçu
    preview_mode = st.checkbox(
        "📋 Mode aperçu",
        help="Voir les résultats avant de les enregistrer",
        key="preview_pageid"
    )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", width="stretch", key="btn_pageid"):
        if not page_ids:
            st.error("Au moins un Page ID requis !")
            return

        run_page_id_search(page_ids, countries, languages, selected_cms, preview_mode)


def render_preview_results():
    """Affiche les résultats en mode aperçu"""
    st.subheader("📋 Aperçu des résultats")
    st.warning("⚠️ Mode aperçu activé - Les données ne sont pas encore enregistrées")

    db = get_database()
    pages_final = st.session_state.get("pages_final", {})
    web_results = st.session_state.get("web_results", {})
    countries = st.session_state.get("countries", ["FR"])

    if not pages_final:
        st.info("Aucun résultat à afficher")
        if st.button("🔙 Nouvelle recherche"):
            st.session_state.show_preview_results = False
            st.rerun()
        return

    st.info(f"📊 {len(pages_final)} pages trouvées")

    # Afficher les pages avec options
    for pid, data in list(pages_final.items()):
        web = web_results.get(pid, {})
        website = data.get('website', '')
        fb_link = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={countries[0]}&view_all_page_id={pid}"
        winning_count = data.get('winning_ads_count', 0)

        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            winning_badge = f" 🏆 {winning_count}" if winning_count > 0 else ""
            st.write(f"**{data.get('page_name', 'N/A')}** - {data.get('ads_active_total', 0)} ads{winning_badge}")
            st.caption(f"CMS: {data.get('cms', 'N/A')} | Produits: {web.get('product_count', 'N/A')}")

        with col2:
            if website:
                st.link_button("🌐 Site", website)
            else:
                st.caption("Pas de site")

        with col3:
            st.link_button("📘 Ads", fb_link)

        with col4:
            if st.button("🚫", key=f"bl_preview_{pid}", help="Blacklister"):
                if db and add_to_blacklist(db, pid, data.get("page_name", ""), "Blacklisté depuis aperçu"):
                    # Retirer de pages_final
                    del st.session_state.pages_final[pid]
                    if pid in st.session_state.web_results:
                        del st.session_state.web_results[pid]
                    st.rerun()

    st.markdown("---")

    # Boutons d'action
    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Sauvegarder en base de données", type="primary", width="stretch"):
            if db:
                try:
                    thresholds = st.session_state.get("state_thresholds", None)
                    languages = st.session_state.get("languages", ["fr"])
                    pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                    det = st.session_state.get("detection_thresholds", {})
                    suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI))
                    ads_saved = save_ads_recherche(db, pages_final, st.session_state.get("page_ads", {}), countries, det.get("min_ads_liste", MIN_ADS_LISTE))
                    winning_ads_data = st.session_state.get("winning_ads_data", [])
                    winning_saved, winning_skipped = save_winning_ads(db, winning_ads_data, pages_final)

                    msg = f"✓ Sauvegardé : {pages_saved} pages, {suivi_saved} suivi, {ads_saved} ads, {winning_saved} winning"
                    if winning_skipped > 0:
                        msg += f" ({winning_skipped} doublons ignorés)"
                    st.success(msg)
                    st.session_state.show_preview_results = False
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur sauvegarde: {e}")

    with col2:
        if st.button("🔙 Nouvelle recherche", width="stretch"):
            st.session_state.show_preview_results = False
            st.session_state.pages_final = {}
            st.session_state.web_results = {}
            st.rerun()


def run_search_process(keywords, countries, languages, min_ads, selected_cms, preview_mode=False):
    """Exécute le processus de recherche complet avec tracking détaillé et logging"""
    from app.api_tracker import APITracker, set_current_tracker, clear_current_tracker
    from app.meta_api import init_token_rotator, clear_token_rotator

    db = get_database()

    # Charger les tokens depuis la base de données (avec IDs pour le logging)
    tokens_with_proxies = []
    if db:
        try:
            from app.database import get_active_meta_tokens_with_proxies, ensure_tables_exist
            ensure_tables_exist(db)
            tokens_with_proxies = get_active_meta_tokens_with_proxies(db)
        except Exception as e:
            st.warning(f"⚠️ Impossible de charger les tokens depuis la DB: {e}")

    # Fallback sur variable d'environnement si pas de tokens en DB
    if not tokens_with_proxies:
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            tokens_with_proxies = [{"id": None, "token": env_token, "proxy": None, "name": "Env Token"}]
            st.info("📝 Utilisation du token depuis META_ACCESS_TOKEN")

    if not tokens_with_proxies:
        st.error("❌ Aucun token Meta API disponible. Configurez vos tokens dans **Settings > Tokens Meta API**.")
        return

    # Sauvegarder dans l'historique
    add_to_search_history('keywords', {
        'keywords': keywords,
        'countries': countries,
        'languages': languages,
        'min_ads': min_ads,
        'cms': selected_cms
    })

    st.info(f"🔄 {len(tokens_with_proxies)} token(s) actif(s)")

    # Initialiser le TokenRotator avec le db pour enregistrer les stats
    rotator = init_token_rotator(tokens_with_proxies=tokens_with_proxies, db=db)

    if rotator.token_count > 1:
        st.success(f"🔄 Rotation automatique activée ({rotator.token_count} tokens)")

    # Utiliser le premier token actif
    client = MetaAdsClient(rotator.get_current_token())

    # Créer le log de recherche en base de données
    log_id = None
    if db:
        try:
            from app.database import create_search_log, ensure_tables_exist
            # S'assurer que toutes les tables existent (notamment SearchLog)
            ensure_tables_exist(db)
            log_id = create_search_log(
                db,
                keywords=keywords,
                countries=countries,
                languages=languages,
                min_ads=min_ads,
                selected_cms=selected_cms if selected_cms else []
            )
        except Exception as e:
            st.warning(f"⚠️ Log non créé: {str(e)[:100]}")

    # Créer l'API tracker pour suivre tous les appels
    api_tracker = APITracker(search_log_id=log_id, db=db)
    set_current_tracker(api_tracker)

    # Créer le tracker de progression avec logging
    progress_container = st.container()
    tracker = SearchProgressTracker(progress_container, db=db, log_id=log_id, api_tracker=api_tracker)

    # Récupérer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db)
        if blacklist_ids:
            st.info(f"🚫 {len(blacklist_ids)} pages en blacklist seront ignorées")

    # ═══ PHASE 1: Recherche par mots-clés ═══
    tracker.start_phase(1, "🔍 Recherche par mots-clés", total_phases=8)
    all_ads = []
    seen_ad_ids = set()

    for i, kw in enumerate(keywords):
        tracker.update_step("Recherche", i + 1, len(keywords), f"Mot-clé: {kw}")

        # Délai entre les mots-clés pour éviter le rate limit
        if i > 0:
            time.sleep(META_DELAY_BETWEEN_KEYWORDS)  # Configurable dans config.py

        try:
            ads = client.search_ads(kw, countries, languages)
            new_ads_count = 0
            for ad in ads:
                ad_id = ad.get("id")
                if ad_id and ad_id not in seen_ad_ids:
                    ad["_keyword"] = kw
                    all_ads.append(ad)
                    seen_ad_ids.add(ad_id)
                    new_ads_count += 1

            # Log détaillé pour ce mot-clé
            tracker.log_detail("🔍", f"'{kw}'", count=new_ads_count, total_so_far=len(all_ads))

        except RuntimeError as e:
            tracker.log_detail("❌", f"'{kw}' - Erreur: {str(e)[:50]}")

    tracker.clear_detail_logs()

    # Stats détaillées Phase 1
    phase1_stats = {
        "Mots-clés recherchés": len(keywords),
        "Annonces trouvées": len(all_ads),
        "Annonces uniques": len(seen_ad_ids),
    }
    tracker.complete_phase(f"{len(all_ads)} annonces trouvées", details={
        "keywords_searched": len(keywords),
        "ads_found": len(all_ads)
    }, stats=phase1_stats)
    tracker.update_metric("total_ads_found", len(all_ads))

    # ═══ PHASE 2: Regroupement par page ═══
    tracker.start_phase(2, "📋 Regroupement par page", total_phases=8)
    pages = {}
    page_ads = defaultdict(list)
    name_counter = defaultdict(Counter)
    blacklisted_ads_count = 0
    blacklisted_pages_found = set()

    for i, ad in enumerate(all_ads):
        if i % 100 == 0:
            tracker.update_step("Regroupement", i + 1, len(all_ads))

        pid = ad.get("page_id")
        if not pid:
            continue

        # Ignorer les pages blacklistées
        if str(pid) in blacklist_ids:
            blacklisted_ads_count += 1
            blacklisted_pages_found.add(str(pid))
            continue

        pname = (ad.get("page_name") or "").strip()

        if pid not in pages:
            pages[pid] = {
                "page_id": pid, "page_name": pname, "website": "",
                "_ad_ids": set(), "_keywords": set(), "ads_found_search": 0,
                "ads_active_total": -1, "currency": "",
                "cms": "Unknown", "is_shopify": False
            }

        # Track which keyword found this page
        if ad.get("_keyword"):
            pages[pid]["_keywords"].add(ad["_keyword"])

        ad_id = ad.get("id")
        if ad_id:
            pages[pid]["_ad_ids"].add(ad_id)
            page_ads[pid].append(ad)
        if pname:
            name_counter[pid][pname] += 1

    for pid, counter in name_counter.items():
        if counter and pid in pages:
            pages[pid]["page_name"] = counter.most_common(1)[0][0]

    for pid, data in pages.items():
        data["ads_found_search"] = len(data["_ad_ids"])

    pages_filtered = {pid: data for pid, data in pages.items() if data["ads_found_search"] >= min_ads}

    # Log détaillé du filtrage
    tracker.log_detail("📊", f"Total pages trouvées", count=len(pages))
    tracker.log_detail("✅", f"Pages avec ≥{min_ads} ads", count=len(pages_filtered))
    if blacklisted_ads_count > 0:
        tracker.log_detail("🚫", f"Ads blacklistées ignorées", count=blacklisted_ads_count)

    tracker.clear_detail_logs()

    # Stats détaillées Phase 2
    phase2_stats = {
        "Pages trouvées": len(pages),
        f"Pages ≥{min_ads} ads": len(pages_filtered),
        "Pages filtrées": len(pages) - len(pages_filtered),
        "Pages blacklistées": len(blacklisted_pages_found),
        "Ads blacklist ignorées": blacklisted_ads_count,
    }

    # Afficher les détails du filtrage
    phase2_details = f"{len(pages_filtered)} pages avec ≥{min_ads} ads"
    if blacklisted_ads_count > 0:
        phase2_details += f" ({blacklisted_ads_count} ads de {len(blacklisted_pages_found)} page(s) blacklistée(s) ignorées)"
    tracker.complete_phase(phase2_details, details={
        "total_pages_before_filter": len(pages),
        "pages_after_filter": len(pages_filtered),
        "blacklisted_ads": blacklisted_ads_count,
        "blacklisted_pages": len(blacklisted_pages_found)
    }, stats=phase2_stats)
    tracker.update_metric("total_pages_found", len(pages))
    tracker.update_metric("pages_after_filter", len(pages_filtered))
    tracker.update_metric("blacklisted_ads_skipped", blacklisted_ads_count)

    if not pages_filtered:
        if blacklisted_ads_count > 0 and len(pages) == 0:
            st.warning(f"⚠️ Toutes les {blacklisted_ads_count} ads trouvées appartiennent à des pages blacklistées")
        elif len(all_ads) == 0:
            st.warning("⚠️ Aucune annonce trouvée pour ces mots-clés. Essayez d'autres termes de recherche.")
        else:
            st.warning(f"⚠️ {len(pages)} pages trouvées mais aucune avec ≥{min_ads} ads (après filtrage blacklist)")
        # Finaliser le log avec statut "no_results"
        tracker.finalize_log(status="no_results")
        return

    # ═══ PHASE 3: Vérification cache + Extraction sites web ═══
    tracker.start_phase(3, "🌐 Extraction sites web (avec cache)", total_phases=8)

    # Récupérer les infos en cache pour toutes les pages
    cached_pages = {}
    if db:
        cached_pages = get_cached_pages_info(db, list(pages_filtered.keys()), cache_days=4)
        cached_count = sum(1 for c in cached_pages.values() if not c.get("needs_rescan"))
        if cached_count > 0:
            st.info(f"💾 {cached_count} pages en cache (scan < 4 jours)")

    # Extraire les URLs pour les pages non cachées ou sans site
    for i, (pid, data) in enumerate(pages_filtered.items()):
        cached = cached_pages.get(str(pid), {})

        # Utiliser le site en cache si disponible
        if cached.get("lien_site") and not cached.get("needs_rescan"):
            data["website"] = cached["lien_site"]
            data["_from_cache"] = True
        else:
            data["website"] = extract_website_from_ads(page_ads.get(pid, []))
            data["_from_cache"] = False

        if i % 10 == 0:
            tracker.update_step("Extraction URL", i + 1, len(pages_filtered))

    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    cached_sites = sum(1 for d in pages_filtered.values() if d.get("_from_cache"))
    sites_new = sites_found - cached_sites

    # Stats détaillées Phase 3
    phase3_stats = {
        "Sites trouvés": sites_found,
        "Sites en cache": cached_sites,
        "Nouveaux sites": sites_new,
        "Sans site web": len(pages_filtered) - sites_found,
    }
    tracker.complete_phase(f"{sites_found} sites ({cached_sites} en cache)", stats=phase3_stats)

    # ═══ PHASE 4: Détection CMS (multithreaded + cache) ═══
    tracker.start_phase(4, "🔍 Détection CMS (parallèle)", total_phases=8)
    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}

    # Séparer les pages avec CMS connu vs à détecter
    pages_need_cms = []
    for pid, data in pages_with_sites.items():
        cached = cached_pages.get(str(pid), {})
        # Utiliser le CMS en cache si valide
        if cached.get("cms") and cached["cms"] not in ("Unknown", "Inconnu", "") and not cached.get("needs_rescan"):
            data["cms"] = cached["cms"]
            data["is_shopify"] = cached["cms"] == "Shopify"
            data["_cms_cached"] = True
        else:
            pages_need_cms.append((pid, data))
            data["_cms_cached"] = False

    cms_cached_count = len(pages_with_sites) - len(pages_need_cms)
    st.info(f"🔍 {len(pages_need_cms)} sites à analyser ({cms_cached_count} CMS en cache)")

    # Fonction pour détection CMS parallèle
    def detect_cms_worker(pid_data):
        pid, data = pid_data
        try:
            cms_result = detect_cms_from_url(data["website"])
            return pid, cms_result
        except Exception as e:
            return pid, {"cms": "Unknown", "is_shopify": False}

    # Multithreading pour la détection CMS (8 workers)
    cms_counts = {}  # Compteur par CMS
    if pages_need_cms:
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(detect_cms_worker, item): item[0] for item in pages_need_cms}

            for future in as_completed(futures):
                pid, cms_result = future.result()
                cms_name = cms_result["cms"]
                pages_with_sites[pid]["cms"] = cms_name
                pages_with_sites[pid]["is_shopify"] = cms_result.get("is_shopify", False)
                completed += 1

                # Compter les CMS
                cms_counts[cms_name] = cms_counts.get(cms_name, 0) + 1

                if completed % 5 == 0:
                    tracker.update_step("Analyse CMS", completed, len(pages_need_cms))
                    # Log les CMS détectés (replace=True pour mise à jour en place)
                    tracker.log_detail("🔍", f"CMS analysés", count=completed, total_so_far=len(pages_need_cms), replace=True)

    # Log des CMS trouvés
    tracker.clear_detail_logs()
    for cms_name, count in sorted(cms_counts.items(), key=lambda x: -x[1])[:5]:
        tracker.log_detail("🏷️", f"{cms_name}", count=count)

    tracker.clear_detail_logs()

    # Compter tous les CMS (y compris ceux en cache)
    all_cms_counts = {}
    for pid, data in pages_with_sites.items():
        cms_name = data.get("cms", "Unknown")
        all_cms_counts[cms_name] = all_cms_counts.get(cms_name, 0) + 1

    # Filter by CMS
    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in cms_options[:-1]:
            return True
        return False

    pages_with_cms = {pid: data for pid, data in pages_with_sites.items() if cms_matches(data.get("cms", "Unknown"))}

    # Stats détaillées Phase 4
    phase4_stats = {
        "Pages analysées": len(pages_with_sites),
        "CMS en cache": cms_cached_count,
        "CMS détectés": len(pages_need_cms),
    }
    # Ajouter les CMS trouvés
    for cms_name in selected_cms:
        if cms_name in all_cms_counts:
            phase4_stats[f"🏷️ {cms_name}"] = all_cms_counts[cms_name]

    phase4_stats["Pages CMS sélectionnés"] = len(pages_with_cms)
    phase4_stats["Pages exclues (autre CMS)"] = len(pages_with_sites) - len(pages_with_cms)

    tracker.complete_phase(f"{len(pages_with_cms)} pages avec CMS sélectionnés", stats=phase4_stats)

    # ═══ PHASE 5: Comptage des annonces ═══
    tracker.start_phase(5, "📊 Comptage des annonces (batch)", total_phases=8)

    # Traiter par batch de 10 pages pour économiser les requêtes API
    page_ids_list = list(pages_with_cms.keys())
    batch_size = 10
    total_batches = (len(page_ids_list) + batch_size - 1) // batch_size

    processed = 0
    for batch_idx in range(0, len(page_ids_list), batch_size):
        batch_pids = page_ids_list[batch_idx:batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        tracker.update_step("Batch API", batch_num, total_batches, f"Batch {batch_num}/{total_batches} ({len(batch_pids)} pages)")

        # Fetch batch
        batch_results = client.fetch_ads_for_pages_batch(batch_pids, countries, languages)

        # Traiter les résultats du batch
        for pid in batch_pids:
            data = pages_with_cms[pid]
            ads_complete, count = batch_results.get(str(pid), ([], 0))

            if count > 0:
                page_ads[pid] = ads_complete
                data["ads_active_total"] = count
                data["currency"] = extract_currency_from_ads(ads_complete)
            else:
                data["ads_active_total"] = data["ads_found_search"]

            processed += 1

        time.sleep(META_DELAY_BETWEEN_BATCHES)  # Pause entre les batches

    pages_final = {pid: data for pid, data in pages_with_cms.items() if data["ads_active_total"] >= min_ads}

    # Stats détaillées Phase 5
    total_ads_counted = sum(d.get("ads_active_total", 0) for d in pages_final.values())
    avg_ads = total_ads_counted // len(pages_final) if pages_final else 0

    # Répartition par état
    etat_counts = {}
    for data in pages_final.values():
        ads_count = data.get("ads_active_total", 0)
        etat = get_etat_from_ads_count(ads_count)
        etat_counts[etat] = etat_counts.get(etat, 0) + 1

    phase5_stats = {
        "Pages comptées": len(pages_with_cms),
        "Pages finales": len(pages_final),
        "Total ads actives": total_ads_counted,
        "Moyenne ads/page": avg_ads,
    }
    # Ajouter répartition par état
    for etat in ["XXL", "XL", "L", "M", "S", "XS"]:
        if etat in etat_counts:
            phase5_stats[f"État {etat}"] = etat_counts[etat]

    tracker.complete_phase(f"{len(pages_final)} pages finales", stats=phase5_stats)

    if not pages_final:
        st.warning("Aucune page finale trouvée")
        return

    # ═══ PHASE 6: Analyse des sites web (multithreaded + cache) ═══
    tracker.start_phase(6, "🔬 Analyse sites web (parallèle)", total_phases=8)
    web_results = {}

    # Séparer les pages à analyser vs celles en cache
    pages_need_analysis = []
    for pid, data in pages_final.items():
        cached = cached_pages.get(str(pid), {})
        # Utiliser les infos en cache si le scan est récent
        if not cached.get("needs_rescan") and cached.get("nombre_produits") is not None:
            web_results[pid] = {
                "product_count": cached.get("nombre_produits", 0),
                "theme": cached.get("template", ""),
                "category": cached.get("thematique", ""),
                "currency_from_site": cached.get("devise", ""),
                "_from_cache": True
            }
            if cached.get("devise") and not data.get("currency"):
                data["currency"] = cached["devise"]
        elif data.get("website"):
            pages_need_analysis.append((pid, data))

    cached_analysis = len(web_results)
    st.info(f"🔬 {len(pages_need_analysis)} sites à analyser ({cached_analysis} en cache)")

    # Fonction worker pour analyse parallèle
    def analyze_web_worker(pid_data):
        pid, data = pid_data
        try:
            result = analyze_website_complete(data["website"], countries[0])
            return pid, result
        except Exception as e:
            return pid, {"product_count": 0, "error": str(e)}

    # Multithreading pour l'analyse web (8 workers)
    if pages_need_analysis:
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_web_worker, item): item[0] for item in pages_need_analysis}

            for future in as_completed(futures):
                pid, result = future.result()
                web_results[pid] = result
                data = pages_final[pid]
                if not data.get("currency") and result.get("currency_from_site"):
                    data["currency"] = result["currency_from_site"]
                completed += 1
                if completed % 5 == 0:
                    tracker.update_step("Analyse web", completed, len(pages_need_analysis))

    # Stats détaillées Phase 6
    total_products = sum(r.get("product_count", 0) for r in web_results.values())
    avg_products = total_products // len(web_results) if web_results else 0

    phase6_stats = {
        "Sites analysés": len(web_results),
        "En cache": cached_analysis,
        "Nouvelles analyses": len(pages_need_analysis),
        "Total produits": total_products,
        "Moyenne produits/site": avg_products,
    }
    tracker.complete_phase(f"{len(web_results)} sites analysés ({cached_analysis} cache)", stats=phase6_stats)

    # ═══ PHASE 7: Détection des Winning Ads ═══
    tracker.start_phase(7, "🏆 Détection des Winning Ads", total_phases=8)
    scan_date = datetime.now()
    winning_ads_data = []
    winning_ads_by_page = {}  # {page_id: count}
    total_ads_checked = 0

    for i, (pid, data) in enumerate(pages_final.items()):
        page_name = data.get("page_name", pid)[:30]
        tracker.update_step("Analyse winning", i + 1, len(pages_final), f"Page: {page_name}")

        page_winning_count = 0
        for ad in page_ads.get(pid, []):
            is_winning, age_days, reach, matched_criteria = is_winning_ad(ad, scan_date, WINNING_AD_CRITERIA)
            if is_winning:
                winning_ads_data.append({
                    "ad": ad,
                    "page_id": pid,
                    "age_days": age_days,
                    "reach": reach,
                    "matched_criteria": matched_criteria
                })
                page_winning_count += 1
            total_ads_checked += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

    # Compter par critère
    criteria_counts = {}
    for w in winning_ads_data:
        criteria = w.get("matched_criteria", "Unknown")
        criteria_counts[criteria] = criteria_counts.get(criteria, 0) + 1

    # Stats détaillées Phase 7
    phase7_stats = {
        "Ads analysées": total_ads_checked,
        "Winning ads": len(winning_ads_data),
        "Pages avec winning": len(winning_ads_by_page),
        "Taux de winning": f"{(len(winning_ads_data)/total_ads_checked*100):.1f}%" if total_ads_checked else "0%",
    }
    # Ajouter les critères
    for criteria, count in sorted(criteria_counts.items(), key=lambda x: -x[1]):
        phase7_stats[f"🎯 {criteria}"] = count

    tracker.complete_phase(f"{len(winning_ads_data)} winning ads sur {len(winning_ads_by_page)} pages", details={
        "winning_ads_count": len(winning_ads_data),
        "pages_with_winning": len(winning_ads_by_page),
        "total_ads_checked": total_ads_checked
    }, stats=phase7_stats)
    tracker.update_metric("winning_ads_count", len(winning_ads_data))

    # Save to session first (needed for preview mode)
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.winning_ads_data = winning_ads_data
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.preview_mode = preview_mode

    if preview_mode:
        # Mode aperçu - afficher le résumé et finaliser le log
        tracker.show_summary()
        tracker.finalize_log(status="preview")
        st.success(f"✓ Recherche terminée ! {len(pages_final)} pages trouvées")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        # ═══ PHASE 8: Sauvegarde en base de données ═══
        tracker.start_phase(8, "💾 Sauvegarde en base de données", total_phases=8)

        pages_saved = 0
        suivi_saved = 0
        ads_saved = 0
        winning_saved = 0

        if db:
            try:
                tracker.update_step("Sauvegarde pages", 1, 4)
                thresholds = st.session_state.get("state_thresholds", None)
                pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)

                tracker.update_step("Sauvegarde suivi", 2, 4)
                det = st.session_state.get("detection_thresholds", {})
                suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI))

                tracker.update_step("Sauvegarde annonces", 3, 4)
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, det.get("min_ads_liste", MIN_ADS_LISTE))

                tracker.update_step("Sauvegarde winning ads", 4, 4)
                winning_saved, winning_skipped = save_winning_ads(db, winning_ads_data, pages_final)

                msg = f"{pages_saved} pages, {suivi_saved} suivi, {ads_saved} ads, {winning_saved} winning"
                if winning_skipped > 0:
                    msg += f" ({winning_skipped} doublons)"

                # Stats détaillées Phase 8
                phase8_stats = {
                    "Pages sauvées": pages_saved,
                    "Suivi pages": suivi_saved,
                    "Annonces sauvées": ads_saved,
                    "Winning ads sauvées": winning_saved,
                    "Winning doublons ignorés": winning_skipped,
                }
                tracker.complete_phase(msg, details={
                    "pages_saved": pages_saved,
                    "suivi_saved": suivi_saved,
                    "ads_saved": ads_saved,
                    "winning_saved": winning_saved,
                    "winning_skipped": winning_skipped
                }, stats=phase8_stats)
                tracker.update_metric("pages_saved", pages_saved)
                tracker.update_metric("ads_saved", ads_saved)

            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")
                tracker.finalize_log(status="failed", error_message=str(e))

        # ═══ PHASE 9: Classification automatique (Gemini) ═══
        # Utilise les données pré-extraites en phase 6 pour éviter de re-scraper
        classified_count = 0
        gemini_key = os.getenv("GEMINI_API_KEY", "")

        if gemini_key and pages_saved > 0:
            tracker.start_phase(9, "🏷️ Classification automatique (Gemini)", total_phases=9)

            try:
                from app.gemini_classifier import classify_with_extracted_content
                from app.database import init_default_taxonomy

                # Initialiser la taxonomie si nécessaire
                init_default_taxonomy(db)

                # Préparer les pages avec les données DÉJÀ EXTRAITES en phase 6
                pages_to_classify = []
                for pid, data in pages_final.items():
                    if data.get("website"):
                        # Récupérer les données extraites pendant l'analyse web (phase 6)
                        web_data = web_results.get(pid, {})
                        pages_to_classify.append({
                            "page_id": pid,
                            "url": data.get("website", ""),
                            "site_title": web_data.get("site_title", ""),
                            "site_description": web_data.get("site_description", ""),
                            "site_h1": web_data.get("site_h1", ""),
                            "site_keywords": web_data.get("site_keywords", "")
                        })

                if pages_to_classify:
                    tracker.update_step("Classification", 1, 1, f"{len(pages_to_classify)} pages")

                    # Classifier avec les données pré-extraites (pas de re-scraping!)
                    result = classify_with_extracted_content(db, pages_to_classify)

                    classified_count = result.get("classified", 0)
                    errors_count = result.get("errors", 0)

                    phase9_stats = {
                        "Pages à classifier": len(pages_to_classify),
                        "Pages classifiées": classified_count,
                        "Erreurs": errors_count,
                    }
                    tracker.complete_phase(f"{classified_count} pages classifiées", stats=phase9_stats)
                else:
                    tracker.complete_phase("Aucune page avec URL à classifier", stats={"Pages": 0})

            except Exception as e:
                st.warning(f"⚠️ Classification non effectuée: {str(e)[:100]}")
                tracker.complete_phase(f"Erreur: {str(e)[:50]}", stats={"Erreur": str(e)[:100]})
        elif not gemini_key:
            # Pas de clé Gemini configurée - on skip silencieusement
            pass

        # Afficher le résumé final
        tracker.show_summary()
        tracker.finalize_log(status="completed")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Pages", pages_saved)
        col2.metric("Suivi", suivi_saved)
        col3.metric("Annonces", ads_saved)
        col4.metric("🏆 Winning", winning_saved)
        col5.metric("🏷️ Classifiées", classified_count)

        st.balloons()
        st.success("🎉 Recherche terminée !")


def run_page_id_search(page_ids, countries, languages, selected_cms, preview_mode=False):
    """Exécute la recherche par Page IDs (optimisée par batch de 10)"""
    from app.meta_api import init_token_rotator

    db = get_database()

    # Charger les tokens depuis la base de données (avec IDs pour le logging)
    tokens_with_proxies = []
    if db:
        try:
            from app.database import get_active_meta_tokens_with_proxies, ensure_tables_exist
            ensure_tables_exist(db)
            tokens_with_proxies = get_active_meta_tokens_with_proxies(db)
        except Exception as e:
            st.warning(f"⚠️ Impossible de charger les tokens: {e}")

    # Fallback sur variable d'environnement
    if not tokens_with_proxies:
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            tokens_with_proxies = [{"id": None, "token": env_token, "proxy": None, "name": "Env Token"}]

    if not tokens_with_proxies:
        st.error("❌ Aucun token Meta API disponible. Configurez vos tokens dans **Settings > Tokens Meta API**.")
        return

    # Sauvegarder dans l'historique
    add_to_search_history('page_ids', {
        'page_ids': page_ids,
        'countries': countries,
        'languages': languages,
        'cms': selected_cms
    })

    # Initialiser le TokenRotator
    rotator = init_token_rotator(tokens_with_proxies=tokens_with_proxies, db=db)
    if rotator.token_count > 1:
        st.success(f"🔄 Rotation automatique activée ({rotator.token_count} tokens)")

    client = MetaAdsClient(rotator.get_current_token())

    # Récupérer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db)
        if blacklist_ids:
            st.info(f"🚫 {len(blacklist_ids)} pages en blacklist seront ignorées")

    # Filtrer les page_ids blacklistés
    page_ids_filtered = [pid for pid in page_ids if str(pid) not in blacklist_ids]
    if len(page_ids_filtered) < len(page_ids):
        st.warning(f"⚠️ {len(page_ids) - len(page_ids_filtered)} Page IDs ignorés (blacklist)")

    if not page_ids_filtered:
        st.error("Aucun Page ID valide après filtrage blacklist")
        return

    # Phase 1: Récupération des annonces par batch
    st.subheader("📊 Phase 1: Récupération des annonces")
    batch_size = 10
    total_batches = (len(page_ids_filtered) + batch_size - 1) // batch_size
    st.caption(f"⚡ {len(page_ids_filtered)} Page IDs → {total_batches} requêtes API")

    pages = {}
    page_ads = defaultdict(list)
    progress = st.progress(0)

    processed = 0
    for batch_idx in range(0, len(page_ids_filtered), batch_size):
        batch_pids = page_ids_filtered[batch_idx:batch_idx + batch_size]

        # Fetch batch
        batch_results = client.fetch_ads_for_pages_batch(batch_pids, countries, languages)

        # Traiter les résultats
        for pid in batch_pids:
            pid_str = str(pid)
            ads_list, count = batch_results.get(pid_str, ([], 0))

            if count > 0:
                # Extraire le page_name depuis les ads
                page_name = ""
                if ads_list:
                    page_name = ads_list[0].get("page_name", "")

                pages[pid_str] = {
                    "page_id": pid_str,
                    "page_name": page_name,
                    "website": extract_website_from_ads(ads_list),
                    "ads_active_total": count,
                    "currency": extract_currency_from_ads(ads_list),
                    "cms": "Unknown",
                    "is_shopify": False,
                    "_keywords": set()  # Pas de keywords pour cette recherche
                }
                page_ads[pid_str] = ads_list

            processed += 1
            progress.progress(processed / len(page_ids_filtered))

        time.sleep(META_DELAY_BETWEEN_BATCHES)  # Pause entre les batches

    st.success(f"✓ {len(pages)} pages avec annonces actives trouvées")

    if not pages:
        st.warning("Aucune page trouvée avec des annonces actives")
        return

    # Phase 2: Détection CMS
    st.subheader("🔍 Phase 2: Détection CMS")
    pages_with_sites = {pid: data for pid, data in pages.items() if data["website"]}
    progress = st.progress(0)

    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow"]

    for i, (pid, data) in enumerate(pages_with_sites.items()):
        cms_result = detect_cms_from_url(data["website"])
        data["cms"] = cms_result["cms"]
        data["is_shopify"] = cms_result["is_shopify"]
        progress.progress((i + 1) / len(pages_with_sites))
        time.sleep(WEB_DELAY_CMS_CHECK)  # Délai pour éviter ban Shopify

    # Filtrer par CMS sélectionnés
    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in cms_options:
            return True
        return False

    pages_final = {pid: data for pid, data in pages.items() if cms_matches(data.get("cms", "Unknown"))}
    st.success(f"✓ {len(pages_final)} pages avec CMS sélectionnés")

    if not pages_final:
        st.warning("Aucune page trouvée avec les CMS sélectionnés")
        return

    # Phase 3: Analyse web
    st.subheader("🔬 Phase 3: Analyse des sites web")
    web_results = {}
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_final.items()):
        if data["website"]:
            result = analyze_website_complete(data["website"], countries[0])
            web_results[pid] = result
            if not data["currency"] and result.get("currency_from_site"):
                data["currency"] = result["currency_from_site"]
        progress.progress((i + 1) / len(pages_final))
        time.sleep(0.2)

    # Phase 4: Détection des Winning Ads
    st.subheader("🏆 Phase 4: Détection des Winning Ads")
    scan_date = datetime.now()
    winning_ads_data = []
    winning_ads_by_page = {}

    progress = st.progress(0)
    for i, (pid, data) in enumerate(pages_final.items()):
        page_winning_count = 0
        for ad in page_ads.get(pid, []):
            is_winning, age_days, reach, matched_criteria = is_winning_ad(ad, scan_date, WINNING_AD_CRITERIA)
            if is_winning:
                winning_ads_data.append({
                    "ad": ad,
                    "page_id": pid,
                    "age_days": age_days,
                    "reach": reach,
                    "matched_criteria": matched_criteria
                })
                page_winning_count += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

        progress.progress((i + 1) / len(pages_final))

    st.success(f"✓ {len(winning_ads_data)} winning ads détectées sur {len(winning_ads_by_page)} pages")

    # Save to session
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.winning_ads_data = winning_ads_data
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.preview_mode = preview_mode

    if preview_mode:
        st.success(f"✓ Recherche terminée ! {len(pages_final)} pages trouvées")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        st.subheader("💾 Phase 5: Sauvegarde en base de données")

        if db:
            try:
                thresholds = st.session_state.get("state_thresholds", None)
                pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                det = st.session_state.get("detection_thresholds", {})
                suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI))
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, det.get("min_ads_liste", MIN_ADS_LISTE))
                winning_saved, winning_skipped = save_winning_ads(db, winning_ads_data, pages_final)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Pages", pages_saved)
                col2.metric("Suivi", suivi_saved)
                col3.metric("Annonces", ads_saved)
                col4.metric("🏆 Winning", winning_saved, delta=f"-{winning_skipped} doublons" if winning_skipped > 0 else None)
                st.success("✓ Données sauvegardées !")
            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")

        st.balloons()
        st.success("🎉 Recherche terminée !")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: PAGES / SHOPS
# ═══════════════════════════════════════════════════════════════════════════════

def render_pages_shops():
    """Page Pages/Shops - Liste des pages avec score et export"""
    st.title("🏪 Pages / Shops")
    st.markdown("Explorer toutes les pages et boutiques")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Initialiser les pages sélectionnées dans session_state
    if 'selected_pages' not in st.session_state:
        st.session_state.selected_pages = []

    # ═══ FILTRES SAUVEGARDÉS ═══
    saved_filters = get_saved_filters(db, filter_type="pages")

    col_saved, col_save_btn = st.columns([4, 1])
    with col_saved:
        filter_options = ["-- Filtres sauvegardés --"] + [f["name"] for f in saved_filters]
        selected_saved = st.selectbox("📂 Charger un filtre", filter_options, key="load_filter")

    # Charger le filtre sélectionné
    loaded_filter = None
    if selected_saved != "-- Filtres sauvegardés --":
        for f in saved_filters:
            if f["name"] == selected_saved:
                loaded_filter = f["filters"]
                break

    # ═══ FILTRES ═══
    st.markdown("#### 🔍 Filtres")

    # Ligne 1: Recherche, CMS, État
    col1, col2, col3 = st.columns(3)

    with col1:
        default_search = loaded_filter.get("search_term", "") if loaded_filter else ""
        search_term = st.text_input("🔍 Rechercher", value=default_search, placeholder="Nom ou site...")

    with col2:
        cms_options = ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"]
        default_cms = loaded_filter.get("cms", "Tous") if loaded_filter else "Tous"
        cms_idx = cms_options.index(default_cms) if default_cms in cms_options else 0
        cms_filter = st.selectbox("CMS", cms_options, index=cms_idx)

    with col3:
        etat_options = ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"]
        default_etat = loaded_filter.get("etat", "Tous") if loaded_filter else "Tous"
        etat_idx = etat_options.index(default_etat) if default_etat in etat_options else 0
        etat_filter = st.selectbox("État", etat_options, index=etat_idx)

    # Ligne 2: Classification (Thématique, Classification, Pays, Limite)
    col4, col5, col6, col7 = st.columns(4)

    with col4:
        # Filtre par thématique/catégorie
        thematique_options = ["Toutes", "Non classifiées"] + get_taxonomy_categories(db)
        thematique_filter = st.selectbox("Thématique", thematique_options, index=0, key="pages_thematique")

    with col5:
        # Filtre par classification (dépend de thématique)
        if thematique_filter not in ["Toutes", "Non classifiées"]:
            subcategory_options = ["Toutes"] + get_all_subcategories(db, category=thematique_filter)
        else:
            subcategory_options = ["Toutes"] + get_all_subcategories(db)
        subcategory_filter = st.selectbox("Classification", subcategory_options, index=0, key="pages_subcategory")

    with col6:
        # Filtre par pays
        countries = get_all_countries(db)
        country_names = {
            "FR": "🇫🇷 France", "DE": "🇩🇪 Allemagne", "ES": "🇪🇸 Espagne",
            "IT": "🇮🇹 Italie", "GB": "🇬🇧 UK", "US": "🇺🇸 USA",
            "BE": "🇧🇪 Belgique", "CH": "🇨🇭 Suisse", "NL": "🇳🇱 Pays-Bas",
        }
        pays_display = ["Tous"] + [country_names.get(c, c) for c in countries]
        pays_values = [None] + countries
        pays_idx = st.selectbox(
            "🌍 Pays",
            range(len(pays_display)),
            format_func=lambda i: pays_display[i],
            index=0,
            key="pages_pays"
        )
        pays_filter = pays_values[pays_idx]

    with col7:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    # Sauvegarder le filtre actuel
    with col_save_btn:
        st.write("")
        with st.popover("💾 Sauver"):
            new_filter_name = st.text_input("Nom du filtre", key="new_filter_name")
            if st.button("Sauvegarder", key="save_filter_btn"):
                if new_filter_name:
                    current_filters = {
                        "search_term": search_term,
                        "cms": cms_filter,
                        "etat": etat_filter
                    }
                    save_filter(db, new_filter_name, current_filters, "pages")
                    st.success(f"Filtre '{new_filter_name}' sauvegardé!")
                    st.rerun()

    # Supprimer un filtre sauvegardé
    if saved_filters:
        with st.expander("🗑️ Gérer les filtres sauvegardés"):
            for sf in saved_filters:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"📂 {sf['name']}")
                with col2:
                    if st.button("❌", key=f"del_filter_{sf['id']}"):
                        delete_saved_filter(db, sf['id'])
                        st.rerun()

    # Mode d'affichage et export
    col_mode, col_bulk, col_export = st.columns([2, 1, 1])
    with col_mode:
        view_mode = st.radio("Mode d'affichage", ["Tableau", "Détaillé", "Sélection"], horizontal=True)

    # Recherche
    try:
        # Déterminer le filtre thématique
        thematique_param = None
        if thematique_filter == "Non classifiées":
            thematique_param = "__unclassified__"  # Valeur spéciale
        elif thematique_filter != "Toutes":
            thematique_param = thematique_filter

        # Déterminer le filtre sous-thématique
        subcategory_param = None
        if subcategory_filter != "Toutes":
            subcategory_param = subcategory_filter

        results = search_pages(
            db,
            cms=cms_filter if cms_filter != "Tous" else None,
            etat=etat_filter if etat_filter != "Tous" else None,
            search_term=search_term if search_term else None,
            thematique=thematique_param,
            subcategory=subcategory_param,
            pays=pays_filter,
            limit=limit
        )

        if results:
            # Enrichir avec scores et winning ads
            winning_by_page = get_winning_ads_by_page(db, days=30)
            winning_counts = {str(k): v for k, v in winning_by_page.items()}

            for page in results:
                pid = str(page.get("page_id", ""))
                winning_count = winning_counts.get(pid, 0)
                page["winning_ads"] = winning_count
                page["score"] = calculate_page_score(page, winning_count)

            # Trier par score
            results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

            # Export CSV personnalisé
            with col_export:
                # Définir toutes les colonnes disponibles
                all_export_columns = {
                    "Page ID": lambda p: p.get("page_id", ""),
                    "Nom": lambda p: p.get("page_name", ""),
                    "Site": lambda p: p.get("lien_site", ""),
                    "CMS": lambda p: p.get("cms", ""),
                    "État": lambda p: p.get("etat", ""),
                    "Ads Actives": lambda p: p.get("nombre_ads_active", 0),
                    "Winning Ads": lambda p: p.get("winning_ads", 0),
                    "Produits": lambda p: p.get("nombre_produits", 0),
                    "Score": lambda p: p.get("score", 0),
                    "Keywords": lambda p: p.get("keywords", ""),
                    "Thématique": lambda p: p.get("thematique", ""),
                    "Sous-catégorie": lambda p: p.get("subcategory", ""),
                    "Confiance Classif.": lambda p: f"{int(p.get('classification_confidence', 0)*100)}%" if p.get('classification_confidence') else "",
                    "Ads Library": lambda p: p.get("lien_fb_ad_library", ""),
                    "Page Facebook": lambda p: f"https://www.facebook.com/{p.get('page_id', '')}",
                    "Date création": lambda p: p.get("date_creation", ""),
                    "Dernière MAJ": lambda p: p.get("date_maj", "")
                }

                # Colonnes par défaut
                default_columns = ["Page ID", "Nom", "Site", "CMS", "État", "Ads Actives", "Winning Ads", "Score"]

                with st.popover("📥 Export CSV"):
                    st.markdown("**Colonnes à exporter:**")
                    selected_columns = st.multiselect(
                        "Sélectionner les colonnes",
                        options=list(all_export_columns.keys()),
                        default=default_columns,
                        key="export_columns_pages",
                        label_visibility="collapsed"
                    )

                    # Présets rapides
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        if st.button("📋 Essentiel", key="preset_essential", width="stretch"):
                            st.session_state.export_columns_pages = ["Page ID", "Nom", "Site", "CMS", "État", "Score"]
                            st.rerun()
                    with col_p2:
                        if st.button("📊 Complet", key="preset_full", width="stretch"):
                            st.session_state.export_columns_pages = list(all_export_columns.keys())
                            st.rerun()

                    if selected_columns:
                        # Générer les données d'export
                        export_data = []
                        for p in results:
                            row = {col: all_export_columns[col](p) for col in selected_columns}
                            export_data.append(row)

                        csv_data = export_to_csv(export_data)
                        st.download_button(
                            f"📥 Télécharger ({len(selected_columns)} colonnes)",
                            csv_data,
                            file_name=f"pages_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            width="stretch"
                        )
                    else:
                        st.warning("Sélectionnez au moins une colonne")

            col_results, col_help = st.columns([3, 1])
            with col_results:
                st.markdown(f"**{len(results)} résultats**")
            with col_help:
                with st.popover("ℹ️ Calcul du score"):
                    st.markdown("""
**Score de performance (0-100 pts)**

**Nombre d'ads actives** (max 40 pts)
- ≥150 ads → 40 pts
- ≥80 ads → 35 pts
- ≥35 ads → 25 pts
- ≥20 ads → 15 pts
- ≥10 ads → 10 pts
- ≥1 ad → 5 pts

**Winning Ads** (max 30 pts)
- ≥10 winning → 30 pts
- ≥5 winning → 25 pts
- ≥3 winning → 20 pts
- ≥1 winning → 15 pts

**Produits** (max 20 pts)
- ≥100 produits → 20 pts
- ≥50 produits → 15 pts
- ≥20 produits → 10 pts
- ≥5 produits → 5 pts

**Bonus CMS** (+10 pts)
- Shopify → +10 pts
""")

            # ═══ MODE SÉLECTION (BULK ACTIONS) ═══
            if view_mode == "Sélection":
                st.info("☑️ Cochez les pages puis appliquez une action groupée")

                # Barre d'actions groupées
                col_actions = st.columns([1, 1, 1, 1, 2])

                with col_actions[0]:
                    if st.button("☑️ Tout sélectionner"):
                        st.session_state.selected_pages = [p.get("page_id") for p in results]
                        st.rerun()

                with col_actions[1]:
                    if st.button("❎ Tout désélectionner"):
                        st.session_state.selected_pages = []
                        st.rerun()

                selected_count = len(st.session_state.selected_pages)
                st.caption(f"**{selected_count}** page(s) sélectionnée(s)")

                # Actions sur la sélection
                if selected_count > 0:
                    st.markdown("---")
                    st.markdown("**Actions groupées:**")
                    action_cols = st.columns(5)

                    with action_cols[0]:
                        if st.button("⭐ Ajouter favoris", width="stretch"):
                            count = bulk_add_to_favorites(db, st.session_state.selected_pages)
                            st.success(f"{count} page(s) ajoutée(s) aux favoris")
                            st.session_state.selected_pages = []
                            st.rerun()

                    with action_cols[1]:
                        if st.button("🚫 Blacklister", width="stretch"):
                            count = bulk_add_to_blacklist(db, st.session_state.selected_pages, "Bulk blacklist")
                            st.success(f"{count} page(s) blacklistée(s)")
                            st.session_state.selected_pages = []
                            st.rerun()

                    with action_cols[2]:
                        # Ajouter à une collection
                        collections = get_collections(db)
                        if collections:
                            coll_names = [c["name"] for c in collections]
                            selected_coll = st.selectbox("📁 Collection", ["--"] + coll_names, key="bulk_coll")
                            if selected_coll != "--":
                                coll_id = next(c["id"] for c in collections if c["name"] == selected_coll)
                                if st.button("Ajouter", key="bulk_add_coll"):
                                    count = bulk_add_to_collection(db, coll_id, st.session_state.selected_pages)
                                    st.success(f"{count} page(s) ajoutée(s)")
                                    st.session_state.selected_pages = []
                                    st.rerun()

                    with action_cols[3]:
                        # Ajouter un tag
                        all_tags = get_all_tags(db)
                        if all_tags:
                            tag_names = [t["name"] for t in all_tags]
                            selected_tag = st.selectbox("🏷️ Tag", ["--"] + tag_names, key="bulk_tag")
                            if selected_tag != "--":
                                tag_id = next(t["id"] for t in all_tags if t["name"] == selected_tag)
                                if st.button("Ajouter", key="bulk_add_tag"):
                                    count = bulk_add_tag(db, tag_id, st.session_state.selected_pages)
                                    st.success(f"Tag ajouté à {count} page(s)")
                                    st.session_state.selected_pages = []
                                    st.rerun()

                st.markdown("---")

                # Liste avec checkboxes
                for page in results:
                    pid = page.get("page_id")
                    score = page.get("score", 0)
                    score_icon = get_score_color(score)

                    col_check, col_info = st.columns([1, 10])

                    with col_check:
                        is_selected = pid in st.session_state.selected_pages
                        if st.checkbox("", value=is_selected, key=f"sel_{pid}"):
                            if pid not in st.session_state.selected_pages:
                                st.session_state.selected_pages.append(pid)
                        else:
                            if pid in st.session_state.selected_pages:
                                st.session_state.selected_pages.remove(pid)

                    with col_info:
                        st.write(f"{score_icon} **{page.get('page_name', 'N/A')}** | {page.get('etat', 'N/A')} | {page.get('nombre_ads_active', 0)} ads | Score: {score}")

            # ═══ MODE TABLEAU ═══
            elif view_mode == "Tableau":
                df = pd.DataFrame(results)

                # Ajouter colonne Score visuel
                df["score_display"] = df.apply(
                    lambda r: f"{get_score_color(r.get('score', 0))} {r.get('score', 0)}", axis=1
                )

                # Formater états avec badges emoji
                df["etat_display"] = df["etat"].apply(lambda x: format_state_for_df(x) if x else "")

                # Formater thématique
                df["thematique_display"] = df["thematique"].apply(lambda x: x if x else "—")

                # Formater classification avec badge de confiance
                def format_classification(row):
                    subcat = row.get("subcategory", "")
                    conf = row.get("classification_confidence", 0)
                    if subcat:
                        # Badge de confiance (sans emoji)
                        if conf and conf >= 0.8:
                            return f"{subcat} ({int(conf*100)}%)"
                        elif conf and conf >= 0.5:
                            return f"{subcat} ({int(conf*100)}%)"
                        else:
                            return subcat
                    return "—"

                df["classification_display"] = df.apply(format_classification, axis=1)

                # Colonnes à afficher (avec thématique et classification)
                display_cols = ["score_display", "page_name", "lien_site", "cms", "etat_display", "nombre_ads_active", "winning_ads", "thematique_display", "classification_display"]
                df_display = df[[c for c in display_cols if c in df.columns]]

                # Renommer colonnes
                col_names = ["Score", "Nom", "Site", "CMS", "État", "Ads", "🏆", "Thématique", "Classification"]
                df_display.columns = col_names[:len(df_display.columns)]

                st.dataframe(
                    df_display,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Site": st.column_config.LinkColumn("Site"),
                    }
                )
            else:
                # Vue détaillée avec boutons blacklist et score
                for page in results:
                    score = page.get("score", 0)
                    winning = page.get("winning_ads", 0)
                    score_icon = get_score_color(score)

                    with st.expander(f"{score_icon} **{page.get('page_name', 'N/A')}** - Score: {score} | {page.get('etat', 'N/A')} ({page.get('nombre_ads_active', 0)} ads, {winning} 🏆)"):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            pid = page.get('page_id')

                            st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                            st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")
                            st.write(f"**Score:** {score}/100 | **Winning Ads:** {winning}")
                            if page.get('keywords'):
                                st.write(f"**Keywords:** {page.get('keywords', '')}")

                            # Classification éditable
                            st.markdown("---")
                            st.markdown("**Classification:**")
                            edit_col1, edit_col2 = st.columns(2)

                            current_thematique = page.get('thematique', '') or ''
                            current_subcat = page.get('subcategory', '') or ''
                            conf = page.get('classification_confidence', 0)

                            with edit_col1:
                                thematique_options_edit = [""] + get_taxonomy_categories(db)
                                current_idx = thematique_options_edit.index(current_thematique) if current_thematique in thematique_options_edit else 0
                                new_thematique = st.selectbox(
                                    "Thématique",
                                    thematique_options_edit,
                                    index=current_idx,
                                    key=f"edit_them_{pid}"
                                )

                            with edit_col2:
                                if new_thematique:
                                    subcat_options_edit = [""] + get_all_subcategories(db, category=new_thematique)
                                else:
                                    subcat_options_edit = [""] + get_all_subcategories(db)
                                current_subcat_idx = subcat_options_edit.index(current_subcat) if current_subcat in subcat_options_edit else 0
                                new_classification = st.selectbox(
                                    "Classification",
                                    subcat_options_edit,
                                    index=current_subcat_idx,
                                    key=f"edit_class_{pid}"
                                )

                            # Bouton sauvegarder si modifié
                            if new_thematique != current_thematique or new_classification != current_subcat:
                                if st.button("💾 Sauvegarder classification", key=f"save_class_{pid}"):
                                    from app.database import update_page_classification
                                    update_page_classification(db, pid, new_thematique, new_classification, confidence=1.0)
                                    st.success("Classification mise à jour!")
                                    st.rerun()
                            elif conf:
                                st.caption(f"Confiance: {int(conf*100)}%")

                            # Afficher les tags
                            page_tags = get_page_tags(db, pid)
                            if page_tags:
                                tag_html = " ".join([f"<span style='background-color:{t['color']};color:white;padding:2px 8px;border-radius:10px;margin-right:5px;font-size:11px;'>{t['name']}</span>" for t in page_tags])
                                st.markdown(tag_html, unsafe_allow_html=True)

                            # Notes
                            st.markdown("---")
                            notes = get_page_notes(db, pid)
                            if notes:
                                st.caption(f"📝 {len(notes)} note(s)")
                                for note in notes[:2]:
                                    st.caption(f"• {note['content'][:50]}...")

                            # Ajouter une note
                            with st.popover("📝 Ajouter note"):
                                new_note = st.text_area("Note", key=f"note_{pid}", placeholder="Votre note...")
                                if st.button("Sauvegarder", key=f"save_note_{pid}"):
                                    if new_note:
                                        add_page_note(db, pid, new_note)
                                        st.success("Note ajoutée!")
                                        st.rerun()

                        with col2:
                            # Favori
                            is_fav = is_favorite(db, pid)
                            fav_icon = "⭐" if is_fav else "☆"
                            if st.button(f"{fav_icon} Favori", key=f"fav_{pid}"):
                                toggle_favorite(db, pid)
                                st.rerun()

                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                            # Bouton copie Page ID
                            st.code(pid, language=None)

                            # Ajouter à une collection
                            collections = get_collections(db)
                            if collections:
                                with st.popover("📁 Collection"):
                                    for coll in collections:
                                        if st.button(f"{coll['icon']} {coll['name']}", key=f"addcoll_{pid}_{coll['id']}"):
                                            add_page_to_collection(db, coll['id'], pid)
                                            st.success(f"Ajouté à {coll['name']}")
                                            st.rerun()

                            # Ajouter un tag
                            all_tags = get_all_tags(db)
                            if all_tags:
                                with st.popover("🏷️ Tag"):
                                    for tag in all_tags:
                                        if st.button(f"{tag['name']}", key=f"addtag_{pid}_{tag['id']}"):
                                            add_tag_to_page(db, pid, tag['id'])
                                            st.success(f"Tag ajouté!")
                                            st.rerun()

                            if st.button("🚫 Blacklist", key=f"bl_page_{pid}"):
                                if add_to_blacklist(db, pid, page.get('page_name', ''), "Blacklisté depuis Pages/Shops"):
                                    st.success(f"✓ Blacklisté")
                                    st.rerun()
                                else:
                                    st.warning("Déjà blacklisté")
        else:
            st.info("Aucun résultat trouvé")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: WATCHLISTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_watchlists():
    """Page Watchlists - Listes de surveillance"""
    st.title("📋 Watchlists")
    st.markdown("Gérer vos listes de surveillance")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Filtres de classification + date
    st.markdown("#### 🔍 Filtres")
    filter_col1, filter_col2 = st.columns([3, 1])

    with filter_col1:
        filters = render_classification_filters(db, key_prefix="watchlists", columns=3)

    with filter_col2:
        days_filter = render_date_filter(key_prefix="watchlists")

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"🏷️ {filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"📂 {filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"🌍 {filters['pays']}")
    if days_filter > 0:
        active_filters.append(f"📅 {days_filter}j")

    if active_filters:
        st.caption(f"Filtres actifs: {' • '.join(active_filters)}")

    st.markdown("---")

    # Créer 3 onglets pour les différentes vues
    tab1, tab2, tab3 = st.tabs(["🌟 Top Performers", "🏆 Top Winning Ads", "📊 Pages avec le + de Winning Ads"])

    # ═══ TAB 1: Top Performers ═══
    with tab1:
        st.subheader("🌟 Top Performers (≥80 ads)")
        try:
            top_pages = search_pages(
                db, etat="XXL", limit=20,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays"),
                days=days_filter if days_filter > 0 else None
            )
            top_pages.extend(search_pages(
                db, etat="XL", limit=20,
                thematique=filters.get("thematique"),
                subcategory=filters.get("subcategory"),
                pays=filters.get("pays"),
                days=days_filter if days_filter > 0 else None
            ))

            if top_pages:
                # Trier par nombre d'ads décroissant
                top_pages_sorted = sorted(top_pages, key=lambda x: x.get("nombre_ads_active", 0), reverse=True)[:20]
                df = pd.DataFrame(top_pages_sorted)

                # Formater la date
                if "dernier_scan" in df.columns:
                    df["dernier_scan"] = pd.to_datetime(df["dernier_scan"]).dt.strftime("%d/%m/%Y %H:%M")

                cols = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active", "dernier_scan", "subcategory", "pays"]
                df_display = df[[c for c in cols if c in df.columns]]
                df_display.columns = ["Page", "Site", "CMS", "État", "Ads Actives", "Dernier Scan", "Catégorie", "Pays"][:len(df_display.columns)]

                col_table, col_export = st.columns([4, 1])
                with col_table:
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                with col_export:
                    render_csv_download(df_display, f"top_performers_{datetime.now().strftime('%Y%m%d')}.csv", "📥 CSV")
            else:
                st.info("Aucune page XXL/XL trouvée")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # ═══ TAB 2: Top Winning Ads ═══
    with tab2:
        st.subheader("🏆 Top Winning Ads (Best Performers)")
        st.caption("Ads avec le plus grand reach et durée de diffusion")

        try:
            # Récupérer les meilleures winning ads (utilise le filtre de jours)
            winning_ads = get_winning_ads(db, limit=50, days=days_filter if days_filter > 0 else 30)

            if winning_ads:
                # Créer un DataFrame pour l'affichage
                ads_data = []
                for ad in winning_ads[:20]:
                    # Formater le reach
                    reach = ad.get("eu_total_reach", 0) or 0
                    if reach >= 1000000:
                        reach_str = f"{reach/1000000:.1f}M"
                    elif reach >= 1000:
                        reach_str = f"{reach/1000:.0f}K"
                    else:
                        reach_str = str(reach)

                    # Extraire le texte de l'ad
                    bodies = ad.get("ad_creative_bodies", "")
                    if isinstance(bodies, str):
                        try:
                            import json
                            bodies = json.loads(bodies) if bodies.startswith("[") else [bodies]
                        except:
                            bodies = [bodies] if bodies else []
                    ad_text = bodies[0][:80] + "..." if bodies and len(bodies[0]) > 80 else (bodies[0] if bodies else "N/A")

                    # Formater la date
                    date_scan = ad.get("date_scan")
                    date_str = date_scan.strftime("%d/%m/%Y %H:%M") if date_scan else "-"

                    ads_data.append({
                        "Page": ad.get("page_name", "N/A"),
                        "Texte Ad": ad_text,
                        "Reach EU": reach_str,
                        "Âge (jours)": ad.get("ad_age_days", 0),
                        "Date Scan": date_str,
                        "Critères": ad.get("matched_criteria", ""),
                        "Lien": ad.get("ad_snapshot_url", "")
                    })

                df = pd.DataFrame(ads_data)

                col_table, col_export = st.columns([4, 1])
                with col_table:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                with col_export:
                    render_csv_download(df, f"top_winning_ads_{datetime.now().strftime('%Y%m%d')}.csv", "📥 CSV")

                # Bouton pour voir les détails
                with st.expander("📋 Détails des Winning Ads"):
                    for i, ad in enumerate(winning_ads[:10]):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{ad.get('page_name', 'N/A')}**")
                            bodies = ad.get("ad_creative_bodies", "")
                            if isinstance(bodies, str):
                                try:
                                    import json
                                    bodies = json.loads(bodies) if bodies.startswith("[") else [bodies]
                                except:
                                    bodies = [bodies] if bodies else []
                            if bodies:
                                st.caption(bodies[0][:200])
                        with col2:
                            if ad.get("ad_snapshot_url"):
                                st.link_button("👁️ Voir", ad["ad_snapshot_url"], use_container_width=True)
                        st.divider()
            else:
                st.info("Aucune winning ad trouvée")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # ═══ TAB 3: Pages avec le plus de Winning Ads ═══
    with tab3:
        st.subheader("📊 Pages avec le plus de Winning Ads")
        st.caption("Classement des pages par nombre de winning ads")

        try:
            # Récupérer le nombre de winning ads par page (utilise le filtre de jours)
            winning_by_page = get_winning_ads_by_page(db, days=days_filter if days_filter > 0 else 30)

            if winning_by_page:
                # Trier par nombre décroissant
                sorted_pages = sorted(winning_by_page.items(), key=lambda x: x[1], reverse=True)[:30]

                # Récupérer les infos des pages
                pages_data = []
                for page_id, count in sorted_pages:
                    # Chercher les infos de la page
                    page_info = search_pages(db, page_id=page_id, limit=1)
                    if page_info:
                        p = page_info[0]
                        # Formater la date
                        dernier_scan = p.get("dernier_scan")
                        date_str = dernier_scan.strftime("%d/%m/%Y") if dernier_scan else "-"

                        pages_data.append({
                            "Page": p.get("page_name", "N/A"),
                            "Site": p.get("lien_site", ""),
                            "Winning Ads": count,
                            "Ads Actives": p.get("nombre_ads_active", 0),
                            "Dernier Scan": date_str,
                            "CMS": p.get("cms", "N/A"),
                            "État": p.get("etat", "N/A"),
                            "Catégorie": p.get("subcategory", ""),
                            "page_id": page_id
                        })
                    else:
                        # Si page pas trouvée, récupérer le nom depuis les winning ads
                        winning = get_winning_ads(db, page_id=page_id, limit=1)
                        page_name = winning[0].get("page_name", page_id) if winning else page_id
                        pages_data.append({
                            "Page": page_name,
                            "Site": "",
                            "Winning Ads": count,
                            "Ads Actives": 0,
                            "Dernier Scan": "-",
                            "CMS": "N/A",
                            "État": "N/A",
                            "Catégorie": "",
                            "page_id": page_id
                        })

                if pages_data:
                    df = pd.DataFrame(pages_data)
                    # Afficher sans le page_id
                    display_cols = ["Page", "Site", "Winning Ads", "Ads Actives", "Dernier Scan", "CMS", "État", "Catégorie"]

                    col_table, col_export = st.columns([4, 1])
                    with col_table:
                        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
                    with col_export:
                        render_csv_download(df[display_cols], f"pages_winning_ranking_{datetime.now().strftime('%Y%m%d')}.csv", "📥 CSV")

                    # Top 3 en métrique
                    st.markdown("##### 🥇 Podium")
                    col1, col2, col3 = st.columns(3)
                    if len(pages_data) >= 1:
                        with col1:
                            st.metric("🥇 1er", pages_data[0]["Page"][:20], f"{pages_data[0]['Winning Ads']} winning ads")
                    if len(pages_data) >= 2:
                        with col2:
                            st.metric("🥈 2ème", pages_data[1]["Page"][:20], f"{pages_data[1]['Winning Ads']} winning ads")
                    if len(pages_data) >= 3:
                        with col3:
                            st.metric("🥉 3ème", pages_data[2]["Page"][:20], f"{pages_data[2]['Winning Ads']} winning ads")
            else:
                st.info("Aucune winning ad enregistrée")
        except Exception as e:
            st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_alerts():
    """Page Alerts - Alertes et notifications"""
    st.title("🔔 Alerts")
    st.markdown("Alertes et changements détectés automatiquement")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Filtres de classification
    st.markdown("#### 🔍 Filtres")
    filters = render_classification_filters(db, key_prefix="alerts", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if filters.get("thematique"):
        active_filters.append(f"🏷️ {filters['thematique']}")
    if filters.get("subcategory"):
        active_filters.append(f"📂 {filters['subcategory']}")
    if filters.get("pays"):
        active_filters.append(f"🌍 {filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' • '.join(active_filters)}")

    st.markdown("---")

    try:
        alerts = generate_alerts(
            db,
            thematique=filters.get("thematique"),
            subcategory=filters.get("subcategory"),
            pays=filters.get("pays")
        )

        if alerts:
            st.success(f"📬 {len(alerts)} alerte(s) active(s)")

            for alert in alerts:
                if alert["type"] == "success":
                    with st.expander(f"✅ {alert['icon']} {alert['title']}", expanded=True):
                        st.success(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    change = item.get("change", "")
                                    if change:
                                        st.write(f"  • {name} ({change})")
                                    else:
                                        st.write(f"  • {name}")

                elif alert["type"] == "warning":
                    with st.expander(f"⚠️ {alert['icon']} {alert['title']}", expanded=True):
                        st.warning(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    delta = item.get("pct_ads", 0)
                                    change = item.get("change", "")
                                    if change:
                                        st.write(f"  • {name} ({change})")
                                    else:
                                        st.write(f"  • {name} ({delta:+.0f}%)")

                else:
                    with st.expander(f"ℹ️ {alert['icon']} {alert['title']}", expanded=True):
                        st.info(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    delta = item.get("pct_ads", 0)
                                    ads = item.get("ads_actuel", 0)
                                    if delta:
                                        st.write(f"  • {name} ({delta:+.0f}%, {ads} ads)")
                                    else:
                                        st.write(f"  • {name}")

                st.markdown("")
        else:
            st.info("🔕 Aucune alerte pour le moment")
            st.caption("Les alertes sont générées automatiquement lors des scans")

        # Section détection manuelle
        st.markdown("---")
        st.subheader("🔍 Détection manuelle")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📈 Rechercher pages en croissance", width="stretch"):
                trends = detect_trends(db, days=7)
                if trends["rising"]:
                    st.success(f"{len(trends['rising'])} page(s) en forte croissance")
                    for t in trends["rising"]:
                        st.write(f"🚀 **{t['nom_site']}** +{t['pct_ads']:.0f}%")
                else:
                    st.info("Aucune page en forte croissance")

        with col2:
            if st.button("📉 Rechercher pages en déclin", width="stretch"):
                trends = detect_trends(db, days=7)
                if trends["falling"]:
                    st.warning(f"{len(trends['falling'])} page(s) en déclin")
                    for t in trends["falling"]:
                        st.write(f"⚠️ **{t['nom_site']}** {t['pct_ads']:.0f}%")
                else:
                    st.info("Aucune page en déclin détectée")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

def render_monitoring():
    """Page Monitoring - Suivi historique et évolution"""
    st.title("📈 Monitoring")
    st.markdown("Suivi de l'évolution des pages depuis le dernier scan")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Sélecteur de période
    col1, col2 = st.columns([1, 3])
    with col1:
        period = st.selectbox(
            "📅 Période",
            options=[7, 14, 30],
            format_func=lambda x: f"1 semaine" if x == 7 else f"2 semaines" if x == 14 else "1 mois",
            index=0
        )

    # Section évolution
    st.subheader("📊 Évolution depuis le dernier scan")

    try:
        evolution = get_evolution_stats(db, period_days=period)

        if evolution:
            st.info(f"📈 {len(evolution)} pages avec évolution sur les {period} derniers jours")

            # Métriques globales
            total_up = sum(1 for e in evolution if e["delta_ads"] > 0)
            total_down = sum(1 for e in evolution if e["delta_ads"] < 0)
            total_stable = sum(1 for e in evolution if e["delta_ads"] == 0)

            col1, col2, col3 = st.columns(3)
            col1.metric("📈 En hausse", total_up)
            col2.metric("📉 En baisse", total_down)
            col3.metric("➡️ Stable", total_stable)

            # Tableau d'évolution
            st.markdown("---")

            for evo in evolution[:20]:  # Top 20
                delta_color = "green" if evo["delta_ads"] > 0 else "red" if evo["delta_ads"] < 0 else "gray"
                delta_icon = "📈" if evo["delta_ads"] > 0 else "📉" if evo["delta_ads"] < 0 else "➡️"

                with st.expander(f"{delta_icon} **{evo['nom_site']}** - {evo['delta_ads']:+d} ads ({evo['pct_ads']:+.1f}%)"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric(
                            "Ads actives",
                            evo["ads_actuel"],
                            delta=f"{evo['delta_ads']:+d}",
                            delta_color="normal" if evo["delta_ads"] >= 0 else "inverse"
                        )

                    with col2:
                        st.metric(
                            "Produits",
                            evo["produits_actuel"],
                            delta=f"{evo['delta_produits']:+d}" if evo["delta_produits"] != 0 else None
                        )

                    with col3:
                        st.metric("Durée entre scans", f"{evo['duree_jours']:.1f} jours")

                    # Dates des scans
                    st.caption(f"🕐 Scan actuel: {evo['date_actuel'].strftime('%Y-%m-%d %H:%M') if evo['date_actuel'] else 'N/A'}")
                    st.caption(f"🕐 Scan précédent: {evo['date_precedent'].strftime('%Y-%m-%d %H:%M') if evo['date_precedent'] else 'N/A'}")

                    # Bouton pour voir l'historique complet
                    if st.button(f"Voir historique complet", key=f"hist_{evo['page_id']}"):
                        st.session_state.monitoring_page_id = evo["page_id"]
                        st.rerun()
        else:
            st.info("Aucune évolution détectée. Effectuez plusieurs scans pour voir les changements.")
    except Exception as e:
        st.error(f"Erreur: {e}")

    st.markdown("---")

    # Section historique d'une page spécifique
    st.subheader("🔍 Historique d'une page")

    # Récupérer page_id depuis session ou input
    default_page_id = st.session_state.get("monitoring_page_id", "")
    page_id = st.text_input("Entrer un Page ID", value=default_page_id)

    if page_id:
        try:
            history = get_page_evolution_history(db, page_id=page_id, limit=50)

            if history and len(history) > 0:
                st.success(f"📊 {len(history)} scans trouvés")

                # Graphique d'évolution amélioré
                if len(history) > 1:
                    chart_header(
                        "📈 Évolution dans le temps",
                        "Suivi du nombre d'annonces et de produits",
                        "La ligne pointillée indique la tendance générale"
                    )

                    dates = [h["date_scan"] for h in history]
                    ads_values = [h["nombre_ads_active"] for h in history]
                    products_values = [h["nombre_produits"] for h in history]

                    fig = create_trend_chart(
                        dates=dates,
                        values=ads_values,
                        value_name="Ads actives",
                        color=CHART_COLORS["primary"],
                        secondary_values=products_values,
                        secondary_name="Produits",
                        show_trend=True,
                        height=350
                    )
                    st.plotly_chart(fig, key="monitoring_page_chart", width="stretch")

                # Tableau avec deltas
                df_data = []
                for h in history:
                    delta_ads_str = f"{h['delta_ads']:+d}" if h["delta_ads"] != 0 else "-"
                    delta_prod_str = f"{h['delta_produits']:+d}" if h["delta_produits"] != 0 else "-"
                    df_data.append({
                        "Date": h["date_scan"].strftime("%Y-%m-%d %H:%M") if h["date_scan"] else "",
                        "Ads": h["nombre_ads_active"],
                        "Δ Ads": delta_ads_str,
                        "Produits": h["nombre_produits"],
                        "Δ Produits": delta_prod_str
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info("Aucun historique trouvé pour cette page")
        except Exception as e:
            st.error(f"Erreur: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARAISON DE PAGES
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("⚖️ Comparer des pages")
    st.caption("Comparez jusqu'à 3 pages côte à côte")

    col1, col2, col3 = st.columns(3)

    with col1:
        page1_id = st.text_input("Page 1", placeholder="Page ID", key="compare_page1")
    with col2:
        page2_id = st.text_input("Page 2", placeholder="Page ID", key="compare_page2")
    with col3:
        page3_id = st.text_input("Page 3 (optionnel)", placeholder="Page ID", key="compare_page3")

    if st.button("🔄 Comparer", type="primary", key="compare_btn"):
        pages_to_compare = [p for p in [page1_id, page2_id, page3_id] if p]

        if len(pages_to_compare) >= 2:
            comparison_data = []

            for pid in pages_to_compare:
                page_results = search_pages(db, search_term=pid, limit=1)
                if page_results:
                    page = page_results[0]
                    # Récupérer l'historique
                    history = get_page_evolution_history(db, page_id=pid, limit=10)
                    avg_ads = sum(h["nombre_ads_active"] for h in history) / len(history) if history else 0
                    trend = "📈" if history and len(history) > 1 and history[0]["delta_ads"] > 0 else "📉" if history and len(history) > 1 and history[0]["delta_ads"] < 0 else "➡️"

                    # Winning ads count
                    winning = get_winning_ads(db, page_id=pid, limit=100)
                    winning_count = len(winning) if winning else 0

                    comparison_data.append({
                        "Page ID": pid,
                        "Nom": page.get("page_name", "N/A")[:25],
                        "CMS": page.get("cms", "N/A"),
                        "État": page.get("etat", "N/A"),
                        "Ads actives": page.get("nombre_ads_active", 0),
                        "Produits": page.get("nombre_produits", 0),
                        "Winning Ads": winning_count,
                        "Moy. Ads": f"{avg_ads:.0f}",
                        "Tendance": trend
                    })
                else:
                    comparison_data.append({
                        "Page ID": pid,
                        "Nom": "Non trouvée",
                        "CMS": "-",
                        "État": "-",
                        "Ads actives": 0,
                        "Produits": 0,
                        "Winning Ads": 0,
                        "Moy. Ads": "-",
                        "Tendance": "-"
                    })

            # Afficher la comparaison
            st.markdown("##### 📊 Résultat de la comparaison")
            df_compare = pd.DataFrame(comparison_data)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)

            # Graphique de comparaison
            if any(d["Ads actives"] > 0 for d in comparison_data):
                fig = go.Figure(data=[
                    go.Bar(name='Ads actives', x=[d["Nom"] for d in comparison_data], y=[d["Ads actives"] for d in comparison_data], marker_color=CHART_COLORS["primary"]),
                    go.Bar(name='Winning Ads', x=[d["Nom"] for d in comparison_data], y=[d["Winning Ads"] for d in comparison_data], marker_color=CHART_COLORS["success"])
                ])
                fig.update_layout(
                    barmode='group',
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True, key="compare_chart")
        else:
            st.warning("Entrez au moins 2 Page IDs pour comparer")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def render_analytics():
    """Page Analytics - Analyses avancées"""
    st.title("📊 Analytics")
    st.markdown("Analyses et statistiques avancées")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    try:
        stats = get_suivi_stats(db)

        # Info card
        info_card(
            "Que signifient ces statistiques ?",
            """
            Cette page vous donne une vue d'ensemble de votre base de données de pages publicitaires.<br><br>
            • <b>Distribution par État</b> : Montre combien de pages sont dans chaque catégorie d'activité<br>
            • <b>Distribution par CMS</b> : Les plateformes e-commerce utilisées (Shopify domine le marché)<br>
            • <b>Thématiques</b> : Les niches/secteurs les plus représentés dans votre base
            """,
            "📚"
        )

        # Stats générales
        col1, col2, col3, col4 = st.columns(4)

        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})
        total_pages = stats.get("total_pages", 0)
        actives = sum(v for k, v in etats.items() if k != "inactif")

        col1.metric("📄 Total Pages", f"{total_pages:,}")
        col2.metric("✅ Pages Actives", f"{actives:,}")
        col3.metric("🛒 CMS Différents", len(cms_stats))

        # Taux d'activité
        taux_actif = (actives / total_pages * 100) if total_pages > 0 else 0
        col4.metric("📈 Taux d'activité", f"{taux_actif:.1f}%")

        st.markdown("---")

        # Graphiques côte à côte
        col1, col2 = st.columns(2)

        with col1:
            chart_header(
                "📊 Distribution par État",
                "Nombre de pages par niveau d'activité",
                "Plus une page a d'ads actives, plus elle est probablement performante"
            )
            if etats:
                # Ordonner les états
                ordre_etats = ["XXL", "XL", "L", "M", "S", "XS", "inactif"]
                etats_ordonne = [(k, etats.get(k, 0)) for k in ordre_etats if etats.get(k, 0) > 0]

                labels = [e[0] for e in etats_ordonne]
                values = [e[1] for e in etats_ordonne]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    value_suffix=" pages",
                    height=300
                )
                st.plotly_chart(fig, key="analytics_states", width="stretch")
            else:
                st.info("Aucune donnée disponible")

        with col2:
            chart_header(
                "🛒 Distribution par CMS",
                "Plateformes e-commerce utilisées",
                "Shopify est le leader du marché dropshipping"
            )
            if cms_stats:
                # Trier par valeur décroissante
                sorted_cms = sorted(cms_stats.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_cms]
                values = [c[1] for c in sorted_cms]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    value_suffix=" sites",
                    height=300
                )
                st.plotly_chart(fig, key="analytics_cms", width="stretch")
            else:
                st.info("Aucune donnée disponible")

        # Top thématiques
        st.markdown("---")
        chart_header(
            "🏷️ Analyse par thématique",
            "Répartition des pages selon leur niche/secteur",
            "Identifiez les marchés les plus compétitifs"
        )

        all_pages = search_pages(db, limit=500)
        if all_pages:
            themes = {}
            for p in all_pages:
                theme = p.get("thematique", "Non classé") or "Non classé"
                themes[theme] = themes.get(theme, 0) + 1

            if themes:
                # Trier et prendre top 10
                sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:10]
                labels = [t[0] for t in sorted_themes]
                values = [t[1] for t in sorted_themes]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    colors=[CHART_COLORS["info"]] * len(labels),
                    value_suffix=" pages",
                    height=350
                )
                st.plotly_chart(fig, key="analytics_themes", width="stretch")
        else:
            st.info("Aucune donnée disponible")

        # ═══════════════════════════════════════════════════════════════════════════
        # GRAPHIQUES D'ÉVOLUTION
        # ═══════════════════════════════════════════════════════════════════════════
        st.markdown("---")
        chart_header(
            "📈 Évolution temporelle",
            "Historique des scans et tendances",
            "Suivez l'évolution de votre base de données au fil du temps"
        )

        # Récupérer les données de suivi pour les graphiques
        from app.database import SuiviPage
        from sqlalchemy import func

        with db.get_session() as session:
            # Données agrégées par jour
            daily_stats = session.query(
                func.date(SuiviPage.date_scan).label('date'),
                func.count(func.distinct(SuiviPage.page_id)).label('pages_scanned'),
                func.avg(SuiviPage.nombre_ads_active).label('avg_ads'),
                func.sum(SuiviPage.nombre_ads_active).label('total_ads')
            ).group_by(
                func.date(SuiviPage.date_scan)
            ).order_by(
                func.date(SuiviPage.date_scan)
            ).limit(60).all()

        if daily_stats:
            df_evolution = pd.DataFrame([
                {
                    "Date": row.date,
                    "Pages scannées": row.pages_scanned,
                    "Ads moyennes": round(row.avg_ads or 0, 1),
                    "Total ads": row.total_ads or 0
                }
                for row in daily_stats
            ])

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### 📊 Pages scannées par jour")
                fig1 = px.area(
                    df_evolution,
                    x="Date",
                    y="Pages scannées",
                    color_discrete_sequence=[CHART_COLORS["primary"]]
                )
                fig1.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                )
                st.plotly_chart(fig1, key="evolution_pages", use_container_width=True)

            with col2:
                st.markdown("##### 📈 Moyenne d'ads actives")
                fig2 = px.line(
                    df_evolution,
                    x="Date",
                    y="Ads moyennes",
                    color_discrete_sequence=[CHART_COLORS["success"]]
                )
                fig2.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                )
                fig2.update_traces(line=dict(width=3))
                st.plotly_chart(fig2, key="evolution_ads", use_container_width=True)

            # Export CSV
            render_csv_download(df_evolution, f"evolution_stats_{datetime.now().strftime('%Y%m%d')}.csv", "📥 Export données évolution")
        else:
            st.info("Pas assez de données pour afficher l'évolution")

        # ═══ ÉVOLUTION D'UNE PAGE SPÉCIFIQUE ═══
        st.markdown("---")
        st.markdown("##### 🔍 Évolution d'une page spécifique")

        page_id_input = st.text_input("Entrez un Page ID", placeholder="Ex: 123456789", key="evolution_page_id")

        if page_id_input:
            page_history = get_page_evolution_history(db, page_id_input, limit=30)

            if page_history:
                df_page = pd.DataFrame(page_history)
                df_page["Date"] = pd.to_datetime(df_page["date_scan"]).dt.strftime("%d/%m")

                col1, col2 = st.columns(2)

                with col1:
                    fig_ads = px.bar(
                        df_page,
                        x="Date",
                        y="nombre_ads_active",
                        title="📊 Évolution des Ads actives",
                        color_discrete_sequence=[CHART_COLORS["primary"]]
                    )
                    fig_ads.update_layout(
                        height=300,
                        margin=dict(l=20, r=20, t=40, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_ads, key="page_ads_evolution", use_container_width=True)

                with col2:
                    fig_prod = px.bar(
                        df_page,
                        x="Date",
                        y="nombre_produits",
                        title="📦 Évolution des Produits",
                        color_discrete_sequence=[CHART_COLORS["success"]]
                    )
                    fig_prod.update_layout(
                        height=300,
                        margin=dict(l=20, r=20, t=40, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_prod, key="page_prod_evolution", use_container_width=True)

                # Tableau des deltas
                st.dataframe(
                    df_page[["Date", "nombre_ads_active", "delta_ads", "nombre_produits", "delta_produits"]].rename(columns={
                        "nombre_ads_active": "Ads",
                        "delta_ads": "Δ Ads",
                        "nombre_produits": "Produits",
                        "delta_produits": "Δ Produits"
                    }),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.warning(f"Aucun historique trouvé pour la page {page_id_input}")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: WINNING ADS
# ═══════════════════════════════════════════════════════════════════════════════

def render_winning_ads():
    """Page Winning Ads - Annonces performantes détectées"""
    st.title("🏆 Winning Ads")
    st.markdown("Annonces performantes basées sur reach + âge")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Critères expliqués
    with st.expander("ℹ️ Critères de détection des Winning Ads", expanded=False):
        st.markdown("""
        Une annonce est considérée comme **winning** si elle valide **au moins un** de ces critères :

        | Âge max | Reach min |
        |---------|-----------|
        | ≤4 jours | >15 000 |
        | ≤5 jours | >20 000 |
        | ≤6 jours | >30 000 |
        | ≤7 jours | >40 000 |
        | ≤8 jours | >50 000 |
        | ≤15 jours | >100 000 |
        | ≤22 jours | >200 000 |
        | ≤29 jours | >400 000 |

        Plus une annonce est récente avec un reach élevé, plus elle est performante.
        """)

    # Filtres de classification
    st.markdown("#### 🔍 Filtres")
    class_filters = render_classification_filters(db, key_prefix="winning", columns=3)

    # Afficher les filtres actifs
    active_filters = []
    if class_filters.get("thematique"):
        active_filters.append(f"🏷️ {class_filters['thematique']}")
    if class_filters.get("subcategory"):
        active_filters.append(f"📂 {class_filters['subcategory']}")
    if class_filters.get("pays"):
        active_filters.append(f"🌍 {class_filters['pays']}")

    if active_filters:
        st.caption(f"Filtres actifs: {' • '.join(active_filters)}")

    st.markdown("---")

    # Filtres existants
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        period = st.selectbox(
            "📅 Période",
            options=[7, 14, 30, 60, 90],
            format_func=lambda x: f"{x} jours",
            index=2
        )

    with col2:
        limit_options = [50, 100, 200, 500, 1000, 0]  # 0 = Toutes
        limit = st.selectbox(
            "Limite",
            limit_options,
            format_func=lambda x: "Toutes" if x == 0 else str(x),
            index=1
        )

    with col3:
        sort_by = st.selectbox(
            "Trier par",
            options=["Reach", "Date de scan", "Âge de l'ad"],
            index=0
        )

    with col4:
        group_by = st.selectbox(
            "Grouper par",
            options=["Aucun", "Par Page", "Par Âge"],
            index=0,
            help="Grouper les winning ads par page ou par âge"
        )

    try:
        # Statistiques globales (avec filtres si actifs)
        if any(class_filters.values()):
            stats = get_winning_ads_stats_filtered(
                db, days=period,
                thematique=class_filters.get("thematique"),
                subcategory=class_filters.get("subcategory"),
                pays=class_filters.get("pays")
            )
        else:
            stats = get_winning_ads_stats(db, days=period)

        st.markdown("---")
        st.subheader("📊 Statistiques")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏆 Total Winning Ads", stats.get("total", 0))
        col2.metric("📄 Pages avec Winning", stats.get("unique_pages", 0))
        col3.metric("📈 Reach moyen", f"{stats.get('avg_reach', 0):,}".replace(",", " "))

        # Critères les plus fréquents
        by_criteria = stats.get("by_criteria", {})
        if by_criteria:
            top_criteria = max(by_criteria.items(), key=lambda x: x[1]) if by_criteria else ("N/A", 0)
            col4.metric("🎯 Critère top", top_criteria[0])

        # Graphique par critère
        if by_criteria:
            st.markdown("---")

            # Info card
            info_card(
                "Comprendre les critères de Winning Ads",
                """
                Chaque critère représente une combinaison âge/reach :<br>
                • <b>≤4j >15k</b> : Ad de moins de 4 jours avec plus de 15 000 personnes touchées<br>
                • Plus le ratio reach/âge est élevé, plus l'ad est performante<br>
                • Une ad qui touche beaucoup de monde rapidement indique un bon produit/créative
                """,
                "🎯"
            )

            col1, col2 = st.columns(2)

            with col1:
                chart_header(
                    "📊 Répartition par critère",
                    "Quels seuils sont les plus atteints",
                    "Le critère le plus fréquent indique le niveau de performance moyen"
                )
                # Trier par valeur
                sorted_criteria = sorted(by_criteria.items(), key=lambda x: x[1], reverse=True)
                labels = [c[0] for c in sorted_criteria]
                values = [c[1] for c in sorted_criteria]

                fig = create_horizontal_bar_chart(
                    labels=labels,
                    values=values,
                    colors=[CHART_COLORS["success"]] * len(labels),
                    value_suffix=" ads",
                    height=280
                )
                st.plotly_chart(fig, key="winning_by_criteria", width="stretch")

            with col2:
                chart_header(
                    "🏆 Top Pages avec Winning Ads",
                    "Pages ayant le plus d'annonces performantes",
                    "Ces pages ont probablement trouvé des produits/créatives gagnants"
                )
                by_page = stats.get("by_page", [])
                if by_page:
                    df_pages = pd.DataFrame(by_page)
                    df_pages.columns = ["Page ID", "Nom", "Winning Ads"]
                    st.dataframe(df_pages, width="stretch", hide_index=True)
                else:
                    st.info("Aucune page avec winning ads")

        # Liste des winning ads
        st.markdown("---")

        # limit=0 signifie "Toutes" -> on utilise une très grande limite
        actual_limit = limit if limit > 0 else 100000

        # Utiliser la fonction filtrée si des filtres sont actifs
        if any(class_filters.values()):
            winning_ads = get_winning_ads_filtered(
                db, limit=actual_limit, days=period,
                thematique=class_filters.get("thematique"),
                subcategory=class_filters.get("subcategory"),
                pays=class_filters.get("pays")
            )
        else:
            winning_ads = get_winning_ads(db, limit=actual_limit, days=period)

        if winning_ads:
            # Header avec export personnalisé
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("📋 Liste des Winning Ads")
            with col2:
                # Colonnes disponibles pour export
                all_winning_columns = {
                    "Page": lambda ad: ad.get("page_name", ""),
                    "Page ID": lambda ad: ad.get("page_id", ""),
                    "Ad ID": lambda ad: ad.get("ad_id", ""),
                    "Reach": lambda ad: ad.get("eu_total_reach", 0),
                    "Âge (jours)": lambda ad: ad.get("ad_age_days", 0),
                    "Critère": lambda ad: ad.get("matched_criteria", ""),
                    "Texte Ad": lambda ad: (ad.get("ad_creative_bodies", "") or "")[:200],
                    "Site": lambda ad: ad.get("lien_site", ""),
                    "CMS": lambda ad: ad.get("cms", ""),
                    "URL Ad": lambda ad: ad.get("ad_snapshot_url", ""),
                    "Date scan": lambda ad: ad.get("date_scan").strftime("%Y-%m-%d") if ad.get("date_scan") else "",
                    "Page Facebook": lambda ad: f"https://www.facebook.com/{ad.get('page_id', '')}",
                    "Ad Library": lambda ad: f"https://www.facebook.com/ads/library/?id={ad.get('ad_id', '')}"
                }

                default_winning_cols = ["Page", "Ad ID", "Reach", "Âge (jours)", "Critère", "Site"]

                with st.popover("📥 Export CSV"):
                    st.markdown("**Colonnes à exporter:**")
                    selected_winning_cols = st.multiselect(
                        "Colonnes",
                        options=list(all_winning_columns.keys()),
                        default=default_winning_cols,
                        key="export_columns_winning",
                        label_visibility="collapsed"
                    )

                    # Présets
                    col_w1, col_w2 = st.columns(2)
                    with col_w1:
                        if st.button("📋 Essentiel", key="preset_win_ess", width="stretch"):
                            st.session_state.export_columns_winning = ["Page", "Ad ID", "Reach", "Critère"]
                            st.rerun()
                    with col_w2:
                        if st.button("📊 Complet", key="preset_win_full", width="stretch"):
                            st.session_state.export_columns_winning = list(all_winning_columns.keys())
                            st.rerun()

                    if selected_winning_cols:
                        export_data = []
                        for ad in winning_ads:
                            row = {col: all_winning_columns[col](ad) for col in selected_winning_cols}
                            export_data.append(row)

                        csv_data = export_to_csv(export_data)
                        group_suffix = f"_{group_by.lower().replace(' ', '_')}" if group_by != "Aucun" else ""
                        st.download_button(
                            f"📥 Télécharger ({len(selected_winning_cols)} col.)",
                            csv_data,
                            f"winning_ads_{period}j{group_suffix}.csv",
                            "text/csv",
                            key="export_winning",
                            width="stretch"
                        )
                    else:
                        st.warning("Sélectionnez au moins une colonne")

            group_info = f" (groupé: {group_by})" if group_by != "Aucun" else ""
            st.info(f"🏆 {len(winning_ads)} winning ads trouvées{group_info}")

            # ═══ AFFICHAGE GROUPÉ ═══
            if group_by == "Par Page":
                # Grouper par page
                groups = {}
                for ad in winning_ads:
                    page_name = ad.get('page_name', 'N/A')
                    page_id = ad.get('page_id', '')
                    key = f"{page_name}||{page_id}"
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(ad)

                # Trier les groupes par nombre d'ads (décroissant)
                sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

                for group_key, ads in sorted_groups:
                    page_name, page_id = group_key.split("||")
                    total_reach = sum(ad.get('eu_total_reach', 0) or 0 for ad in ads)

                    with st.expander(f"📄 **{page_name}** - {len(ads)} winning ads (Total reach: {total_reach:,}".replace(",", " ") + ")"):
                        # Tableau des ads de cette page
                        table_data = []
                        for ad in sorted(ads, key=lambda x: x.get('eu_total_reach', 0) or 0, reverse=True):
                            reach_val = ad.get('eu_total_reach', 0) or 0
                            table_data.append({
                                "Ad ID": ad.get('ad_id', '')[:15],
                                "Reach": f"{reach_val:,}".replace(",", " "),
                                "Âge (j)": ad.get('ad_age_days', 0) or 0,
                                "Critère": ad.get('matched_criteria', 'N/A'),
                                "Texte": (ad.get('ad_creative_bodies', '') or '')[:60] + "...",
                                "Ad URL": ad.get('ad_snapshot_url', '')
                            })
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, width="stretch", hide_index=True,
                                   column_config={"Ad URL": st.column_config.LinkColumn("Voir")})

                        # Lien vers le site
                        site = ads[0].get('lien_site', '')
                        if site:
                            st.link_button("🌐 Voir le site", site)
                        st.code(page_id, language=None)

            elif group_by == "Par Âge":
                # Grouper par tranches d'âge
                age_ranges = [
                    (0, 4, "0-4 jours (très récent)"),
                    (5, 7, "5-7 jours"),
                    (8, 14, "8-14 jours"),
                    (15, 21, "15-21 jours"),
                    (22, 30, "22-30 jours"),
                    (31, 999, "30+ jours")
                ]

                groups = {label: [] for _, _, label in age_ranges}

                for ad in winning_ads:
                    age = ad.get('ad_age_days', 0) or 0
                    for min_age, max_age, label in age_ranges:
                        if min_age <= age <= max_age:
                            groups[label].append(ad)
                            break

                for _, _, label in age_ranges:
                    ads = groups[label]
                    if not ads:
                        continue

                    total_reach = sum(ad.get('eu_total_reach', 0) or 0 for ad in ads)
                    avg_reach = total_reach // len(ads) if ads else 0

                    with st.expander(f"📅 **{label}** - {len(ads)} ads (Reach moyen: {avg_reach:,}".replace(",", " ") + ")"):
                        table_data = []
                        for ad in sorted(ads, key=lambda x: x.get('eu_total_reach', 0) or 0, reverse=True):
                            reach_val = ad.get('eu_total_reach', 0) or 0
                            table_data.append({
                                "Page": ad.get('page_name', 'N/A')[:30],
                                "Reach": f"{reach_val:,}".replace(",", " "),
                                "Âge": f"{ad.get('ad_age_days', 0)}j",
                                "Critère": ad.get('matched_criteria', 'N/A'),
                                "Site": ad.get('lien_site', ''),
                                "Ad URL": ad.get('ad_snapshot_url', '')
                            })
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, width="stretch", hide_index=True,
                                   column_config={
                                       "Site": st.column_config.LinkColumn("Site"),
                                       "Ad URL": st.column_config.LinkColumn("Voir")
                                   }, height=min(400, 50 + len(ads) * 35))

            # ═══ AFFICHAGE NORMAL (pas de groupement) - Tableau ═══
            else:
                table_data = []
                for ad in winning_ads:
                    reach_val = ad.get('eu_total_reach', 0) or 0
                    table_data.append({
                        "Page": ad.get('page_name', 'N/A')[:40],
                        "Reach": f"{reach_val:,}".replace(",", " "),
                        "Âge (j)": ad.get('ad_age_days', 0) or 0,
                        "Critère": ad.get('matched_criteria', 'N/A'),
                        "Texte": (ad.get('ad_creative_bodies', '') or '')[:80] + "..." if len(ad.get('ad_creative_bodies', '') or '') > 80 else (ad.get('ad_creative_bodies', '') or ''),
                        "Site": ad.get('lien_site', ''),
                        "Ad URL": ad.get('ad_snapshot_url', ''),
                        "Page ID": ad.get('page_id', ''),
                        "Ad ID": ad.get('ad_id', ''),
                        "Scan": ad.get('date_scan').strftime('%Y-%m-%d') if ad.get('date_scan') else ''
                    })

                df_winning = pd.DataFrame(table_data)

                # Configuration des colonnes pour les liens cliquables
                column_config = {
                    "Site": st.column_config.LinkColumn("Site"),
                    "Ad URL": st.column_config.LinkColumn("Voir Ad"),
                }

                st.dataframe(
                    df_winning,
                    width="stretch",
                    hide_index=True,
                    column_config=column_config,
                    height=600
                )

        else:
            st.info("Aucune winning ad trouvée pour cette période. Lancez une recherche pour en détecter.")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════

def render_blacklist():
    """Page Blacklist - Gestion des pages blacklistées"""
    st.title("🚫 Blacklist")
    st.markdown("Gérer les pages exclues des recherches")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Formulaire d'ajout
    st.subheader("➕ Ajouter une page")
    with st.form("add_blacklist_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_page_id = st.text_input("Page ID *", placeholder="123456789")
        with col2:
            new_page_name = st.text_input("Nom de la page", placeholder="Nom optionnel")

        new_raison = st.text_input("Raison", placeholder="Raison du blacklistage")

        submitted = st.form_submit_button("➕ Ajouter à la blacklist", type="primary")

        if submitted:
            if new_page_id:
                if add_to_blacklist(db, new_page_id.strip(), new_page_name.strip(), new_raison.strip()):
                    st.success(f"✓ Page {new_page_id} ajoutée à la blacklist")
                    st.rerun()
                else:
                    st.warning("Cette page est déjà dans la blacklist")
            else:
                st.error("Page ID requis")

    st.markdown("---")

    # Liste des pages blacklistées
    st.subheader("📋 Pages en blacklist")

    try:
        blacklist = get_blacklist(db)

        if blacklist:
            # Barre de recherche
            search_bl = st.text_input("🔍 Rechercher", placeholder="Filtrer par ID ou nom...")

            # Filtrer si recherche
            if search_bl:
                search_lower = search_bl.lower()
                blacklist = [
                    entry for entry in blacklist
                    if search_lower in str(entry.get("page_id", "")).lower()
                    or search_lower in str(entry.get("page_name", "")).lower()
                ]

            st.info(f"🚫 {len(blacklist)} pages en blacklist")

            # Affichage en tableau avec actions
            for entry in blacklist:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                    with col1:
                        st.write(f"**{entry.get('page_name') or 'Sans nom'}**")
                        st.caption(f"ID: `{entry['page_id']}`")

                    with col2:
                        if entry.get('raison'):
                            st.write(f"📝 {entry['raison']}")
                        else:
                            st.caption("Pas de raison")

                    with col3:
                        if entry.get('added_at'):
                            st.write(f"📅 {entry['added_at'].strftime('%Y-%m-%d %H:%M')}")

                    with col4:
                        if st.button("🗑️ Retirer", key=f"remove_bl_{entry['page_id']}", help="Retirer de la blacklist"):
                            if remove_from_blacklist(db, entry['page_id']):
                                st.success("✓ Retiré de la blacklist")
                                st.rerun()

                    st.markdown("---")
        else:
            st.info("Aucune page en blacklist")

        # Statistiques
        if blacklist:
            st.subheader("📊 Statistiques")
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total pages blacklistées", len(blacklist))

            with col2:
                # Compter celles avec raison
                with_reason = sum(1 for e in blacklist if e.get("raison"))
                st.metric("Avec raison", with_reason)

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

def render_settings():
    """Page Settings - Paramètres"""
    st.title("⚙️ Settings")
    st.markdown("Configuration de l'application")

    # ═══════════════════════════════════════════════════════════════════════════
    # GESTION DES TOKENS META API
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("🔑 Tokens Meta API")
    st.markdown("Gérez vos tokens Meta API pour la rotation automatique anti-ban.")

    db = get_database()

    if db:
        from app.database import (
            get_all_meta_tokens, add_meta_token, delete_meta_token,
            update_meta_token, reset_token_stats, clear_rate_limit, ensure_tables_exist
        )

        # S'assurer que les tables existent
        ensure_tables_exist(db)

        # Récupérer tous les tokens
        tokens = get_all_meta_tokens(db)

        # Stats globales
        total_tokens = len(tokens)
        active_tokens = len([t for t in tokens if t["is_active"]])
        rate_limited = len([t for t in tokens if t.get("is_rate_limited")])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total tokens", total_tokens)
        col2.metric("Tokens actifs", active_tokens)
        col3.metric("Rate-limited", rate_limited, delta=None if rate_limited == 0 else f"-{rate_limited}", delta_color="inverse")

        # Ajouter un nouveau token
        with st.expander("➕ Ajouter un nouveau token", expanded=len(tokens) == 0):
            new_token_name = st.text_input("Nom du token (optionnel)", placeholder="Token Principal", key="new_token_name")
            new_token_value = st.text_input("Token Meta API", type="password", key="new_token_value",
                                            help="Collez votre token Meta Ads API ici")
            new_proxy_url = st.text_input("Proxy URL (optionnel)", placeholder="http://user:pass@ip:port", key="new_proxy_url",
                                          help="Proxy associé à ce token pour éviter les bans IP")

            if st.button("Ajouter le token", type="primary", key="btn_add_token"):
                if new_token_value and new_token_value.strip():
                    token_id = add_meta_token(
                        db,
                        new_token_value.strip(),
                        new_token_name.strip() or None,
                        new_proxy_url.strip() or None
                    )
                    if token_id:
                        st.success(f"✅ Token ajouté avec succès (ID: {token_id})")
                        st.rerun()
                else:
                    st.error("Veuillez entrer un token valide")

        # Liste des tokens existants
        if tokens:
            st.markdown("##### Tokens configurés")

            for t in tokens:
                status_icon = "🟢" if t["is_active"] and not t.get("is_rate_limited") else "🔴" if t.get("is_rate_limited") else "⚫"
                rate_info = " ⏱️ Rate-limited" if t.get("is_rate_limited") else ""
                proxy_info = " 🌐" if t.get("proxy_url") else ""

                with st.expander(f"{status_icon} **{t['name']}** - {t['token_masked']}{proxy_info}{rate_info}"):
                    # Stats
                    stat_cols = st.columns(4)
                    stat_cols[0].metric("Appels", t["total_calls"])
                    stat_cols[1].metric("Erreurs", t["total_errors"])
                    stat_cols[2].metric("Rate limits", t["rate_limit_hits"])
                    stat_cols[3].metric("Statut", "Actif" if t["is_active"] else "Inactif")

                    # Proxy info
                    current_proxy = t.get("proxy_url") or ""
                    if current_proxy:
                        # Masquer le mot de passe dans l'affichage
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(current_proxy)
                            if parsed.password:
                                masked = current_proxy.replace(parsed.password, "****")
                            else:
                                masked = current_proxy
                        except:
                            masked = current_proxy[:30] + "..."
                        st.caption(f"🌐 Proxy: {masked}")
                    else:
                        st.caption("🌐 Proxy: Non configuré")

                    # Modifier le token
                    new_token_value = st.text_input(
                        "Modifier le token",
                        value="",
                        placeholder="Nouveau token Meta API (laissez vide pour ne pas modifier)",
                        key=f"token_value_{t['id']}",
                        type="password",
                        help="Entrez le nouveau token pour le remplacer"
                    )
                    if st.button("💾 Sauvegarder token", key=f"save_token_{t['id']}"):
                        if new_token_value.strip():
                            update_meta_token(db, t["id"], token_value=new_token_value)
                            st.success("Token mis à jour!")
                            st.rerun()
                        else:
                            st.warning("Veuillez entrer un token valide")

                    # Modifier le proxy
                    new_proxy = st.text_input(
                        "Modifier le proxy",
                        value=current_proxy,
                        placeholder="http://user:pass@ip:port",
                        key=f"proxy_{t['id']}",
                        help="Laissez vide pour supprimer le proxy"
                    )
                    if st.button("💾 Sauvegarder proxy", key=f"save_proxy_{t['id']}"):
                        update_meta_token(db, t["id"], proxy_url=new_proxy)
                        st.success("Proxy mis à jour!")
                        st.rerun()

                    st.markdown("---")

                    # Dernière utilisation
                    if t["last_used_at"]:
                        st.caption(f"📅 Dernière utilisation: {t['last_used_at'].strftime('%d/%m/%Y %H:%M')}")
                    if t["last_error_message"]:
                        st.caption(f"❌ Dernière erreur: {t['last_error_message'][:100]}")
                    if t.get("is_rate_limited") and t["rate_limited_until"]:
                        st.warning(f"⏱️ Rate-limited jusqu'à: {t['rate_limited_until'].strftime('%H:%M:%S')}")

                    # Actions
                    action_cols = st.columns(5)

                    with action_cols[0]:
                        new_active = not t["is_active"]
                        if st.button("🔄 Activer" if not t["is_active"] else "⏸️ Désactiver", key=f"toggle_{t['id']}"):
                            update_meta_token(db, t["id"], is_active=new_active)
                            st.rerun()

                    with action_cols[1]:
                        if st.button("✅ Vérifier", key=f"verify_{t['id']}"):
                            from app.database import verify_meta_token
                            with st.spinner("Vérification..."):
                                result = verify_meta_token(db, t["id"])
                            if result["valid"]:
                                st.success(f"✅ Token valide ({result['response_time_ms']}ms)")
                            else:
                                st.error(f"❌ {result.get('error', 'Erreur inconnue')}")

                    with action_cols[2]:
                        if t.get("is_rate_limited"):
                            if st.button("🔓 Débloquer", key=f"unblock_{t['id']}"):
                                clear_rate_limit(db, t["id"])
                                st.rerun()

                    with action_cols[3]:
                        if st.button("📊 Reset stats", key=f"reset_{t['id']}"):
                            reset_token_stats(db, t["id"])
                            st.rerun()

                    with action_cols[4]:
                        if st.button("🗑️ Supprimer", key=f"delete_{t['id']}"):
                            delete_meta_token(db, t["id"])
                            st.success("Token supprimé")
                            st.rerun()
        else:
            st.info("Aucun token configuré. Ajoutez votre premier token Meta API ci-dessus.")

            # Migration depuis variable d'environnement
            env_token = os.getenv("META_ACCESS_TOKEN", "")
            if env_token:
                st.markdown("---")
                st.markdown("**💡 Token trouvé dans les variables d'environnement**")
                if st.button("Importer depuis META_ACCESS_TOKEN", key="import_env_token"):
                    add_meta_token(db, env_token, "Token Principal (importé)")
                    st.success("Token importé avec succès!")
                    st.rerun()

    else:
        st.warning("Base de données non connectée. Configurez la connexion pour gérer les tokens.")
        # Fallback sur l'ancien système
        token = st.text_input(
            "Meta API Token (fallback)",
            type="password",
            value=os.getenv("META_ACCESS_TOKEN", ""),
            help="Token d'accès Meta Ads API"
        )
        if token:
            st.success("✓ Token configuré")
        else:
            st.warning("⚠️ Token non configuré")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════════
    # LOGS D'UTILISATION DES TOKENS
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📋 Logs d'utilisation des Tokens")
    st.markdown("Historique détaillé de l'utilisation de chaque token Meta API")

    if db:
        from app.database import get_token_usage_logs, get_token_stats_detailed, verify_all_tokens

        # Filtres
        log_filter_cols = st.columns([2, 2, 2, 2])

        with log_filter_cols[0]:
            tokens = get_all_meta_tokens(db)
            token_options = {"all": "Tous les tokens"}
            for t in tokens:
                token_options[str(t["id"])] = f"{t['name']}"
            selected_token_filter = st.selectbox(
                "Token",
                options=list(token_options.keys()),
                format_func=lambda x: token_options[x],
                key="log_token_filter"
            )

        with log_filter_cols[1]:
            action_types = {
                "all": "Toutes les actions",
                "search": "🔍 Recherches",
                "page_fetch": "📄 Fetch pages",
                "verification": "✅ Vérifications",
                "rate_limit": "⏱️ Rate limits"
            }
            selected_action = st.selectbox(
                "Type d'action",
                options=list(action_types.keys()),
                format_func=lambda x: action_types[x],
                key="log_action_filter"
            )

        with log_filter_cols[2]:
            log_days = st.selectbox(
                "Période",
                options=[1, 7, 14, 30],
                format_func=lambda x: f"{x} jour{'s' if x > 1 else ''}",
                index=1,
                key="log_days_filter"
            )

        with log_filter_cols[3]:
            log_limit = st.selectbox(
                "Limite",
                options=[50, 100, 200, 500],
                index=1,
                key="log_limit_filter"
            )

        # Vérification de tous les tokens
        if st.button("🔄 Vérifier tous les tokens", key="verify_all_tokens"):
            with st.spinner("Vérification en cours..."):
                results = verify_all_tokens(db)
            for r in results:
                if r["valid"]:
                    st.success(f"✅ {r['name']}: Valide ({r['response_time_ms']}ms)")
                else:
                    st.error(f"❌ {r['name']}: {r.get('error', 'Erreur inconnue')}")

        # Récupération des logs
        token_id_filter = None if selected_token_filter == "all" else int(selected_token_filter)
        action_filter = None if selected_action == "all" else selected_action

        logs = get_token_usage_logs(
            db,
            token_id=token_id_filter,
            days=log_days,
            limit=log_limit,
            action_type=action_filter
        )

        # Statistiques résumées
        if logs:
            st.markdown("#### 📊 Résumé")

            # Calculs
            total_logs = len(logs)
            success_logs = sum(1 for l in logs if l.get("success", False))
            error_logs = total_logs - success_logs
            total_ads = sum(l.get("ads_count", 0) or 0 for l in logs)
            avg_response = sum(l.get("response_time_ms", 0) or 0 for l in logs) / total_logs if total_logs > 0 else 0

            # Comptage par type
            action_counts = {}
            for l in logs:
                act = l.get("action_type", "unknown")
                action_counts[act] = action_counts.get(act, 0) + 1

            sum_cols = st.columns(5)
            with sum_cols[0]:
                st.metric("Total appels", total_logs)
            with sum_cols[1]:
                st.metric("✅ Succès", success_logs)
            with sum_cols[2]:
                st.metric("❌ Erreurs", error_logs)
            with sum_cols[3]:
                st.metric("📢 Ads trouvées", f"{total_ads:,}")
            with sum_cols[4]:
                st.metric("⏱️ Temps moyen", f"{avg_response:.0f}ms")

            # Stats par token (si tous sélectionnés)
            if selected_token_filter == "all" and len(tokens) > 0:
                with st.expander("📊 Répartition par token", expanded=True):
                    token_stats = {}
                    for l in logs:
                        tid = l.get("token_id")
                        tname = l.get("token_name", f"Token #{tid}")
                        if tid not in token_stats:
                            token_stats[tid] = {"name": tname, "calls": 0, "success": 0, "ads": 0}
                        token_stats[tid]["calls"] += 1
                        if l.get("success"):
                            token_stats[tid]["success"] += 1
                        token_stats[tid]["ads"] += l.get("ads_count", 0) or 0

                    for tid, stats in token_stats.items():
                        success_rate = (stats["success"] / stats["calls"] * 100) if stats["calls"] > 0 else 0
                        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                        with col1:
                            st.markdown(f"**{stats['name']}**")
                        with col2:
                            st.markdown(f"📞 {stats['calls']} appels")
                        with col3:
                            st.markdown(f"✅ {success_rate:.0f}%")
                        with col4:
                            st.markdown(f"📢 {stats['ads']:,} ads")

            # Tableau des logs
            st.markdown("#### 📝 Historique des appels")

            log_data = []
            for l in logs:
                action_icon = {
                    "search": "🔍",
                    "page_fetch": "📄",
                    "verification": "✅",
                    "rate_limit": "⏱️"
                }.get(l.get("action_type", ""), "❓")

                status_icon = "✅" if l.get("success") else "❌"

                log_data.append({
                    "Date": l.get("created_at").strftime("%d/%m %H:%M") if l.get("created_at") else "-",
                    "Token": l.get("token_name", "-")[:15],
                    "Action": f"{action_icon} {l.get('action_type', '-')}",
                    "Mot-clé": (l.get("keyword") or "-")[:20],
                    "Pays": l.get("countries") or "-",
                    "Ads": l.get("ads_count") or 0,
                    "Temps": f"{l.get('response_time_ms') or 0}ms",
                    "Status": status_icon,
                    "Erreur": (l.get("error_message") or "")[:30]
                })

            if log_data:
                st.dataframe(
                    log_data,
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("Aucun log trouvé pour les critères sélectionnés.")
            st.caption("💡 Les logs sont enregistrés automatiquement lors des recherches avec la fonction de logging activée.")

        # Stats détaillées par token (expandeur)
        with st.expander("🔬 Statistiques détaillées par token"):
            for t in tokens:
                st.markdown(f"##### {t['name']}")
                stats = get_token_stats_detailed(db, t["id"], days=30)

                if stats:
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("Total appels", stats.get("total_calls", 0))
                    with cols[1]:
                        st.metric("Taux succès", f"{stats.get('success_rate', 0):.1f}%")
                    with cols[2]:
                        st.metric("Temps moyen", f"{stats.get('avg_response_time', 0):.0f}ms")
                    with cols[3]:
                        st.metric("Total ads", f"{stats.get('total_ads', 0):,}")

                    # Top mots-clés
                    if stats.get("top_keywords"):
                        st.markdown("**Top mots-clés recherchés:**")
                        for kw in stats["top_keywords"][:5]:
                            st.caption(f"• {kw['keyword']}: {kw['count']} recherche(s)")

                    # Distribution par type
                    if stats.get("by_action_type"):
                        st.markdown("**Répartition par type:**")
                        for act in stats["by_action_type"]:
                            act_icon = {"search": "🔍", "page_fetch": "📄", "verification": "✅", "rate_limit": "⏱️"}.get(act["type"], "❓")
                            st.caption(f"• {act_icon} {act['type']}: {act['count']} appel(s)")
                else:
                    st.caption("Aucune statistique disponible")

                st.markdown("---")

    else:
        st.warning("Base de données non connectée.")

    st.markdown("---")

    # Database info
    st.subheader("🗄️ Base de données")

    db = get_database()
    if db:
        st.success("✓ Connecté à PostgreSQL")
        st.code(DATABASE_URL.replace(DATABASE_URL.split("@")[0].split(":")[-1], "****"))

        try:
            stats = get_suivi_stats(db)
            col1, col2, col3 = st.columns(3)
            col1.metric("Pages en base", stats.get("total_pages", 0))
            col2.metric("États différents", len(stats.get("etats", {})))
            col3.metric("CMS différents", len(stats.get("cms", {})))
        except:
            pass
    else:
        st.error("✗ Non connecté")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTIQUES API
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📡 Statistiques API")
    st.markdown("Utilisation des APIs sur les 30 derniers jours")

    if db:
        from app.database import get_search_logs_stats

        api_stats = get_search_logs_stats(db, days=30)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔵 Meta API", f"{api_stats.get('total_meta_api_calls', 0):,}")
        with col2:
            st.metric("🟠 ScraperAPI", f"{api_stats.get('total_scraper_api_calls', 0):,}")
        with col3:
            st.metric("🌐 Web Direct", f"{api_stats.get('total_web_requests', 0):,}")
        with col4:
            st.metric("⚠️ Rate Limits", f"{api_stats.get('total_rate_limit_hits', 0):,}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("❌ Meta Erreurs", f"{api_stats.get('total_meta_api_errors', 0):,}")
        with col2:
            st.metric("❌ Scraper Erreurs", f"{api_stats.get('total_scraper_api_errors', 0):,}")
        with col3:
            st.metric("❌ Web Erreurs", f"{api_stats.get('total_web_errors', 0):,}")
        with col4:
            cost = api_stats.get('total_scraper_api_cost', 0) or 0
            st.metric("💰 Coût ScraperAPI", f"${cost:.2f}")

        # Calcul du taux d'erreur
        total_calls = (api_stats.get('total_meta_api_calls', 0) or 0) + (api_stats.get('total_scraper_api_calls', 0) or 0)
        total_errors = (api_stats.get('total_meta_api_errors', 0) or 0) + (api_stats.get('total_scraper_api_errors', 0) or 0)
        error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0

        st.progress(min(error_rate / 100, 1.0))
        st.caption(f"Taux d'erreur: {error_rate:.1f}% ({total_errors}/{total_calls} appels)")

        # Stats par token (si disponibles)
        with st.expander("📊 Utilisation par token"):
            tokens = get_all_meta_tokens(db)
            if tokens:
                for t in tokens:
                    status = "🟢" if t["is_active"] and not t.get("is_rate_limited") else "🔴"
                    st.markdown(f"""
                    **{status} {t['name']}**
                    - Appels: {t['total_calls']:,} | Erreurs: {t['total_errors']} | Rate limits: {t['rate_limit_hits']}
                    """)
            else:
                st.caption("Aucun token configuré")

        # ═══ GESTION DU CACHE API ═══
        st.markdown("---")
        st.subheader("💾 Cache API Meta")
        st.markdown("Le cache stocke les resultats des appels API pour eviter les requetes redondantes.")

        from app.database import get_cache_stats, clear_expired_cache, clear_all_cache

        try:
            cache_stats = get_cache_stats(db)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Entrees valides", cache_stats.get("valid_entries", 0))
            with col2:
                st.metric("Entrees expirees", cache_stats.get("expired_entries", 0))
            with col3:
                st.metric("Total hits", f"{cache_stats.get('total_hits', 0):,}")
            with col4:
                hit_rate = 0
                if cache_stats.get("total_hits", 0) > 0:
                    # Estimation du hit rate
                    hit_rate = min(100, cache_stats.get("total_hits", 0) / max(1, cache_stats.get("valid_entries", 1)) * 10)
                st.metric("Efficacite", f"{hit_rate:.0f}%")

            # Stats par type
            if cache_stats.get("by_type"):
                with st.expander("📊 Details par type"):
                    for t in cache_stats["by_type"]:
                        st.write(f"**{t['type']}**: {t['count']} entrees, {t['hits']} hits")

            # Actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🧹 Nettoyer expire", key="clear_expired_cache"):
                    deleted = clear_expired_cache(db)
                    st.success(f"✅ {deleted} entrees expirees supprimees")
                    st.rerun()
            with col2:
                if st.button("🗑️ Vider tout le cache", key="clear_all_cache"):
                    deleted = clear_all_cache(db)
                    st.success(f"✅ {deleted} entrees supprimees")
                    st.rerun()
            with col3:
                st.caption("TTL: 6h (recherches), 3h (pages)")

        except Exception as e:
            st.error(f"Erreur cache: {e}")

    st.markdown("---")

    # Seuils de détection (configurables)
    st.subheader("📊 Seuils de détection")
    st.markdown("Ces seuils déterminent quelles pages sont sauvegardées dans les différentes tables de la base de données.")

    # Récupérer les seuils actuels
    detection = st.session_state.detection_thresholds

    col1, col2 = st.columns(2)

    with col1:
        new_min_suivi = st.number_input(
            "Min. ads pour Suivi (suivi_page)",
            min_value=1,
            max_value=100,
            value=detection.get("min_ads_suivi", MIN_ADS_SUIVI),
            help="Nombre minimum d'ads actives pour qu'une page soit ajoutée à la table de suivi. Cette table permet de suivre l'évolution des pages au fil du temps."
        )
        st.caption("📈 **Table suivi_page** : Historique d'évolution des pages (ads, produits) pour le monitoring")

    with col2:
        new_min_liste = st.number_input(
            "Min. ads pour Liste Ads (liste_ads_recherche)",
            min_value=1,
            max_value=100,
            value=detection.get("min_ads_liste", MIN_ADS_LISTE),
            help="Nombre minimum d'ads actives pour qu'une page ait ses annonces détaillées sauvegardées. Seules les pages dépassant ce seuil auront leurs annonces individuelles enregistrées."
        )
        st.caption("📋 **Table liste_ads_recherche** : Détail de chaque annonce (créatifs, textes, liens...)")

    # Bouton sauvegarder seuils détection
    if st.button("💾 Sauvegarder les seuils de détection", key="save_detection"):
        st.session_state.detection_thresholds = {
            "min_ads_suivi": new_min_suivi,
            "min_ads_liste": new_min_liste,
        }
        st.success("✓ Seuils de détection sauvegardés !")

    # Explication visuelle
    with st.expander("ℹ️ Comment fonctionnent ces seuils ?"):
        st.markdown("""
        **Lors d'une recherche, les pages sont filtrées par ces seuils :**

        | Table | Seuil | Contenu |
        |-------|-------|---------|
        | `liste_page_recherche` | Toutes | Toutes les pages trouvées avec infos de base |
        | `suivi_page` | Min. Suivi | Pages pour le monitoring (évolution historique) |
        | `liste_ads_recherche` | Min. Liste Ads | Détail des annonces individuelles |

        **Exemple avec seuils actuels :**
        - Une page avec **5 ads** → Sauvée uniquement dans `liste_page_recherche`
        - Une page avec **15 ads** → Sauvée dans `liste_page_recherche` + `suivi_page`
        - Une page avec **25 ads** → Sauvée dans les 3 tables
        """)

    st.markdown("---")

    # Configuration des états
    st.subheader("🏷️ Configuration des états")
    st.markdown("Définissez les seuils minimums d'ads actives pour chaque état:")

    # Récupérer les seuils actuels
    thresholds = st.session_state.state_thresholds

    col1, col2, col3 = st.columns(3)

    with col1:
        new_xs = st.number_input(
            "XS (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XS", 1),
            help="Seuil minimum pour l'état XS"
        )
        new_m = st.number_input(
            "M (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("M", 20),
            help="Seuil minimum pour l'état M"
        )

    with col2:
        new_s = st.number_input(
            "S (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("S", 10),
            help="Seuil minimum pour l'état S"
        )
        new_l = st.number_input(
            "L (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("L", 35),
            help="Seuil minimum pour l'état L"
        )

    with col3:
        new_xl = st.number_input(
            "XL (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XL", 80),
            help="Seuil minimum pour l'état XL"
        )
        new_xxl = st.number_input(
            "XXL (min)",
            min_value=1,
            max_value=1000,
            value=thresholds.get("XXL", 150),
            help="Seuil minimum pour l'état XXL"
        )

    # Bouton pour sauvegarder
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 Sauvegarder", type="primary"):
            # Vérifier la cohérence des seuils
            new_thresholds = {
                "XS": new_xs,
                "S": new_s,
                "M": new_m,
                "L": new_l,
                "XL": new_xl,
                "XXL": new_xxl
            }

            # Vérifier que les seuils sont croissants
            if new_xs < new_s < new_m < new_l < new_xl < new_xxl:
                st.session_state.state_thresholds = new_thresholds
                st.success("✓ Seuils sauvegardés !")
            else:
                st.error("Les seuils doivent être strictement croissants (XS < S < M < L < XL < XXL)")

    with col2:
        if st.button("🔄 Réinitialiser"):
            st.session_state.state_thresholds = DEFAULT_STATE_THRESHOLDS.copy()
            st.rerun()

    # Afficher un aperçu des états
    st.markdown("---")
    st.markdown("**Aperçu des états actuels:**")

    current = st.session_state.state_thresholds
    preview_data = [
        {"État": "Inactif", "Plage": "0 ads"},
        {"État": "XS", "Plage": f"{current['XS']}-{current['S']-1} ads"},
        {"État": "S", "Plage": f"{current['S']}-{current['M']-1} ads"},
        {"État": "M", "Plage": f"{current['M']}-{current['L']-1} ads"},
        {"État": "L", "Plage": f"{current['L']}-{current['XL']-1} ads"},
        {"État": "XL", "Plage": f"{current['XL']}-{current['XXL']-1} ads"},
        {"État": "XXL", "Plage": f"≥{current['XXL']} ads"},
    ]
    st.dataframe(pd.DataFrame(preview_data), width="stretch", hide_index=True)

    # ─────────────────────────────────────────────────────────────────────────────
    # Gestion de la blacklist
    st.markdown("---")
    st.subheader("🚫 Gestion de la Blacklist")

    # Ajouter manuellement une page à la blacklist
    with st.expander("➕ Ajouter une page à la blacklist"):
        col1, col2 = st.columns(2)
        with col1:
            new_bl_page_id = st.text_input("Page ID", key="new_bl_page_id")
        with col2:
            new_bl_page_name = st.text_input("Nom de la page (optionnel)", key="new_bl_page_name")

        new_bl_raison = st.text_input("Raison (optionnel)", key="new_bl_raison")

        if st.button("➕ Ajouter à la blacklist"):
            if new_bl_page_id:
                if add_to_blacklist(db, new_bl_page_id, new_bl_page_name, new_bl_raison):
                    st.success(f"✓ Page {new_bl_page_id} ajoutée à la blacklist")
                    st.rerun()
                else:
                    st.warning("Cette page est déjà dans la blacklist")
            else:
                st.error("Page ID requis")

    # Afficher la blacklist
    st.markdown("**Pages en blacklist:**")
    try:
        blacklist = get_blacklist(db)

        if blacklist:
            st.info(f"🚫 {len(blacklist)} pages en blacklist")

            for entry in blacklist:
                col1, col2, col3 = st.columns([3, 2, 1])

                with col1:
                    st.write(f"**{entry.get('page_name') or entry['page_id']}**")
                    st.caption(f"ID: {entry['page_id']}")

                with col2:
                    if entry.get('raison'):
                        st.caption(f"Raison: {entry['raison']}")
                    if entry.get('added_at'):
                        st.caption(f"Ajouté: {entry['added_at'].strftime('%Y-%m-%d %H:%M')}")

                with col3:
                    if st.button("🗑️ Retirer", key=f"rm_bl_{entry['page_id']}"):
                        if remove_from_blacklist(db, entry['page_id']):
                            st.success("✓ Retiré")
                            st.rerun()
        else:
            st.info("Aucune page en blacklist")

    except Exception as e:
        st.error(f"Erreur: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # GESTION DE LA TAXONOMIE DE CLASSIFICATION
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("Classification automatique (Gemini)")
    st.markdown("Gérez les catégories et sous-catégories pour la classification automatique des sites.")

    # Vérifier la clé API Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        st.success("✅ Clé API Gemini configurée")
    else:
        st.warning("⚠️ Clé API Gemini non configurée. Ajoutez GEMINI_API_KEY dans les variables d'environnement.")

    # Configuration du modèle Gemini
    if db:
        from app.database import get_app_setting, set_app_setting, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT

        st.markdown("---")
        st.markdown("##### Modèle Gemini")
        st.caption("Les modèles Gemini évoluent régulièrement. Modifiez si le modèle actuel devient obsolète.")

        current_model = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)

        col_model, col_btn = st.columns([3, 1])
        with col_model:
            # Liste des modèles disponibles (peut être mise à jour)
            model_options = [
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
                "gemini-1.5-pro",
                "gemini-2.0-flash-exp",
                "gemini-exp-1206",
            ]
            # Ajouter le modèle actuel s'il n'est pas dans la liste
            if current_model and current_model not in model_options:
                model_options.insert(0, current_model)

            # Champ texte pour entrer un modèle personnalisé
            new_model = st.text_input(
                "Nom du modèle",
                value=current_model,
                help="Entrez le nom exact du modèle Gemini (ex: gemini-1.5-flash, gemini-2.0-flash-exp)",
                key="gemini_model_input"
            )

        with col_btn:
            st.write("")  # Espacement
            if st.button("💾 Sauvegarder", key="save_gemini_model"):
                if new_model and new_model.strip():
                    set_app_setting(db, SETTING_GEMINI_MODEL, new_model.strip(), "Modèle Gemini pour la classification")
                    st.success(f"✅ Modèle mis à jour: {new_model}")
                    st.rerun()
                else:
                    st.error("Veuillez entrer un nom de modèle valide")

        # Afficher les modèles suggérés
        st.caption(f"**Modèles suggérés:** {', '.join(model_options[:4])}")

        # ═══ TEST API GEMINI ═══
        st.markdown("##### Tester l'API Gemini")
        st.caption("Vérifiez que la clé API et le modèle fonctionnent correctement.")

        test_col1, test_col2 = st.columns([1, 2])
        with test_col1:
            if st.button("🧪 Tester API", key="test_gemini_api", type="primary"):
                if not gemini_key:
                    st.error("❌ Clé API Gemini non configurée")
                else:
                    with st.spinner("Test en cours..."):
                        try:
                            import google.generativeai as genai
                        except ImportError:
                            st.error("❌ Librairie `google-generativeai` non installée")
                            st.code("pip install -U google-generativeai", language="bash")
                            st.caption("Installez cette librairie puis redémarrez l'application.")
                            genai = None

                        if genai:
                            try:
                                # Configurer l'API
                                genai.configure(api_key=gemini_key)

                                # Récupérer le modèle configuré
                                test_model_name = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)

                                # Créer le modèle
                                model = genai.GenerativeModel(test_model_name)

                                # Test simple avec une classification exemple
                                test_prompt = """Tu es un expert en classification de sites e-commerce.
Classifie ce site fictif de test dans une catégorie.

Site: "SuperShoes.com" - Vente de chaussures de sport et baskets pour hommes et femmes.

Réponds uniquement avec:
- Catégorie: [catégorie principale]
- Confiance: [haute/moyenne/basse]
- Raison: [1 phrase]"""

                                response = model.generate_content(test_prompt)

                                if response and response.text:
                                    st.success(f"✅ API Gemini fonctionne!")
                                    st.markdown(f"**Modèle testé:** `{test_model_name}`")
                                    st.markdown("**Réponse de test:**")
                                    st.code(response.text[:500])
                                else:
                                    st.warning("⚠️ API accessible mais réponse vide")

                            except Exception as e:
                                error_msg = str(e)
                                if "API_KEY" in error_msg or "401" in error_msg:
                                    st.error("❌ Clé API invalide ou expirée")
                                elif "model" in error_msg.lower() or "404" in error_msg:
                                    st.error(f"❌ Modèle '{test_model_name}' non trouvé. Vérifiez le nom du modèle.")
                                elif "quota" in error_msg.lower() or "429" in error_msg:
                                    st.error("❌ Quota API dépassé")
                                else:
                                    st.error(f"❌ Erreur: {error_msg[:200]}")

        with test_col2:
            st.info("Le test envoie une requête simple pour vérifier que la clé API et le modèle sont valides.")

        st.markdown("---")

    if db:
        from app.database import (
            get_all_taxonomy, add_taxonomy_entry, update_taxonomy_entry,
            delete_taxonomy_entry, init_default_taxonomy, get_taxonomy_categories,
            get_classification_stats, ClassificationTaxonomy
        )

        # Initialiser la taxonomie par défaut si vide
        if st.button("🔄 Initialiser taxonomie par défaut", key="init_taxonomy"):
            added = init_default_taxonomy(db)
            if added > 0:
                st.success(f"✅ {added} catégories ajoutées")
                st.rerun()
            else:
                st.info("La taxonomie est déjà initialisée")

        # Stats de classification
        try:
            class_stats = get_classification_stats(db)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Pages classifiées", class_stats["classified"])
            col2.metric("Non classifiées", class_stats["unclassified"])
            col3.metric("Taux", f"{class_stats['classification_rate']}%")
            col4.metric("Total pages", class_stats["total"])
        except Exception:
            pass

        # Afficher la taxonomie existante
        taxonomy = get_all_taxonomy(db, active_only=False)

        if taxonomy:
            # Grouper par catégorie
            categories = {}
            for entry in taxonomy:
                if entry.category not in categories:
                    categories[entry.category] = []
                categories[entry.category].append(entry)

            st.markdown(f"**{len(taxonomy)} entrées dans {len(categories)} catégories**")

            for cat_name, entries in categories.items():
                with st.expander(f"📁 **{cat_name}** ({len(entries)} sous-catégories)"):
                    for entry in entries:
                        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])

                        with col1:
                            new_subcat = st.text_input(
                                "Sous-catégorie",
                                value=entry.subcategory,
                                key=f"subcat_{entry.id}",
                                label_visibility="collapsed"
                            )

                        with col2:
                            new_desc = st.text_input(
                                "Description",
                                value=entry.description or "",
                                key=f"desc_{entry.id}",
                                label_visibility="collapsed",
                                placeholder="Description/exemples"
                            )

                        with col3:
                            is_active = st.checkbox(
                                "Actif",
                                value=entry.is_active,
                                key=f"active_{entry.id}"
                            )

                        with col4:
                            if st.button("🗑️", key=f"del_tax_{entry.id}"):
                                delete_taxonomy_entry(db, entry.id)
                                st.rerun()

                        # Sauvegarder si modifié
                        if (new_subcat != entry.subcategory or
                            new_desc != (entry.description or "") or
                            is_active != entry.is_active):
                            update_taxonomy_entry(
                                db, entry.id,
                                subcategory=new_subcat,
                                description=new_desc if new_desc else None,
                                is_active=is_active
                            )

        # Ajouter une nouvelle entrée
        st.markdown("---")
        st.markdown("**➕ Ajouter une catégorie/sous-catégorie**")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Liste des catégories existantes + option nouvelle
            existing_cats = get_taxonomy_categories(db)
            cat_options = existing_cats + ["➕ Nouvelle catégorie..."]
            selected_cat = st.selectbox("Catégorie", options=cat_options, key="new_tax_cat")

            if selected_cat == "➕ Nouvelle catégorie...":
                new_cat_name = st.text_input("Nouvelle catégorie", key="new_cat_name")
            else:
                new_cat_name = selected_cat

        with col2:
            new_subcat_name = st.text_input("Sous-catégorie", key="new_subcat_name")

        with col3:
            new_tax_desc = st.text_input("Description", key="new_tax_desc", placeholder="Exemples de produits...")

        if st.button("➕ Ajouter", key="add_taxonomy"):
            if new_cat_name and new_subcat_name:
                entry_id = add_taxonomy_entry(db, new_cat_name, new_subcat_name, new_tax_desc or None)
                st.success(f"✅ Entrée ajoutée (ID: {entry_id})")
                st.rerun()
            else:
                st.error("Catégorie et sous-catégorie requises")

        # Lancer la classification manuelle
        st.markdown("---")
        st.markdown("**🚀 Classifier les pages non classifiées**")

        col1, col2 = st.columns([1, 2])
        with col1:
            batch_size = st.number_input("Nombre de pages", min_value=10, max_value=500, value=50, step=10)

        with col2:
            if st.button("🚀 Lancer la classification", key="run_classification", type="primary"):
                if not gemini_key:
                    st.error("Configurez GEMINI_API_KEY d'abord")
                else:
                    with st.spinner(f"Classification de {batch_size} pages en cours..."):
                        try:
                            from app.gemini_classifier import classify_and_save

                            result = classify_and_save(db, limit=batch_size)

                            if "error" in result:
                                st.error(result["error"])
                            else:
                                st.success(f"✅ {result['classified']} pages classifiées ({result.get('errors', 0)} erreurs)")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erreur: {e}")

        # ═══════════════════════════════════════════════════════════════════════════
        # MIGRATION: Appliquer aux pages existantes
        # ═══════════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("🔄 Migration des données existantes")
        st.markdown("Appliquer la classification et le pays France aux pages déjà enregistrées.")

        # Importer les fonctions de migration
        from app.database import (
            get_pages_count, migration_add_country_to_all_pages,
            get_all_pages_for_classification, update_pages_classification_batch,
            build_taxonomy_prompt, init_default_taxonomy
        )

        # Stats actuelles
        try:
            migration_stats = get_pages_count(db)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total pages", migration_stats["total"])
            col2.metric("Classifiées", migration_stats["classified"])
            col3.metric("Avec pays FR", migration_stats["with_fr"])
            col4.metric("Sans pays FR", migration_stats["without_fr"])
        except Exception:
            migration_stats = {"total": 0, "classified": 0, "with_fr": 0, "without_fr": 0, "unclassified": 0}

        # Actions de migration
        st.markdown("**Actions de migration:**")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🇫🇷 Ajouter France**")
            st.caption(f"{migration_stats.get('without_fr', 0)} pages sans FR")
            if st.button("Ajouter FR à toutes les pages", key="migration_add_fr", type="secondary"):
                if migration_stats.get('without_fr', 0) == 0:
                    st.info("✓ Toutes les pages ont déjà FR")
                else:
                    with st.spinner("Ajout de FR en cours..."):
                        try:
                            updated = migration_add_country_to_all_pages(db, "FR")
                            st.success(f"✅ {updated} pages mises à jour avec FR")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur: {e}")

        with col2:
            st.markdown("**Classification Gemini**")
            unclassified = migration_stats.get('unclassified', 0)
            st.caption(f"{unclassified} pages non classifiées")
            reclassify_all = st.checkbox("Re-classifier TOUTES les pages", key="migration_reclassify_all")

            pages_to_classify = migration_stats.get('total', 0) if reclassify_all else unclassified

            if st.button("Lancer la classification", key="migration_classify", type="secondary"):
                if not gemini_key:
                    st.error("Configurez GEMINI_API_KEY d'abord")
                elif pages_to_classify == 0:
                    st.info("✓ Aucune page à classifier")
                else:
                    # Estimation du temps
                    from app.gemini_classifier import BATCH_SIZE, RATE_LIMIT_DELAY
                    gemini_batches = (pages_to_classify + BATCH_SIZE - 1) // BATCH_SIZE
                    estimated_time = gemini_batches * RATE_LIMIT_DELAY / 60

                    st.info(f"⏱️ Temps estimé: ~{estimated_time:.1f} minutes ({gemini_batches} batches)")

                    # Progress bar et status
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        # Initialiser taxonomie
                        init_default_taxonomy(db)
                        taxonomy_text = build_taxonomy_prompt(db)

                        if not taxonomy_text:
                            st.error("Aucune taxonomie configurée")
                        else:
                            # Récupérer les pages
                            pages = get_all_pages_for_classification(db, include_classified=reclassify_all)
                            total_pages = len(pages)

                            if total_pages == 0:
                                st.info("✓ Aucune page à classifier")
                            else:
                                from app.gemini_classifier import classify_pages_sync

                                # Traiter par lots
                                batch_size_migration = 100
                                total_classified = 0
                                total_errors = 0

                                for i in range(0, total_pages, batch_size_migration):
                                    batch = pages[i:i + batch_size_migration]
                                    batch_num = i // batch_size_migration + 1
                                    total_batches = (total_pages + batch_size_migration - 1) // batch_size_migration

                                    progress = (i + len(batch)) / total_pages
                                    progress_bar.progress(progress)
                                    status_text.text(f"Batch {batch_num}/{total_batches} - {len(batch)} pages...")

                                    try:
                                        results = classify_pages_sync(batch, taxonomy_text)

                                        classifications = [
                                            {
                                                "page_id": r.page_id,
                                                "category": r.category,
                                                "subcategory": r.subcategory,
                                                "confidence": r.confidence_score
                                            }
                                            for r in results
                                        ]

                                        updated = update_pages_classification_batch(db, classifications)
                                        errors = sum(1 for r in results if r.error)
                                        total_classified += updated
                                        total_errors += errors

                                    except Exception as e:
                                        st.warning(f"Erreur batch {batch_num}: {e}")
                                        total_errors += len(batch)

                                progress_bar.progress(1.0)
                                status_text.text("Terminé!")
                                st.success(f"✅ {total_classified} pages classifiées ({total_errors} erreurs)")
                                st.rerun()

                    except Exception as e:
                        st.error(f"Erreur: {e}")

        with col3:
            st.markdown("**🚀 Migration complète**")
            st.caption("FR + Classification de toutes les pages")
            if st.button("Lancer migration complète", key="migration_full", type="primary"):
                if not gemini_key:
                    st.error("Configurez GEMINI_API_KEY d'abord")
                else:
                    # Étape 1: Ajouter FR
                    with st.spinner("Étape 1/2: Ajout de FR..."):
                        try:
                            updated_fr = migration_add_country_to_all_pages(db, "FR")
                            st.success(f"✅ Étape 1: {updated_fr} pages avec FR")
                        except Exception as e:
                            st.error(f"Erreur FR: {e}")
                            updated_fr = 0

                    # Étape 2: Classification
                    from app.gemini_classifier import BATCH_SIZE, RATE_LIMIT_DELAY

                    init_default_taxonomy(db)
                    taxonomy_text = build_taxonomy_prompt(db)

                    if not taxonomy_text:
                        st.error("Aucune taxonomie configurée")
                    else:
                        pages = get_all_pages_for_classification(db, include_classified=True)
                        total_pages = len(pages)

                        if total_pages == 0:
                            st.info("✓ Aucune page à classifier")
                        else:
                            gemini_batches = (total_pages + BATCH_SIZE - 1) // BATCH_SIZE
                            estimated_time = gemini_batches * RATE_LIMIT_DELAY / 60
                            st.info(f"⏱️ Étape 2: Classification de {total_pages} pages (~{estimated_time:.1f} min)")

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            try:
                                from app.gemini_classifier import classify_pages_sync

                                batch_size_migration = 100
                                total_classified = 0
                                total_errors = 0

                                for i in range(0, total_pages, batch_size_migration):
                                    batch = pages[i:i + batch_size_migration]
                                    batch_num = i // batch_size_migration + 1
                                    total_batches = (total_pages + batch_size_migration - 1) // batch_size_migration

                                    progress = (i + len(batch)) / total_pages
                                    progress_bar.progress(progress)
                                    status_text.text(f"Batch {batch_num}/{total_batches}...")

                                    try:
                                        results = classify_pages_sync(batch, taxonomy_text)

                                        classifications = [
                                            {
                                                "page_id": r.page_id,
                                                "category": r.category,
                                                "subcategory": r.subcategory,
                                                "confidence": r.confidence_score
                                            }
                                            for r in results
                                        ]

                                        updated = update_pages_classification_batch(db, classifications)
                                        errors = sum(1 for r in results if r.error)
                                        total_classified += updated
                                        total_errors += errors

                                    except Exception as e:
                                        total_errors += len(batch)

                                progress_bar.progress(1.0)
                                status_text.text("Migration terminée!")
                                st.success(f"✅ Migration complète: {updated_fr} pages FR, {total_classified} classifiées")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Erreur classification: {e}")

        # ═══════════════════════════════════════════════════════════════════════════
        # NETTOYAGE DES DOUBLONS
        # ═══════════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("🧹 Nettoyage des doublons")
        st.markdown("Supprimez les entrées en doublon dans la base de données (garde les plus récentes).")

        from sqlalchemy import func
        from app.database import AdsRecherche, WinningAds

        with db.get_session() as session:
            # Compter les doublons dans liste_ads_recherche
            ads_duplicates = session.query(
                AdsRecherche.ad_id,
                func.count(AdsRecherche.id).label('count')
            ).group_by(AdsRecherche.ad_id).having(func.count(AdsRecherche.id) > 1).count()

            # Compter les doublons dans winning_ads
            winning_duplicates = session.query(
                WinningAds.ad_id,
                func.count(WinningAds.id).label('count')
            ).group_by(WinningAds.ad_id).having(func.count(WinningAds.id) > 1).count()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Doublons Ads Recherche", ads_duplicates)
        with col2:
            st.metric("Doublons Winning Ads", winning_duplicates)
        with col3:
            st.metric("Total doublons", ads_duplicates + winning_duplicates)

        if ads_duplicates + winning_duplicates > 0:
            st.warning(f"⚠️ {ads_duplicates + winning_duplicates} doublons détectés")

            if st.button("🧹 Nettoyer les doublons", type="primary", key="cleanup_duplicates"):
                with st.spinner("Nettoyage en cours..."):
                    total_deleted = 0

                    # Nettoyer liste_ads_recherche
                    with db.get_session() as session:
                        # Trouver les ad_id avec doublons
                        duplicates_ads = session.query(
                            AdsRecherche.ad_id
                        ).group_by(AdsRecherche.ad_id).having(func.count(AdsRecherche.id) > 1).all()

                        for (ad_id,) in duplicates_ads:
                            entries = session.query(AdsRecherche).filter(
                                AdsRecherche.ad_id == ad_id
                            ).order_by(AdsRecherche.date_scan.desc()).all()

                            for entry in entries[1:]:  # Garder le premier (plus récent)
                                session.delete(entry)
                                total_deleted += 1

                        session.commit()

                    # Nettoyer winning_ads
                    with db.get_session() as session:
                        duplicates_winning = session.query(
                            WinningAds.ad_id
                        ).group_by(WinningAds.ad_id).having(func.count(WinningAds.id) > 1).all()

                        for (ad_id,) in duplicates_winning:
                            entries = session.query(WinningAds).filter(
                                WinningAds.ad_id == ad_id
                            ).order_by(WinningAds.date_scan.desc()).all()

                            for entry in entries[1:]:
                                session.delete(entry)
                                total_deleted += 1

                        session.commit()

                    st.success(f"✅ {total_deleted} doublons supprimés")
                    st.rerun()
        else:
            st.success("✅ Aucun doublon détecté")

        # ═══════════════════════════════════════════════════════════════════════════
        # ARCHIVAGE DES DONNEES ANCIENNES
        # ═══════════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("📦 Archivage des anciennes donnees")
        st.markdown("Deplacez les donnees de plus de 90 jours vers les tables d'archive pour optimiser les performances.")

        from app.database import get_archive_stats, archive_old_data

        try:
            archive_stats = get_archive_stats(db)

            # Stats actuelles
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Tables principales**")
                st.metric("Suivi Page", archive_stats.get("suivi_page", 0))
                st.metric("Ads Recherche", archive_stats.get("liste_ads_recherche", 0))
                st.metric("Winning Ads", archive_stats.get("winning_ads", 0))
            with col2:
                st.markdown("**Archivables (>90j)**")
                st.metric("Suivi Page", archive_stats.get("suivi_page_archivable", 0))
                st.metric("Ads Recherche", archive_stats.get("liste_ads_recherche_archivable", 0))
                st.metric("Winning Ads", archive_stats.get("winning_ads_archivable", 0))
            with col3:
                st.markdown("**Deja archives**")
                st.metric("Suivi Page", archive_stats.get("suivi_page_archive", 0))
                st.metric("Ads Recherche", archive_stats.get("liste_ads_recherche_archive", 0))
                st.metric("Winning Ads", archive_stats.get("winning_ads_archive", 0))

            # Total archivable
            total_archivable = (
                archive_stats.get("suivi_page_archivable", 0) +
                archive_stats.get("liste_ads_recherche_archivable", 0) +
                archive_stats.get("winning_ads_archivable", 0)
            )

            if total_archivable > 0:
                st.warning(f"⚠️ {total_archivable:,} entrees peuvent etre archivees")

                col1, col2 = st.columns([1, 2])
                with col1:
                    days_threshold = st.number_input("Seuil (jours)", min_value=30, max_value=365, value=90, key="archive_days")

                if st.button("📦 Lancer l'archivage", type="primary", key="archive_btn"):
                    with st.spinner("Archivage en cours..."):
                        result = archive_old_data(db, days_threshold=days_threshold)
                        total_archived = sum(result.values())
                        st.success(f"✅ {total_archived:,} entrees archivees")
                        st.json(result)
                        st.rerun()
            else:
                st.success("✅ Aucune donnee a archiver")

        except Exception as e:
            st.error(f"Erreur: {e}")

    else:
        st.warning("Base de données non connectée")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: FAVORIS
# ═══════════════════════════════════════════════════════════════════════════════

def render_favorites():
    """Page Favoris - Pages favorites"""
    st.title("⭐ Favoris")
    st.markdown("Vos pages favorites pour un accès rapide")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    try:
        favorite_ids = get_favorites(db)

        if favorite_ids:
            st.info(f"⭐ {len(favorite_ids)} page(s) en favoris")

            # Récupérer les détails des pages favorites
            pages = []
            for fav_id in favorite_ids:
                page_results = search_pages(db, search_term=fav_id, limit=1)
                if page_results:
                    pages.append(page_results[0])

            if pages:
                for page in pages:
                    pid = page.get("page_id")
                    with st.expander(f"⭐ **{page.get('page_name', 'N/A')}** - {page.get('etat', 'N/A')} ({page.get('nombre_ads_active', 0)} ads)"):
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                            st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")

                            # Tags
                            tags = get_page_tags(db, pid)
                            if tags:
                                tag_html = " ".join([f"<span style='background-color:{t['color']};color:white;padding:2px 8px;border-radius:10px;margin-right:5px;font-size:12px;'>{t['name']}</span>" for t in tags])
                                st.markdown(tag_html, unsafe_allow_html=True)

                            # Notes
                            notes = get_page_notes(db, pid)
                            if notes:
                                st.caption(f"📝 {len(notes)} note(s)")

                        with col2:
                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                        with col3:
                            if st.button("❌ Retirer", key=f"unfav_{pid}"):
                                remove_favorite(db, pid)
                                st.success("Retiré des favoris")
                                st.rerun()
        else:
            st.info("Aucune page en favoris. Ajoutez des pages depuis la page Pages/Shops.")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: COLLECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def render_collections():
    """Page Collections - Dossiers de pages"""
    st.title("📁 Collections")
    st.markdown("Organisez vos pages en dossiers thématiques")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Créer une nouvelle collection
    with st.expander("➕ Nouvelle collection", expanded=False):
        with st.form("new_collection"):
            col1, col2 = st.columns(2)
            with col1:
                coll_name = st.text_input("Nom *", placeholder="Ex: Concurrents mode")
            with col2:
                coll_icon = st.selectbox("Icône", ["📁", "🎯", "🔥", "💎", "🚀", "⭐", "🏆", "📊"])

            coll_desc = st.text_area("Description", placeholder="Description optionnelle...")
            coll_color = st.color_picker("Couleur", "#6366F1")

            if st.form_submit_button("Créer", type="primary"):
                if coll_name:
                    create_collection(db, coll_name, coll_desc, coll_color, coll_icon)
                    st.success(f"Collection '{coll_name}' créée!")
                    st.rerun()
                else:
                    st.error("Nom requis")

    st.markdown("---")

    # Liste des collections
    collections = get_collections(db)

    if collections:
        for coll in collections:
            coll_id = coll["id"]
            with st.expander(f"{coll['icon']} **{coll['name']}** ({coll['page_count']} pages)"):
                st.caption(coll.get("description", ""))

                # Pages de la collection
                page_ids = get_collection_pages(db, coll_id)
                if page_ids:
                    for pid in page_ids[:10]:  # Limiter à 10
                        page_results = search_pages(db, search_term=pid, limit=1)
                        if page_results:
                            page = page_results[0]
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"• {page.get('page_name', pid)} - {page.get('etat', 'N/A')}")
                            with col2:
                                if st.button("❌", key=f"rm_{coll_id}_{pid}"):
                                    remove_page_from_collection(db, coll_id, pid)
                                    st.rerun()
                else:
                    st.caption("Aucune page dans cette collection")

                # Actions
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col2:
                    if st.button("🗑️ Supprimer collection", key=f"del_coll_{coll_id}"):
                        delete_collection(db, coll_id)
                        st.success("Collection supprimée")
                        st.rerun()
    else:
        st.info("Aucune collection. Créez-en une pour organiser vos pages.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: TAGS
# ═══════════════════════════════════════════════════════════════════════════════

def render_tags():
    """Page Tags - Gestion des tags"""
    st.title("🏷️ Tags")
    st.markdown("Créez et gérez vos tags personnalisés")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    # Créer un nouveau tag
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        new_tag_name = st.text_input("Nouveau tag", placeholder="Ex: À surveiller")
    with col2:
        new_tag_color = st.color_picker("Couleur", "#3B82F6")
    with col3:
        st.write("")
        st.write("")
        if st.button("➕ Créer", type="primary"):
            if new_tag_name:
                result = create_tag(db, new_tag_name.strip(), new_tag_color)
                if result:
                    st.success(f"Tag '{new_tag_name}' créé!")
                    st.rerun()
                else:
                    st.error("Ce tag existe déjà")
            else:
                st.error("Nom requis")

    st.markdown("---")

    # Liste des tags
    tags = get_all_tags(db)

    if tags:
        st.subheader(f"📋 {len(tags)} tag(s)")

        for tag in tags:
            tag_id = tag["id"]
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.markdown(
                    f"<span style='background-color:{tag['color']};color:white;padding:5px 15px;border-radius:15px;'>{tag['name']}</span>",
                    unsafe_allow_html=True
                )

            with col2:
                # Nombre de pages avec ce tag
                page_ids = get_pages_by_tag(db, tag_id)
                st.caption(f"{len(page_ids)} page(s)")

            with col3:
                if st.button("👁️ Voir", key=f"view_tag_{tag_id}"):
                    st.session_state.filter_tag_id = tag_id
                    st.session_state.current_page = "Pages / Shops"
                    st.rerun()

            with col4:
                if st.button("🗑️", key=f"del_tag_{tag_id}"):
                    delete_tag(db, tag_id)
                    st.success("Tag supprimé")
                    st.rerun()
    else:
        st.info("Aucun tag créé. Créez votre premier tag ci-dessus.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CREATIVE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def render_creative_analysis():
    """Page Creative Analysis - Analyse des créatives publicitaires"""
    st.title("🎨 Creative Analysis")
    st.markdown("Analysez les tendances créatives des annonces")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    info_card(
        "Comment utiliser cette analyse ?",
        """
        Cette page analyse le contenu textuel des annonces pour identifier :<br>
        • Les <b>mots-clés</b> les plus utilisés dans les titres et textes<br>
        • Les <b>emojis</b> les plus populaires<br>
        • Les <b>call-to-actions</b> (CTA) les plus fréquents<br>
        • Les <b>longueurs de texte</b> optimales
        """,
        "🎨"
    )

    try:
        # Récupérer les winning ads pour analyse
        winning_ads = get_winning_ads(db, limit=500, days=30)

        if not winning_ads:
            st.warning("Pas assez de données. Lancez des recherches pour collecter des annonces.")
            return

        st.success(f"📊 Analyse basée sur {len(winning_ads)} winning ads")

        # Analyse des textes
        all_bodies = []
        all_titles = []
        all_captions = []
        emojis = []

        import re

        for ad in winning_ads:
            body = ad.get("ad_creative_bodies", "") or ""
            title = ad.get("ad_creative_link_titles", "") or ""
            caption = ad.get("ad_creative_link_captions", "") or ""

            all_bodies.append(body)
            all_titles.append(title)
            all_captions.append(caption)

            # Extraire emojis
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"
                u"\U0001F300-\U0001F5FF"
                u"\U0001F680-\U0001F6FF"
                u"\U0001F1E0-\U0001F1FF"
                u"\U00002702-\U000027B0"
                u"\U000024C2-\U0001F251"
                "]+", flags=re.UNICODE)
            found_emojis = emoji_pattern.findall(body + " " + title)
            emojis.extend(found_emojis)

        # Statistiques
        col1, col2, col3, col4 = st.columns(4)

        avg_body_len = sum(len(b) for b in all_bodies) / len(all_bodies) if all_bodies else 0
        avg_title_len = sum(len(t) for t in all_titles) / len(all_titles) if all_titles else 0

        col1.metric("📝 Longueur moyenne texte", f"{avg_body_len:.0f} car.")
        col2.metric("📌 Longueur moyenne titre", f"{avg_title_len:.0f} car.")
        col3.metric("😀 Total emojis trouvés", len(emojis))
        col4.metric("📊 Ads analysées", len(winning_ads))

        st.markdown("---")

        # Top mots-clés
        col1, col2 = st.columns(2)

        with col1:
            chart_header("🔤 Mots-clés fréquents", "Mots les plus utilisés dans les textes")

            # Compter les mots
            all_text = " ".join(all_bodies + all_titles).lower()
            words = re.findall(r'\b[a-zàâäéèêëïîôùûüç]{4,}\b', all_text)

            # Stopwords français basiques
            stopwords = {"pour", "dans", "avec", "vous", "votre", "nous", "cette", "plus", "tout", "tous", "faire", "comme", "être", "avoir", "sans"}
            words = [w for w in words if w not in stopwords]

            word_counts = Counter(words).most_common(10)

            if word_counts:
                labels = [w[0] for w in word_counts]
                values = [w[1] for w in word_counts]
                fig = create_horizontal_bar_chart(labels, values, colors=[CHART_COLORS["primary"]] * len(labels))
                st.plotly_chart(fig, key="word_freq", width="stretch")

        with col2:
            chart_header("😀 Emojis populaires", "Emojis les plus utilisés")

            emoji_counts = Counter(emojis).most_common(10)

            if emoji_counts:
                for emoji, count in emoji_counts:
                    st.write(f"{emoji} : {count} fois")
            else:
                st.caption("Pas assez d'emojis trouvés")

        # CTAs fréquents
        st.markdown("---")
        chart_header("🎯 Call-to-Actions détectés", "Phrases d'action les plus fréquentes")

        cta_patterns = [
            "acheter maintenant", "commander", "découvrir", "profiter", "en savoir plus",
            "cliquez", "obtenez", "télécharger", "essayer", "réserver",
            "shop now", "buy now", "order now", "get yours", "learn more",
            "livraison gratuite", "offre limitée", "promo", "soldes", "-50%", "-30%"
        ]

        cta_counts = {}
        combined_text = " ".join(all_bodies + all_titles + all_captions).lower()

        for cta in cta_patterns:
            count = combined_text.count(cta.lower())
            if count > 0:
                cta_counts[cta] = count

        if cta_counts:
            sorted_ctas = sorted(cta_counts.items(), key=lambda x: x[1], reverse=True)[:8]
            for cta, count in sorted_ctas:
                st.write(f"• **{cta}** : {count} occurrence(s)")
        else:
            st.caption("Aucun CTA commun détecté")

        # ═══════════════════════════════════════════════════════════════════════════
        # GALERIE DES CRÉATIFS
        # ═══════════════════════════════════════════════════════════════════════════
        st.markdown("---")
        chart_header(
            "🖼️ Galerie des créatifs",
            "Aperçu visuel des publicités performantes",
            "Cliquez sur une ad pour voir les détails"
        )

        # Filtrer les ads avec des URLs d'aperçu
        ads_with_preview = [ad for ad in winning_ads if ad.get("ad_snapshot_url")]

        if ads_with_preview:
            # Contrôles de la galerie
            col_filter, col_sort = st.columns(2)
            with col_filter:
                gallery_limit = st.slider("Nombre d'ads", 6, 30, 12, 6, key="gallery_limit")
            with col_sort:
                sort_by = st.selectbox("Trier par", ["Reach", "Âge (récent)", "Page"], key="gallery_sort")

            # Trier
            if sort_by == "Reach":
                ads_with_preview = sorted(ads_with_preview, key=lambda x: x.get("eu_total_reach", 0) or 0, reverse=True)
            elif sort_by == "Âge (récent)":
                ads_with_preview = sorted(ads_with_preview, key=lambda x: x.get("ad_age_days", 999))

            # Affichage en grille
            cols_per_row = 3
            ads_to_show = ads_with_preview[:gallery_limit]

            for i in range(0, len(ads_to_show), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    if i + j < len(ads_to_show):
                        ad = ads_to_show[i + j]
                        with col:
                            # Card de l'ad
                            reach = ad.get("eu_total_reach", 0) or 0
                            reach_str = f"{reach/1000:.0f}K" if reach >= 1000 else str(reach)
                            age = ad.get("ad_age_days", 0)
                            page_name = (ad.get("page_name", "N/A") or "N/A")[:20]

                            st.markdown(f"""
                            <div style="border: 1px solid #333; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
                                <div style="font-size: 12px; color: #888;">📊 {reach_str} reach • {age}j</div>
                                <div style="font-size: 14px; font-weight: bold; margin: 5px 0;">{page_name}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Texte de l'ad (aperçu)
                            body = ad.get("ad_creative_bodies", "") or ""
                            if body:
                                st.caption(body[:80] + ("..." if len(body) > 80 else ""))

                            # Lien vers l'ad
                            ad_url = ad.get("ad_snapshot_url", "")
                            if ad_url:
                                st.link_button("👁️ Voir", ad_url, use_container_width=True)
        else:
            st.info("Aucune ad avec aperçu disponible")

    except Exception as e:
        st.error(f"Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SCHEDULED SCANS
# ═══════════════════════════════════════════════════════════════════════════════

def render_scheduled_scans():
    """Page Scans Programmés - Automatisation des recherches"""
    st.title("🕐 Scans Programmés")
    st.markdown("Automatisez vos recherches récurrentes")

    db = get_database()
    if not db:
        st.warning("Base de données non connectée")
        return

    info_card(
        "Comment fonctionnent les scans programmés ?",
        """
        Les scans programmés vous permettent de :<br>
        • Définir des recherches automatiques par mots-clés<br>
        • Choisir la fréquence (quotidien, hebdomadaire, mensuel)<br>
        • Recevoir automatiquement les nouvelles pages détectées<br><br>
        <b>Note :</b> Pour l'exécution automatique, un scheduler externe (cron) est nécessaire.
        """,
        "🕐"
    )

    # Créer un nouveau scan
    with st.expander("➕ Nouveau scan programmé", expanded=False):
        with st.form("new_scan"):
            scan_name = st.text_input("Nom du scan *", placeholder="Ex: Veille mode femme")
            scan_keywords = st.text_area("Mots-clés *", placeholder="Un mot-clé par ligne\nEx:\nrobe été\nmode femme\nsummer dress")

            col1, col2, col3 = st.columns(3)
            with col1:
                scan_countries = st.multiselect("Pays", AVAILABLE_COUNTRIES, default=["FR"])
            with col2:
                scan_languages = st.multiselect("Langues", AVAILABLE_LANGUAGES, default=["fr"])
            with col3:
                scan_frequency = st.selectbox("Fréquence", ["daily", "weekly", "monthly"], format_func=lambda x: {"daily": "Quotidien", "weekly": "Hebdomadaire", "monthly": "Mensuel"}[x])

            if st.form_submit_button("Créer le scan", type="primary"):
                if scan_name and scan_keywords:
                    create_scheduled_scan(
                        db,
                        scan_name,
                        scan_keywords,
                        ",".join(scan_countries),
                        ",".join(scan_languages),
                        scan_frequency
                    )
                    st.success(f"Scan '{scan_name}' créé!")
                    st.rerun()
                else:
                    st.error("Nom et mots-clés requis")

    st.markdown("---")

    # Liste des scans
    scans = get_scheduled_scans(db)

    if scans:
        st.subheader(f"📋 {len(scans)} scan(s) programmé(s)")

        for scan in scans:
            scan_id = scan["id"]
            status_icon = "🟢" if scan["is_active"] else "🔴"
            freq_label = {"daily": "Quotidien", "weekly": "Hebdomadaire", "monthly": "Mensuel"}.get(scan["frequency"], scan["frequency"])

            with st.expander(f"{status_icon} **{scan['name']}** - {freq_label}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**Mots-clés:** {scan['keywords'][:100]}...")
                    st.write(f"**Pays:** {scan['countries']} | **Langues:** {scan['languages']}")

                    if scan["last_run"]:
                        st.caption(f"Dernier run: {scan['last_run'].strftime('%Y-%m-%d %H:%M')}")
                    if scan["next_run"]:
                        st.caption(f"Prochain run: {scan['next_run'].strftime('%Y-%m-%d %H:%M')}")

                with col2:
                    # Toggle actif/inactif
                    new_status = st.toggle("Actif", value=scan["is_active"], key=f"toggle_{scan_id}")
                    if new_status != scan["is_active"]:
                        update_scheduled_scan(db, scan_id, is_active=new_status)
                        st.rerun()

                    if st.button("🗑️ Supprimer", key=f"del_scan_{scan_id}"):
                        delete_scheduled_scan(db, scan_id)
                        st.success("Scan supprimé")
                        st.rerun()

                    if st.button("▶️ Exécuter", key=f"run_scan_{scan_id}"):
                        st.info("Fonctionnalité en cours de développement")
    else:
        st.info("Aucun scan programmé. Créez-en un pour automatiser vos recherches.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: BACKGROUND SEARCHES
# ═══════════════════════════════════════════════════════════════════════════════

def render_background_searches():
    """Page de suivi des recherches en arrière-plan - uniquement les recherches actives"""
    import json

    # Auto-refresh toutes les 5 secondes si des recherches sont en cours
    try:
        from streamlit_autorefresh import st_autorefresh
        # Ne pas auto-refresh si pas de recherches actives (vérifié plus bas)
        auto_refresh_enabled = st.session_state.get("bg_has_active_searches", False)
        if auto_refresh_enabled:
            st_autorefresh(interval=5000, limit=None, key="bg_autorefresh")
    except ImportError:
        pass  # Package non installé, refresh manuel

    st.title("🔄 Recherches en cours")
    st.markdown("Suivi en temps réel des recherches en arrière-plan.")
    st.caption("💡 Les numéros de tâche (Tâche #X) sont différents des numéros de recherche dans l'historique (Recherche #Y). Une fois terminée, la recherche apparaît dans **Historique**.")

    db = get_database()
    if not db:
        st.error("Base de données non connectée")
        return

    # Initialiser le worker
    try:
        from app.background_worker import get_worker, init_worker
        from app.database import (
            get_interrupted_searches, restart_search_queue,
            cancel_search_queue, SearchQueue
        )
        worker = init_worker()
    except Exception as e:
        st.error(f"Erreur initialisation worker: {e}")
        return

    # ═══ Recherches interrompues (après redémarrage) ═══
    interrupted = get_interrupted_searches(db)
    if interrupted:
        st.warning(f"⚠️ {len(interrupted)} recherche(s) interrompue(s) suite à une maintenance")

        for search in interrupted:
            keywords = json.loads(search.keywords) if search.keywords else []
            keywords_display = ", ".join(keywords[:3])
            if len(keywords) > 3:
                keywords_display += f"... (+{len(keywords) - 3})"

            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.write(f"**Tâche #{search.id}** - {search.created_at:%d/%m %H:%M} - Phase {search.current_phase}/9")
                st.caption(f"Mots-clés: {keywords_display}")
            with col2:
                if st.button("🔄 Reprendre", key=f"resume_{search.id}"):
                    restart_search_queue(db, search.id)
                    st.success("Recherche relancée!")
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"delete_int_{search.id}"):
                    with db.get_session() as session:
                        session.query(SearchQueue).filter(SearchQueue.id == search.id).delete()
                    st.rerun()

        st.divider()

    # ═══ Recherches actives ═══
    active_searches = worker.get_active_searches()

    # Stocker l'état pour l'auto-refresh
    st.session_state["bg_has_active_searches"] = len(active_searches) > 0

    if active_searches:
        # Bouton de rafraîchissement manuel
        col_refresh, col_info = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 Rafraîchir", width="stretch"):
                st.rerun()
        with col_info:
            st.caption("🔁 Rafraîchissement automatique toutes les 5 secondes")

        st.divider()

        for search in active_searches:
            keywords = search.get("keywords", [])
            keywords_display = ", ".join(keywords[:5])
            if len(keywords) > 5:
                keywords_display += f"... (+{len(keywords) - 5})"

            # Container avec bordure visuelle
            with st.container():
                # En-tête avec statut
                if search["status"] == "running":
                    phase = search.get("phase", 0)
                    phase_name = search.get("phase_name", "")
                    progress = search.get("progress", 0)
                    message = search.get("message", "")
                    phases_data = search.get("phases_data", [])

                    # Titre avec phase et temps écoulé
                    header_col1, header_col2 = st.columns([3, 1])
                    with header_col1:
                        st.markdown(f"### 🟢 Tâche #{search['id']} - En cours")
                    with header_col2:
                        if search.get("started_at"):
                            started = search["started_at"]
                            elapsed = datetime.now() - started.replace(tzinfo=None)
                            minutes = int(elapsed.total_seconds() // 60)
                            seconds = int(elapsed.total_seconds() % 60)
                            st.markdown(f"**⏱️ {minutes}m {seconds}s**")

                    # Informations de la phase actuelle
                    phase_col1, phase_col2 = st.columns([3, 1])
                    with phase_col1:
                        st.markdown(f"**Phase {phase}/9:** {phase_name}")
                    with phase_col2:
                        st.markdown(f"**{progress}%**")

                    # Barre de progression
                    st.progress(progress / 100)

                    # Message de progression détaillé
                    if message:
                        st.info(f"📍 {message}")

                    # ═══ Journal d'activité détaillé ═══
                    st.markdown("##### 📋 Journal d'activité")

                    # Afficher les phases complétées
                    if phases_data:
                        for phase_info in phases_data:
                            phase_num = phase_info.get("num", "?")
                            phase_name_log = phase_info.get("name", "")
                            phase_result = phase_info.get("result", "")
                            phase_duration = phase_info.get("duration", "")

                            # Formater la durée
                            duration_str = ""
                            if phase_duration:
                                if phase_duration >= 60:
                                    duration_str = f" ({phase_duration/60:.1f}m)"
                                else:
                                    duration_str = f" ({phase_duration:.1f}s)"

                            st.markdown(f"✅ **Phase {phase_num}:** {phase_name_log} → {phase_result}{duration_str}")

                    # Phase en cours (non encore complétée)
                    if phase and phase_name:
                        st.markdown(f"🔄 **Phase {phase}:** {phase_name} ...")

                    # Afficher les mots-clés
                    st.caption(f"🔍 Mots-clés: {keywords_display}")

                else:
                    # Recherche en attente
                    st.markdown(f"### 🟡 Tâche #{search['id']} - En attente")
                    st.write(f"**Mots-clés:** {keywords_display}")

                    if search.get("created_at"):
                        st.caption(f"Créée: {search['created_at']:%d/%m/%Y %H:%M}")

                    # Bouton d'annulation
                    if st.button("❌ Annuler cette recherche", key=f"cancel_{search['id']}"):
                        worker.cancel_search(search["id"])
                        st.success("Recherche annulée")
                        st.rerun()

                st.divider()

    else:
        st.info("🎉 Aucune recherche en cours actuellement.")
        st.markdown("""
        **Pour lancer une recherche en arrière-plan:**
        1. Allez dans **Search Ads**
        2. Configurez vos critères de recherche
        3. Cochez **⏳ Lancer en arrière-plan**
        4. Cliquez sur **Lancer la recherche**

        La recherche continuera même si vous quittez la page.
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SEARCH LOGS
# ═══════════════════════════════════════════════════════════════════════════════

def render_search_logs():
    """Page Historique des Recherches - Logs détaillés de toutes les recherches"""
    st.title("📜 Historique des Recherches")
    st.markdown("Consultez l'historique complet de vos recherches avec les métriques détaillées.")

    db = get_database()
    if not db:
        st.error("Base de données non connectée")
        return

    # S'assurer que les migrations sont exécutées (ajoute les colonnes manquantes)
    from app.database import ensure_tables_exist
    ensure_tables_exist(db)

    # Import des fonctions de log
    from app.database import get_search_logs, get_search_log_detail, get_search_logs_stats, delete_search_log

    # Stats globales
    stats = get_search_logs_stats(db, days=30)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Recherches (30j)", stats.get("total_searches", 0))
    with col2:
        completed = stats.get("by_status", {}).get("completed", 0)
        st.metric("Complétées", completed)
    with col3:
        avg_duration = stats.get("avg_duration_seconds", 0)
        if avg_duration > 60:
            st.metric("Durée moyenne", f"{avg_duration/60:.1f}m")
        else:
            st.metric("Durée moyenne", f"{avg_duration:.1f}s")
    with col4:
        st.metric("Total pages trouvées", stats.get("total_pages_found", 0))

    # Stats API globales
    total_api = (stats.get("total_meta_api_calls", 0) +
                 stats.get("total_scraper_api_calls", 0) +
                 stats.get("total_web_requests", 0))

    if total_api > 0:
        st.markdown("##### Statistiques API (30 jours)")
        api1, api2, api3, api4, api5 = st.columns(5)
        with api1:
            st.metric("Meta API", stats.get("total_meta_api_calls", 0))
        with api2:
            st.metric("ScraperAPI", stats.get("total_scraper_api_calls", 0))
        with api3:
            st.metric("Web Direct", stats.get("total_web_requests", 0))
        with api4:
            st.metric("Rate Limits", stats.get("total_rate_limit_hits", 0))
        with api5:
            cost = stats.get("total_scraper_api_cost", 0)
            st.metric("Coût ScraperAPI", f"${cost:.2f}")

    st.markdown("---")

    # Filtres
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.selectbox(
            "Filtrer par statut",
            options=["Tous", "completed", "preview", "no_results", "failed", "running"],
            index=0
        )
    with col2:
        limit = st.selectbox("Nombre de résultats", options=[20, 50, 100], index=0)

    # Récupérer les logs
    status_param = None if status_filter == "Tous" else status_filter
    logs = get_search_logs(db, limit=limit, status=status_param)

    if not logs:
        st.info("Aucun historique de recherche disponible.")
        return

    st.markdown(f"### {len(logs)} recherche(s)")

    for log in logs:
        log_id = log["id"]
        started = log["started_at"]
        status = log["status"]
        keywords = log["keywords"] or "-"
        duration = log.get("duration_seconds", 0)

        # Status badge
        status_emoji = {
            "completed": "✅",
            "preview": "👁️",
            "failed": "❌",
            "running": "🔄",
            "no_results": "⚠️"
        }.get(status, "❓")

        # Format duration
        if duration:
            if duration > 60:
                duration_str = f"{duration/60:.1f}m"
            else:
                duration_str = f"{duration:.1f}s"
        else:
            duration_str = "-"

        # Format date
        if started:
            date_str = started.strftime("%d/%m/%Y %H:%M")
        else:
            date_str = "-"

        with st.expander(f"{status_emoji} **#{log_id}** - {date_str} - {keywords[:50]}{'...' if len(keywords) > 50 else ''} ({duration_str})"):
            # Métriques principales
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Ads trouvées", log.get("total_ads_found", 0))
            with m2:
                st.metric("Pages trouvées", log.get("total_pages_found", 0))
            with m3:
                st.metric("Pages filtrées", log.get("pages_after_filter", 0))
            with m4:
                st.metric("Winning Ads", log.get("winning_ads_count", 0))

            # ═══ TABLEAUX PAGES ET WINNING ADS (avec historique complet) ═══
            from app.database import get_pages_for_search, get_winning_ads_for_search, get_search_history_stats

            # Récupérer les stats d'historique
            history_stats = get_search_history_stats(db, log_id)

            # Tableau des pages trouvées (utilise les tables d'historique many-to-many)
            pages_from_search = get_pages_for_search(db, log_id, limit=100)
            if pages_from_search:
                new_pages = history_stats.get("new_pages", 0)
                existing_pages = history_stats.get("existing_pages", 0)

                with st.expander(f"📄 **Pages trouvées ({len(pages_from_search)})** — 🆕 {new_pages} nouvelles | 📝 {existing_pages} existantes", expanded=False):
                    # Sélecteur de colonnes
                    all_page_columns = ["Status", "Page", "Site", "CMS", "État", "Ads", "Thématique", "Pays", "Keyword", "Ads (découverte)"]
                    default_page_cols = ["Status", "Page", "Site", "CMS", "État", "Ads"]

                    selected_page_cols = st.multiselect(
                        "Colonnes à afficher",
                        options=all_page_columns,
                        default=default_page_cols,
                        key=f"page_cols_{log_id}"
                    )

                    # Créer DataFrame avec toutes les colonnes disponibles
                    pages_df_data = []
                    for p in pages_from_search:
                        row = {}
                        if "Status" in selected_page_cols:
                            row["Status"] = "🆕 Nouveau" if p.get("was_new") else "📝 Existant"
                        if "Page" in selected_page_cols:
                            row["Page"] = (p.get("page_name") or "")[:30]
                        if "Site" in selected_page_cols:
                            row["Site"] = (p.get("lien_site") or "")[:35]
                        if "CMS" in selected_page_cols:
                            row["CMS"] = p.get("cms", "-")
                        if "État" in selected_page_cols:
                            row["État"] = p.get("etat", "-")
                        if "Ads" in selected_page_cols:
                            row["Ads"] = p.get("nombre_ads_active", 0)
                        if "Thématique" in selected_page_cols:
                            row["Thématique"] = (p.get("thematique") or "-")[:20]
                        if "Pays" in selected_page_cols:
                            row["Pays"] = (p.get("pays") or "-")[:15]
                        if "Keyword" in selected_page_cols:
                            row["Keyword"] = (p.get("keyword_matched") or "-")[:20]
                        if "Ads (découverte)" in selected_page_cols:
                            row["Ads (découverte)"] = p.get("ads_count_at_discovery", 0)

                        if row:
                            pages_df_data.append(row)

                    if pages_df_data:
                        df_pages = pd.DataFrame(pages_df_data)
                        st.dataframe(df_pages, hide_index=True, use_container_width=True)

            # Tableau des winning ads (utilise les tables d'historique many-to-many)
            winning_from_search = get_winning_ads_for_search(db, log_id, limit=100)
            if winning_from_search:
                new_winning = history_stats.get("new_winning_ads", 0)
                existing_winning = history_stats.get("existing_winning_ads", 0)

                with st.expander(f"🏆 **Winning Ads ({len(winning_from_search)})** — 🆕 {new_winning} nouvelles | 📝 {existing_winning} existantes", expanded=False):
                    # Sélecteur de colonnes
                    all_winning_columns = ["Status", "Page", "Âge", "Reach", "Critère", "Site", "Snapshot", "Reach (découverte)", "Âge (découverte)"]
                    default_winning_cols = ["Status", "Page", "Âge", "Reach", "Critère", "Site"]

                    selected_winning_cols = st.multiselect(
                        "Colonnes à afficher",
                        options=all_winning_columns,
                        default=default_winning_cols,
                        key=f"winning_cols_{log_id}"
                    )

                    # Créer DataFrame
                    winning_df_data = []
                    for a in winning_from_search:
                        row = {}
                        if "Status" in selected_winning_cols:
                            row["Status"] = "🆕 Nouveau" if a.get("was_new") else "📝 Existant"
                        if "Page" in selected_winning_cols:
                            row["Page"] = (a.get("page_name") or "")[:25]
                        if "Âge" in selected_winning_cols:
                            row["Âge"] = f"{a.get('ad_age_days', '-')}j" if a.get("ad_age_days") is not None else "-"
                        if "Reach" in selected_winning_cols:
                            reach = a.get("eu_total_reach")
                            row["Reach"] = f"{reach:,}".replace(",", " ") if reach else "-"
                        if "Critère" in selected_winning_cols:
                            row["Critère"] = a.get("matched_criteria", "-")
                        if "Site" in selected_winning_cols:
                            row["Site"] = (a.get("lien_site") or "")[:25]
                        if "Snapshot" in selected_winning_cols:
                            snapshot_url = a.get("ad_snapshot_url", "")
                            row["Snapshot"] = "🔗" if snapshot_url else "-"
                        if "Reach (découverte)" in selected_winning_cols:
                            reach_d = a.get("reach_at_discovery", 0)
                            row["Reach (découverte)"] = f"{reach_d:,}".replace(",", " ") if reach_d else "-"
                        if "Âge (découverte)" in selected_winning_cols:
                            row["Âge (découverte)"] = f"{a.get('age_days_at_discovery', '-')}j"

                        if row:
                            winning_df_data.append(row)

                    if winning_df_data:
                        df_winning = pd.DataFrame(winning_df_data)
                        st.dataframe(df_winning, hide_index=True, use_container_width=True)

            # Paramètres de recherche
            st.markdown("**Paramètres:**")
            param_cols = st.columns(4)
            with param_cols[0]:
                st.caption(f"📍 Pays: {log.get('countries', '-')}")
            with param_cols[1]:
                st.caption(f"🌐 Langues: {log.get('languages', '-')}")
            with param_cols[2]:
                st.caption(f"📊 Min ads: {log.get('min_ads', '-')}")
            with param_cols[3]:
                st.caption(f"🛍️ CMS: {log.get('selected_cms', '-') or 'Tous'}")

            # Mots-clés complets
            st.markdown("**Mots-clés:**")
            st.code(keywords)

            # Détails des phases avec stats
            phases_data = log.get("phases_data", [])
            if phases_data:
                st.markdown("**📊 Détails par phase:**")

                for p in phases_data:
                    phase_num = p.get('num', '?')
                    phase_name = p.get('name', 'N/A')
                    phase_time = p.get("time_formatted", "-")
                    phase_result = p.get("result", "-")
                    phase_stats = p.get("stats", {})

                    # Header de la phase avec expander
                    with st.expander(f"**Phase {phase_num}:** {phase_name} — {phase_result} ({phase_time})", expanded=False):
                        if phase_stats:
                            # Afficher les stats en 2 colonnes
                            stat_items = list(phase_stats.items())
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
                                                display_val = ", ".join(f"{k}: {v}" for k, v in value.items())
                                            else:
                                                display_val = str(value)
                                            st.metric(key, display_val)
                        else:
                            st.caption("Pas de statistiques détaillées pour cette phase")

            # ═══ STATISTIQUES API ═══
            meta_api_calls = log.get("meta_api_calls", 0) or 0
            scraper_api_calls = log.get("scraper_api_calls", 0) or 0
            web_requests = log.get("web_requests", 0) or 0
            total_api_calls = meta_api_calls + scraper_api_calls + web_requests

            if total_api_calls > 0:
                st.markdown("**Statistiques API:**")

                # Ligne 1: Compteurs principaux
                api_cols = st.columns(4)
                with api_cols[0]:
                    st.metric("🔗 Meta API", meta_api_calls)
                with api_cols[1]:
                    st.metric("🌐 ScraperAPI", scraper_api_calls)
                with api_cols[2]:
                    st.metric("📡 Web Direct", web_requests)
                with api_cols[3]:
                    st.metric("📊 Total", total_api_calls)

                # Ligne 2: Erreurs et coûts
                meta_errors = log.get("meta_api_errors", 0) or 0
                scraper_errors = log.get("scraper_api_errors", 0) or 0
                web_errors = log.get("web_errors", 0) or 0
                rate_limits = log.get("rate_limit_hits", 0) or 0
                scraper_cost = log.get("scraper_api_cost", 0) or 0

                err_cols = st.columns(5)
                with err_cols[0]:
                    st.caption(f"❌ Meta erreurs: {meta_errors}")
                with err_cols[1]:
                    st.caption(f"❌ Scraper erreurs: {scraper_errors}")
                with err_cols[2]:
                    st.caption(f"❌ Web erreurs: {web_errors}")
                with err_cols[3]:
                    st.caption(f"⏱️ Rate limits: {rate_limits}")
                with err_cols[4]:
                    st.caption(f"💰 Coût ScraperAPI: ${scraper_cost:.4f}")

                # Détail des erreurs scraper par type (si disponibles)
                scraper_errors_by_type = log.get("scraper_errors_by_type")
                if scraper_errors_by_type and isinstance(scraper_errors_by_type, dict) and len(scraper_errors_by_type) > 0:
                    error_labels = {
                        "timeout": "⏰ Timeout",
                        "403_forbidden": "🚫 403 Bloqué",
                        "404_not_found": "🔍 404 Non trouvé",
                        "429_rate_limit": "⏱️ 429 Rate limit",
                        "500_server_error": "💥 500 Erreur serveur",
                        "502_bad_gateway": "🌐 502 Bad Gateway",
                        "503_unavailable": "🔧 503 Indisponible",
                        "unknown": "❓ Inconnu"
                    }
                    err_details = []
                    for err_type, count in sorted(scraper_errors_by_type.items(), key=lambda x: -x[1]):
                        label = error_labels.get(err_type, f"⚠️ {err_type}")
                        err_details.append(f"{label}: {count}")
                    st.caption("📊 **Détail erreurs scraper:** " + " | ".join(err_details))

                # ═══ LISTE DÉTAILLÉE DES ERREURS ═══
                errors_list = log.get("errors_list", [])
                if errors_list and len(errors_list) > 0:
                    with st.expander(f"🚨 **{len(errors_list)} erreur(s) détaillée(s)**", expanded=False):
                        # Grouper par type d'erreur
                        errors_by_type = {}
                        for err in errors_list:
                            err_type = err.get("type", "unknown")
                            if err_type not in errors_by_type:
                                errors_by_type[err_type] = []
                            errors_by_type[err_type].append(err)

                        # Afficher par type
                        type_icons = {
                            "meta_api": "🔵 Meta API",
                            "scraper_api": "🟠 ScraperAPI",
                            "web": "🌐 Web",
                            "rate_limit": "⏱️ Rate Limit",
                            "unknown": "❓ Autre"
                        }

                        for err_type, errs in errors_by_type.items():
                            type_label = type_icons.get(err_type, f"⚠️ {err_type}")
                            st.markdown(f"**{type_label}** ({len(errs)})")

                            for err in errs[:10]:  # Limiter à 10 par type
                                timestamp = err.get("timestamp", "")
                                message = err.get("message", "Erreur inconnue")[:200]
                                keyword = err.get("keyword", "")
                                url = err.get("url", "")

                                details = []
                                if keyword:
                                    details.append(f"Mot-clé: {keyword}")
                                if url:
                                    details.append(f"URL: {url[:50]}...")
                                if timestamp:
                                    details.append(f"À: {timestamp}")

                                st.error(f"❌ {message}")
                                if details:
                                    st.caption(" | ".join(details))

                            if len(errs) > 10:
                                st.caption(f"... et {len(errs) - 10} autres erreurs de ce type")

                # Ligne 3: Temps moyens
                meta_avg = log.get("meta_api_avg_time", 0) or 0
                scraper_avg = log.get("scraper_api_avg_time", 0) or 0
                web_avg = log.get("web_avg_time", 0) or 0

                time_cols = st.columns(3)
                with time_cols[0]:
                    st.caption(f"⏱️ Meta avg: {meta_avg:.0f}ms")
                with time_cols[1]:
                    st.caption(f"⏱️ Scraper avg: {scraper_avg:.0f}ms")
                with time_cols[2]:
                    st.caption(f"⏱️ Web avg: {web_avg:.0f}ms")

                # Détails par mot-clé (si disponibles)
                api_details = log.get("api_details")
                if api_details and isinstance(api_details, dict) and len(api_details) > 0:
                    with st.expander("📋 Détails par mot-clé"):
                        details_table = []
                        for kw, kw_stats in api_details.items():
                            details_table.append({
                                "Mot-clé": kw[:30] + "..." if len(kw) > 30 else kw,
                                "Appels": kw_stats.get("calls", 0),
                                "Ads": kw_stats.get("ads_found", 0),
                                "Erreurs": kw_stats.get("errors", 0),
                                "Temps (ms)": f"{kw_stats.get('time_ms', 0):.0f}"
                            })
                        if details_table:
                            df_details = pd.DataFrame(details_table)
                            st.dataframe(df_details, hide_index=True, width="stretch")

            # Message d'erreur ou d'avertissement
            if status == "failed" and log.get("error_message"):
                st.error(f"Erreur: {log.get('error_message')}")
            elif status == "no_results":
                # Afficher la raison pour les recherches sans résultats
                error_msg = log.get("error_message")
                if error_msg:
                    st.warning(f"⚠️ {error_msg}")
                else:
                    # Message par défaut si pas d'erreur spécifique
                    total_ads = log.get("total_ads_found", 0)
                    pages_found = log.get("total_pages_found", 0)
                    pages_filtered = log.get("pages_after_filter", 0)
                    min_ads = log.get("min_ads", 0)

                    if total_ads == 0:
                        st.warning("⚠️ Aucune publicité trouvée pour ces mots-clés dans les pays/langues sélectionnés")
                    elif pages_found == 0:
                        st.warning("⚠️ Publicités trouvées mais aucune page n'a pu être extraite")
                    elif pages_filtered == 0:
                        st.warning(f"⚠️ {pages_found} pages trouvées mais aucune ne correspond aux filtres (min {min_ads} ads, CMS: {log.get('selected_cms', 'Tous')})")

            # Détails supplémentaires
            with st.columns([3, 1])[1]:
                if st.button("🗑️ Supprimer", key=f"del_log_{log_id}"):
                    delete_search_log(db, log_id)
                    st.success("Log supprimé")
                    st.rerun()


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

    # Initialiser le worker de recherches en arrière-plan
    try:
        from app.background_worker import init_worker
        from app.database import recover_interrupted_searches, DatabaseManager, ensure_tables_exist

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

    # Router
    page = st.session_state.current_page

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
