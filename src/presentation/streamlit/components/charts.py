"""
Composants de graphiques pour le dashboard Streamlit.

Ce module contient les fonctions de création de graphiques
utilisant Plotly pour le dashboard.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE STYLE
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


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSANTS D'INFO
# ═══════════════════════════════════════════════════════════════════════════════

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
            # Échapper les apostrophes pour éviter de casser l'attribut HTML
            safe_help = help_text.replace("'", "&#39;")
            st.markdown(f"<span title='{safe_help}' style='cursor: help; font-size: 18px;'>ℹ️</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"**{title}**")
        if subtitle:
            st.caption(subtitle)


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ═══════════════════════════════════════════════════════════════════════════════

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
