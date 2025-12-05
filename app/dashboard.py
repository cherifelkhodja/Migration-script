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
    DEFAULT_STATE_THRESHOLDS, WINNING_AD_CRITERIA
)
from app.meta_api import MetaAdsClient, extract_website_from_ads, extract_currency_from_ads
from app.shopify_detector import detect_cms_from_url
from app.web_analyzer import analyze_website_complete
from app.utils import load_blacklist, is_blacklisted
from app.database import (
    DatabaseManager, save_pages_recherche, save_suivi_page,
    save_ads_recherche, get_suivi_stats, search_pages, get_suivi_history,
    get_evolution_stats, get_page_evolution_history, get_etat_from_ads_count,
    add_to_blacklist, remove_from_blacklist, get_blacklist, get_blacklist_ids,
    is_winning_ad, save_winning_ads, get_winning_ads, get_winning_ads_stats,
    get_all_pages, get_winning_ads_by_page
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
        }
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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


def generate_alerts(db: DatabaseManager) -> list:
    """
    Génère des alertes basées sur les données

    Returns:
        Liste d'alertes avec type, message, data
    """
    alerts = []

    try:
        # Alerte: Nouvelles pages XXL
        xxl_pages = search_pages(db, etat="XXL", limit=50)
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

        # Alerte: Winning ads récentes
        winning_stats = get_winning_ads_stats(db, days=1)
        if winning_stats.get("total", 0) > 0:
            alerts.append({
                "type": "success",
                "icon": "🏆",
                "title": f"{winning_stats['total']} winning ad(s) aujourd'hui",
                "message": f"Reach moyen: {winning_stats.get('avg_reach', 0):,}",
                "data": winning_stats.get("by_page", [])[:5]
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
        st.markdown("## 📊 Meta Ads Analyzer")

        # Global Search
        search_query = st.text_input(
            "🔍 Recherche rapide",
            placeholder="Nom, site, page_id...",
            key="global_search"
        )
        if search_query and len(search_query) >= 2:
            db = get_database()
            if db:
                results = search_pages(db, search_term=search_query, limit=5)
                if results:
                    st.caption(f"{len(results)} résultat(s)")
                    for r in results:
                        if st.button(f"→ {r.get('page_name', 'N/A')[:25]}", key=f"sr_{r['page_id']}"):
                            st.session_state.selected_page_id = r['page_id']
                            st.session_state.current_page = "Pages / Shops"
                            st.rerun()
                else:
                    st.caption("Aucun résultat")

        st.markdown("---")

        # Main Navigation
        st.markdown("### Main")

        if st.button("🏠 Dashboard", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Dashboard" else "secondary"):
            st.session_state.current_page = "Dashboard"
            st.rerun()

        if st.button("🔍 Search Ads", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Search Ads" else "secondary"):
            st.session_state.current_page = "Search Ads"
            st.rerun()

        if st.button("🏪 Pages / Shops", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Pages / Shops" else "secondary"):
            st.session_state.current_page = "Pages / Shops"
            st.rerun()

        if st.button("📋 Watchlists", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Watchlists" else "secondary"):
            st.session_state.current_page = "Watchlists"
            st.rerun()

        if st.button("🔔 Alerts", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Alerts" else "secondary"):
            st.session_state.current_page = "Alerts"
            st.rerun()

        st.markdown("---")
        st.markdown("### More")

        if st.button("📈 Monitoring", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Monitoring" else "secondary"):
            st.session_state.current_page = "Monitoring"
            st.rerun()

        if st.button("📊 Analytics", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
            st.session_state.current_page = "Analytics"
            st.rerun()

        if st.button("🏆 Winning Ads", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Winning Ads" else "secondary"):
            st.session_state.current_page = "Winning Ads"
            st.rerun()

        if st.button("🚫 Blacklist", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Blacklist" else "secondary"):
            st.session_state.current_page = "Blacklist"
            st.rerun()

        if st.button("⚙️ Settings", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Settings" else "secondary"):
            st.session_state.current_page = "Settings"
            st.rerun()

        # Database status
        st.markdown("---")
        db = get_database()
        if db:
            st.success("🟢 Database connected")
        else:
            st.error("🔴 Database offline")


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

    try:
        stats = get_suivi_stats(db)
        winning_stats = get_winning_ads_stats(db, days=7)
        winning_by_page = get_winning_ads_by_page(db, days=30)

        # KPIs principaux avec trends
        col1, col2, col3, col4, col5 = st.columns(5)

        total_pages = stats.get("total_pages", 0)
        etats = stats.get("etats", {})
        cms_stats = stats.get("cms", {})

        actives = sum(v for k, v in etats.items() if k != "inactif")
        shopify_count = cms_stats.get("Shopify", 0)
        xxl_count = etats.get("XXL", 0)
        winning_total = winning_stats.get("total", 0)

        col1.metric("📄 Total Pages", total_pages)
        col2.metric("✅ Actives", actives)
        col3.metric("🚀 XXL (≥150)", xxl_count)
        col4.metric("🛒 Shopify", shopify_count)
        col5.metric("🏆 Winning (7j)", winning_total)

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
                    st.plotly_chart(fig, key="dash_etats", use_container_width=True)
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
                st.plotly_chart(fig, key="dash_cms", use_container_width=True)
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

            df = pd.DataFrame(top_pages)
            cols_to_show = ["page_name", "cms", "etat", "nombre_ads_active", "winning_count", "score_display"]
            col_names = ["Nom", "CMS", "État", "Ads", "🏆 Winning", "Score"]
            df_display = df[[c for c in cols_to_show if c in df.columns]]
            df_display.columns = col_names[:len(df_display.columns)]
            st.dataframe(df_display, use_container_width=True, hide_index=True)

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
    st.markdown("Rechercher et analyser des annonces Meta")

    # Vérifier si on a des résultats en aperçu à afficher
    if st.session_state.get("show_preview_results", False):
        render_preview_results()
        return

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
    # Configuration de recherche
    with st.expander("⚙️ Configuration de recherche", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            token = st.text_input(
                "Token Meta API",
                type="password",
                value=os.getenv("META_ACCESS_TOKEN", ""),
                help="Votre token d'accès Meta Ads API",
                key="token_keyword"
            )

            keywords_input = st.text_area(
                "Mots-clés (un par ligne)",
                placeholder="dropshipping\necommerce\nboutique",
                height=100
            )
            keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]

        with col2:
            countries = st.multiselect(
                "Pays cibles",
                options=list(AVAILABLE_COUNTRIES.keys()),
                default=DEFAULT_COUNTRIES,
                format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
                key="countries_keyword"
            )

            languages = st.multiselect(
                "Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=DEFAULT_LANGUAGES,
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_keyword"
            )

            min_ads = st.slider("Min. ads pour inclusion", 1, 50, MIN_ADS_INITIAL, key="min_ads_keyword")

    # CMS Filter
    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
    selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=cms_options, key="cms_keyword")

    # Mode aperçu
    st.markdown("---")
    preview_mode = st.checkbox(
        "📋 Mode aperçu (ne pas enregistrer en BDD)",
        help="Permet de voir les résultats avant de les enregistrer, et de blacklister des pages",
        key="preview_keyword"
    )

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche", type="primary", use_container_width=True, key="btn_keyword"):
        if not token:
            st.error("Token Meta API requis !")
            return
        if not keywords:
            st.error("Au moins un mot-clé requis !")
            return

        run_search_process(token, keywords, countries, languages, min_ads, selected_cms, preview_mode)


def render_page_id_search():
    """Recherche par Page IDs (optimisée par batch de 10)"""
    st.info("⚡ Optimisation: les Page IDs sont traités par batch de 10 pour économiser les requêtes API")

    with st.expander("⚙️ Configuration de recherche", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            token = st.text_input(
                "Token Meta API",
                type="password",
                value=os.getenv("META_ACCESS_TOKEN", ""),
                help="Votre token d'accès Meta Ads API",
                key="token_pageid"
            )

            page_ids_input = st.text_area(
                "Page IDs (un par ligne)",
                placeholder="123456789\n987654321\n456789123",
                height=150,
                help="Entrez les Page IDs Facebook, un par ligne"
            )
            page_ids = [pid.strip() for pid in page_ids_input.split("\n") if pid.strip()]

        with col2:
            countries = st.multiselect(
                "Pays cibles",
                options=list(AVAILABLE_COUNTRIES.keys()),
                default=DEFAULT_COUNTRIES,
                format_func=lambda x: f"{x} - {AVAILABLE_COUNTRIES[x]}",
                key="countries_pageid"
            )

            languages = st.multiselect(
                "Langues",
                options=list(AVAILABLE_LANGUAGES.keys()),
                default=DEFAULT_LANGUAGES,
                format_func=lambda x: f"{x} - {AVAILABLE_LANGUAGES[x]}",
                key="languages_pageid"
            )

    # CMS Filter
    cms_options = ["Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Squarespace", "BigCommerce", "Webflow", "Autre/Inconnu"]
    selected_cms = st.multiselect("CMS à inclure", options=cms_options, default=cms_options, key="cms_pageid")

    # Mode aperçu
    st.markdown("---")
    preview_mode = st.checkbox(
        "📋 Mode aperçu (ne pas enregistrer en BDD)",
        help="Permet de voir les résultats avant de les enregistrer, et de blacklister des pages",
        key="preview_pageid"
    )

    # Stats
    if page_ids:
        batch_count = (len(page_ids) + 9) // 10
        st.caption(f"📊 {len(page_ids)} Page IDs → {batch_count} requêtes API")

    # Bouton de recherche
    if st.button("🚀 Lancer la recherche par Page IDs", type="primary", use_container_width=True, key="btn_pageid"):
        if not token:
            st.error("Token Meta API requis !")
            return
        if not page_ids:
            st.error("Au moins un Page ID requis !")
            return

        run_page_id_search(token, page_ids, countries, languages, selected_cms, preview_mode)


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
        if st.button("💾 Sauvegarder en base de données", type="primary", use_container_width=True):
            if db:
                try:
                    thresholds = st.session_state.get("state_thresholds", None)
                    languages = st.session_state.get("languages", ["fr"])
                    pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                    det = st.session_state.get("detection_thresholds", {})
                    suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI))
                    ads_saved = save_ads_recherche(db, pages_final, st.session_state.get("page_ads", {}), countries, det.get("min_ads_liste", MIN_ADS_LISTE))
                    winning_ads_data = st.session_state.get("winning_ads_data", [])
                    winning_saved = save_winning_ads(db, winning_ads_data, pages_final)

                    st.success(f"✓ Sauvegardé : {pages_saved} pages, {suivi_saved} suivi, {ads_saved} ads, {winning_saved} winning")
                    st.session_state.show_preview_results = False
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur sauvegarde: {e}")

    with col2:
        if st.button("🔙 Nouvelle recherche", use_container_width=True):
            st.session_state.show_preview_results = False
            st.session_state.pages_final = {}
            st.session_state.web_results = {}
            st.rerun()


def run_search_process(token, keywords, countries, languages, min_ads, selected_cms, preview_mode=False):
    """Exécute le processus de recherche complet"""
    client = MetaAdsClient(token)
    db = get_database()

    # Récupérer la blacklist
    blacklist_ids = set()
    if db:
        blacklist_ids = get_blacklist_ids(db)
        if blacklist_ids:
            st.info(f"🚫 {len(blacklist_ids)} pages en blacklist seront ignorées")

    # Phase 1: Recherche
    st.subheader("🔍 Phase 1: Recherche par mots-clés")
    all_ads = []
    seen_ad_ids = set()
    progress = st.progress(0)

    for i, kw in enumerate(keywords):
        st.text(f"Recherche: '{kw}'...")
        ads = client.search_ads(kw, countries, languages)
        for ad in ads:
            ad_id = ad.get("id")
            if ad_id and ad_id not in seen_ad_ids:
                ad["_keyword"] = kw
                all_ads.append(ad)
                seen_ad_ids.add(ad_id)
        progress.progress((i + 1) / len(keywords))

    st.success(f"✓ {len(all_ads)} annonces trouvées")

    # Phase 2: Regroupement
    st.subheader("📋 Phase 2: Regroupement par page")
    pages = {}
    page_ads = defaultdict(list)
    name_counter = defaultdict(Counter)

    for ad in all_ads:
        pid = ad.get("page_id")
        if not pid:
            continue

        # Ignorer les pages blacklistées
        if str(pid) in blacklist_ids:
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
    st.success(f"✓ {len(pages_filtered)} pages avec ≥{min_ads} ads")

    if not pages_filtered:
        st.warning("Aucune page trouvée avec assez d'ads")
        return

    # Phase 3: Extraction sites
    st.subheader("🌐 Phase 3: Extraction des sites web")
    progress = st.progress(0)
    for i, (pid, data) in enumerate(pages_filtered.items()):
        data["website"] = extract_website_from_ads(page_ads.get(pid, []))
        progress.progress((i + 1) / len(pages_filtered))

    sites_found = sum(1 for d in pages_filtered.values() if d["website"])
    st.success(f"✓ {sites_found} sites extraits")

    # Phase 4: Détection CMS
    st.subheader("🔍 Phase 4: Détection CMS")
    pages_with_sites = {pid: data for pid, data in pages_filtered.items() if data["website"]}
    progress = st.progress(0)

    for i, (pid, data) in enumerate(pages_with_sites.items()):
        cms_result = detect_cms_from_url(data["website"])
        data["cms"] = cms_result["cms"]
        data["is_shopify"] = cms_result["is_shopify"]
        progress.progress((i + 1) / len(pages_with_sites))
        time.sleep(0.1)

    # Filter by CMS
    def cms_matches(cms_name):
        if cms_name in selected_cms:
            return True
        if "Autre/Inconnu" in selected_cms and cms_name not in cms_options[:-1]:
            return True
        return False

    pages_with_cms = {pid: data for pid, data in pages_with_sites.items() if cms_matches(data.get("cms", "Unknown"))}
    st.success(f"✓ {len(pages_with_cms)} pages avec CMS sélectionnés")

    # Phase 5: Comptage (optimisé par batch de 10)
    st.subheader("📊 Phase 5: Comptage des annonces")
    progress = st.progress(0)

    # Traiter par batch de 10 pages pour économiser les requêtes API
    page_ids_list = list(pages_with_cms.keys())
    batch_size = 10
    total_batches = (len(page_ids_list) + batch_size - 1) // batch_size

    st.caption(f"⚡ Optimisation: {len(page_ids_list)} pages en {total_batches} requêtes (batch de {batch_size})")

    processed = 0
    for batch_idx in range(0, len(page_ids_list), batch_size):
        batch_pids = page_ids_list[batch_idx:batch_idx + batch_size]

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
            progress.progress(processed / len(page_ids_list))

        time.sleep(0.2)  # Pause entre les batches

    pages_final = {pid: data for pid, data in pages_with_cms.items() if data["ads_active_total"] >= min_ads}
    st.success(f"✓ {len(pages_final)} pages finales")

    # Phase 6: Analyse web
    st.subheader("🔬 Phase 6: Analyse des sites web")
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

    # Phase 7: Détection des Winning Ads
    st.subheader("🏆 Phase 7: Détection des Winning Ads")
    scan_date = datetime.now()
    winning_ads_data = []
    winning_ads_by_page = {}  # {page_id: count}

    progress = st.progress(0)
    total_ads_checked = 0

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
            total_ads_checked += 1

        if page_winning_count > 0:
            winning_ads_by_page[pid] = page_winning_count
            data["winning_ads_count"] = page_winning_count

        progress.progress((i + 1) / len(pages_final))

    st.success(f"✓ {len(winning_ads_data)} winning ads détectées sur {len(winning_ads_by_page)} pages")

    # Save to session first (needed for preview mode)
    st.session_state.pages_final = pages_final
    st.session_state.web_results = web_results
    st.session_state.page_ads = dict(page_ads)
    st.session_state.winning_ads_data = winning_ads_data
    st.session_state.countries = countries
    st.session_state.languages = languages
    st.session_state.preview_mode = preview_mode

    if preview_mode:
        # Mode aperçu - rediriger vers la page d'aperçu
        st.success(f"✓ Recherche terminée ! {len(pages_final)} pages trouvées")
        st.session_state.show_preview_results = True
        st.rerun()
    else:
        # Mode normal - sauvegarder directement
        st.subheader("💾 Phase 8: Sauvegarde en base de données")

        if db:
            try:
                thresholds = st.session_state.get("state_thresholds", None)
                pages_saved = save_pages_recherche(db, pages_final, web_results, countries, languages, thresholds)
                det = st.session_state.get("detection_thresholds", {})
                suivi_saved = save_suivi_page(db, pages_final, web_results, det.get("min_ads_suivi", MIN_ADS_SUIVI))
                ads_saved = save_ads_recherche(db, pages_final, dict(page_ads), countries, det.get("min_ads_liste", MIN_ADS_LISTE))
                winning_saved = save_winning_ads(db, winning_ads_data, pages_final)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Pages", pages_saved)
                col2.metric("Suivi", suivi_saved)
                col3.metric("Annonces", ads_saved)
                col4.metric("🏆 Winning", winning_saved)
                st.success("✓ Données sauvegardées !")
            except Exception as e:
                st.error(f"Erreur sauvegarde: {e}")

        st.balloons()
        st.success("🎉 Recherche terminée !")


def run_page_id_search(token, page_ids, countries, languages, selected_cms, preview_mode=False):
    """Exécute la recherche par Page IDs (optimisée par batch de 10)"""
    client = MetaAdsClient(token)
    db = get_database()

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

        time.sleep(0.2)  # Pause entre les batches

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
        time.sleep(0.1)

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
                winning_saved = save_winning_ads(db, winning_ads_data, pages_final)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Pages", pages_saved)
                col2.metric("Suivi", suivi_saved)
                col3.metric("Annonces", ads_saved)
                col4.metric("🏆 Winning", winning_saved)
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

    # Filtres
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search_term = st.text_input("🔍 Rechercher", placeholder="Nom ou site...")

    with col2:
        cms_filter = st.selectbox("CMS", ["Tous", "Shopify", "WooCommerce", "PrestaShop", "Magento", "Wix", "Unknown"])

    with col3:
        etat_filter = st.selectbox("État", ["Tous", "XXL", "XL", "L", "M", "S", "XS", "inactif"])

    with col4:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    # Mode d'affichage et export
    col_mode, col_export = st.columns([3, 1])
    with col_mode:
        view_mode = st.radio("Mode d'affichage", ["Tableau", "Détaillé"], horizontal=True)

    # Recherche
    try:
        results = search_pages(
            db,
            cms=cms_filter if cms_filter != "Tous" else None,
            etat=etat_filter if etat_filter != "Tous" else None,
            search_term=search_term if search_term else None,
            limit=limit
        )

        if results:
            # Enrichir avec scores et winning ads
            winning_by_page = get_winning_ads_by_page(db, limit=1000)
            winning_counts = {str(w["page_id"]): w["count"] for w in winning_by_page}

            for page in results:
                pid = str(page.get("page_id", ""))
                winning_count = winning_counts.get(pid, 0)
                page["winning_ads"] = winning_count
                page["score"] = calculate_page_score(page, winning_count)

            # Trier par score
            results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

            # Export CSV
            with col_export:
                export_data = [{
                    "Page ID": p.get("page_id", ""),
                    "Nom": p.get("page_name", ""),
                    "Site": p.get("lien_site", ""),
                    "CMS": p.get("cms", ""),
                    "État": p.get("etat", ""),
                    "Ads": p.get("nombre_ads_active", 0),
                    "Winning Ads": p.get("winning_ads", 0),
                    "Produits": p.get("nombre_produits", 0),
                    "Score": p.get("score", 0),
                    "Keywords": p.get("keywords", ""),
                    "Thématique": p.get("thematique", ""),
                    "Ads Library": p.get("lien_fb_ad_library", "")
                } for p in results]

                csv_data = export_to_csv(export_data)
                st.download_button(
                    "📥 Export CSV",
                    csv_data,
                    file_name=f"pages_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )

            st.markdown(f"**{len(results)} résultats**")

            if view_mode == "Tableau":
                df = pd.DataFrame(results)

                # Ajouter colonne Score visuel
                df["score_display"] = df.apply(
                    lambda r: f"{get_score_color(r.get('score', 0))} {r.get('score', 0)}", axis=1
                )

                # Colonnes à afficher
                display_cols = ["score_display", "page_name", "lien_site", "cms", "etat", "nombre_ads_active", "winning_ads", "nombre_produits"]
                df_display = df[[c for c in display_cols if c in df.columns]]

                # Renommer colonnes
                col_names = ["Score", "Nom", "Site", "CMS", "État", "Ads", "🏆", "Produits"]
                df_display.columns = col_names[:len(df_display.columns)]

                st.dataframe(
                    df_display,
                    use_container_width=True,
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
                            st.write(f"**Site:** {page.get('lien_site', 'N/A')}")
                            st.write(f"**CMS:** {page.get('cms', 'N/A')} | **Produits:** {page.get('nombre_produits', 0)}")
                            st.write(f"**Score:** {score}/100 | **Winning Ads:** {winning}")
                            if page.get('keywords'):
                                st.write(f"**Keywords:** {page.get('keywords', '')}")
                            if page.get('thematique'):
                                st.write(f"**Thématique:** {page.get('thematique', '')}")

                        with col2:
                            pid = page.get('page_id')
                            if page.get('lien_fb_ad_library'):
                                st.link_button("📘 Ads Library", page['lien_fb_ad_library'])

                            # Bouton copie Page ID
                            st.code(pid, language=None)

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

    # Suivi des pages performantes
    st.subheader("🌟 Top Performers (≥80 ads)")
    try:
        top_pages = search_pages(db, etat="XXL", limit=20)
        top_pages.extend(search_pages(db, etat="XL", limit=20))

        if top_pages:
            df = pd.DataFrame(top_pages)
            cols = ["page_name", "lien_site", "cms", "etat", "nombre_ads_active"]
            df_display = df[[c for c in cols if c in df.columns]].head(20)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune page XXL/XL trouvée")
    except Exception as e:
        st.error(f"Erreur: {e}")

    st.markdown("---")

    # Shopify uniquement
    st.subheader("🛒 Shopify Stores")
    try:
        shopify_pages = search_pages(db, cms="Shopify", limit=30)
        if shopify_pages:
            df = pd.DataFrame(shopify_pages)
            cols = ["page_name", "lien_site", "etat", "nombre_ads_active", "nombre_produits"]
            df_display = df[[c for c in cols if c in df.columns]]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune boutique Shopify trouvée")
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

    try:
        alerts = generate_alerts(db)

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
                                    st.write(f"  • {name}")

                elif alert["type"] == "warning":
                    with st.expander(f"⚠️ {alert['icon']} {alert['title']}", expanded=True):
                        st.warning(alert["message"])
                        if alert.get("data"):
                            for item in alert["data"][:5]:
                                if isinstance(item, dict):
                                    name = item.get("page_name") or item.get("nom_site", "N/A")
                                    delta = item.get("pct_ads", 0)
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
            if st.button("📈 Rechercher pages en croissance", use_container_width=True):
                trends = detect_trends(db, days=7)
                if trends["rising"]:
                    st.success(f"{len(trends['rising'])} page(s) en forte croissance")
                    for t in trends["rising"]:
                        st.write(f"🚀 **{t['nom_site']}** +{t['pct_ads']:.0f}%")
                else:
                    st.info("Aucune page en forte croissance")

        with col2:
            if st.button("📉 Rechercher pages en déclin", use_container_width=True):
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
                    st.plotly_chart(fig, key="monitoring_page_chart", use_container_width=True)

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
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun historique trouvé pour cette page")
        except Exception as e:
            st.error(f"Erreur: {e}")


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
                st.plotly_chart(fig, key="analytics_states", use_container_width=True)
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
                st.plotly_chart(fig, key="analytics_cms", use_container_width=True)
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
                st.plotly_chart(fig, key="analytics_themes", use_container_width=True)
        else:
            st.info("Aucune donnée disponible")

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

    # Filtres
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        period = st.selectbox(
            "📅 Période",
            options=[7, 14, 30, 60, 90],
            format_func=lambda x: f"{x} jours",
            index=2
        )

    with col2:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    with col3:
        sort_by = st.selectbox(
            "Trier par",
            options=["Reach", "Date de scan", "Âge de l'ad"],
            index=0
        )

    with col4:
        dedup_mode = st.selectbox(
            "Dédupliquer",
            options=["Aucune", "Par Ad ID", "Par Page"],
            index=0,
            help="Par Ad ID: 1 seule entrée par ad. Par Page: 1 meilleure ad par page."
        )

    try:
        # Statistiques globales
        stats = get_winning_ads_stats(db, days=period)

        st.markdown("---")
        st.subheader("📊 Statistiques")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏆 Total Winning Ads", stats.get("total", 0))
        col2.metric("📄 Pages avec Winning", len(stats.get("by_page", [])))
        col3.metric("📈 Reach moyen", f"{stats.get('avg_reach', 0):,}")

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
                st.plotly_chart(fig, key="winning_by_criteria", use_container_width=True)

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
                    st.dataframe(df_pages, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune page avec winning ads")

        # Liste des winning ads
        st.markdown("---")

        winning_ads = get_winning_ads(db, limit=limit, days=period)

        if winning_ads:
            # Appliquer la déduplication AVANT l'export
            if dedup_mode == "Par Ad ID":
                seen_ids = set()
                deduped = []
                for ad in winning_ads:
                    ad_id = ad.get("ad_id")
                    if ad_id not in seen_ids:
                        seen_ids.add(ad_id)
                        deduped.append(ad)
                winning_ads = deduped

            elif dedup_mode == "Par Page":
                # Garder la meilleure ad par page (plus haut reach)
                best_by_page = {}
                for ad in winning_ads:
                    pid = ad.get("page_id")
                    reach = ad.get("eu_total_reach", 0) or 0
                    if pid not in best_by_page or reach > (best_by_page[pid].get("eu_total_reach", 0) or 0):
                        best_by_page[pid] = ad
                winning_ads = list(best_by_page.values())
                # Re-trier par reach
                winning_ads = sorted(winning_ads, key=lambda x: x.get("eu_total_reach", 0) or 0, reverse=True)

            # Header avec export
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("📋 Liste des Winning Ads")
            with col2:
                # Préparer données pour export (déjà dédupliquées)
                export_data = []
                for ad in winning_ads:
                    export_data.append({
                        "page_name": ad.get("page_name", ""),
                        "page_id": ad.get("page_id", ""),
                        "ad_id": ad.get("ad_id", ""),
                        "reach": ad.get("eu_total_reach", 0),
                        "age_days": ad.get("ad_age_days", 0),
                        "criteria": ad.get("matched_criteria", ""),
                        "ad_text": (ad.get("ad_creative_bodies", "") or "")[:200],
                        "site": ad.get("lien_site", ""),
                        "ad_url": ad.get("ad_snapshot_url", ""),
                        "scan_date": ad.get("date_scan").strftime("%Y-%m-%d") if ad.get("date_scan") else ""
                    })
                csv_data = export_to_csv(export_data)
                dedup_suffix = f"_{dedup_mode.lower().replace(' ', '_')}" if dedup_mode != "Aucune" else ""
                st.download_button(
                    "📥 Export CSV",
                    csv_data,
                    f"winning_ads_{period}j{dedup_suffix}.csv",
                    "text/csv",
                    key="export_winning"
                )

            dedup_info = f" (dédupliqué: {dedup_mode})" if dedup_mode != "Aucune" else ""
            st.info(f"🏆 {len(winning_ads)} winning ads trouvées{dedup_info}")

            for ad in winning_ads:
                reach_formatted = f"{ad.get('eu_total_reach', 0):,}" if ad.get('eu_total_reach') else "N/A"
                age = ad.get('ad_age_days', 'N/A')
                criteria = ad.get('matched_criteria', 'N/A')

                with st.expander(f"🏆 **{ad.get('page_name', 'N/A')}** - {reach_formatted} reach ({criteria})"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        # Texte de l'annonce
                        bodies = ad.get('ad_creative_bodies', '')
                        if bodies:
                            st.markdown("**Texte de l'annonce:**")
                            st.text(bodies[:500] + "..." if len(bodies) > 500 else bodies)

                        # Liens
                        captions = ad.get('ad_creative_link_captions', '')
                        if captions:
                            st.markdown(f"**Caption:** {captions}")

                        titles = ad.get('ad_creative_link_titles', '')
                        if titles:
                            st.markdown(f"**Titre:** {titles}")

                    with col2:
                        st.metric("📈 Reach", reach_formatted)
                        st.metric("📅 Âge", f"{age} jours" if age else "N/A")
                        st.metric("🎯 Critère", criteria)

                        # Date de création
                        creation = ad.get('ad_creation_time')
                        if creation:
                            st.caption(f"Créé: {creation.strftime('%Y-%m-%d')}")

                        # Date de scan
                        scan = ad.get('date_scan')
                        if scan:
                            st.caption(f"Scanné: {scan.strftime('%Y-%m-%d %H:%M')}")

                        # Liens
                        if ad.get('ad_snapshot_url'):
                            st.link_button("🔗 Voir l'annonce", ad['ad_snapshot_url'])

                        if ad.get('lien_site'):
                            st.link_button("🌐 Site", ad['lien_site'])

                        # Copie rapide (code box avec bouton copie intégré)
                        st.caption("📋 Page ID:")
                        st.code(ad.get('page_id', ''), language=None)

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

    # API Settings
    st.subheader("🔑 API Configuration")

    token = st.text_input(
        "Meta API Token",
        type="password",
        value=os.getenv("META_ACCESS_TOKEN", ""),
        help="Token d'accès Meta Ads API"
    )

    if token:
        st.success("✓ Token configuré")
    else:
        st.warning("⚠️ Token non configuré")

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
    st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

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
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
