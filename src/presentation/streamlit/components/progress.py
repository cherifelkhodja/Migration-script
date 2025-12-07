"""
Composants de progression pour le suivi des recherches.

Ce module fournit SearchProgressTracker pour afficher la progression
des recherches multi-phases dans l'interface Streamlit.

Version complète avec:
- Layout deux colonnes (progression + stats en temps réel)
- Calcul ETA
- Logs détaillés avec horodatage
- Résumé final avec tableau et statistiques API
"""
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import streamlit as st
import pandas as pd


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
            from src.infrastructure.adapters.api_tracker import clear_current_tracker
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
                st.dataframe(df, hide_index=True, use_container_width=True)

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
