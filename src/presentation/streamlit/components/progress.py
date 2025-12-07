"""
Composants de progression pour le suivi des recherches.

Ce module fournit SearchProgressTracker pour afficher la progression
des recherches multi-phases dans l'interface Streamlit.
"""
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import streamlit as st


class SearchProgressTracker:
    """
    Tracker de progression pour les recherches multi-phases.

    Affiche une interface de progression avec:
    - Barre de progression globale
    - Phases numerotees avec statut
    - Details en temps reel
    - Metriques finales

    Usage:
        tracker = SearchProgressTracker(container, db=db, log_id=log_id)
        tracker.start_phase(1, "Recherche", total_phases=8)
        tracker.update_step("Etape", 1, 10)
        tracker.complete_phase("10 resultats")
        tracker.show_summary()
    """

    def __init__(
        self,
        container,
        db=None,
        log_id: int = None,
        api_tracker=None
    ):
        """
        Initialise le tracker de progression.

        Args:
            container: Container Streamlit pour l'affichage
            db: Instance DatabaseManager (optionnel)
            log_id: ID du log de recherche (optionnel)
            api_tracker: Tracker d'appels API (optionnel)
        """
        self.container = container
        self.db = db
        self.log_id = log_id
        self.api_tracker = api_tracker

        self.start_time = time.time()
        self.current_phase = 0
        self.total_phases = 8
        self.phases_completed: List[Dict] = []
        self.metrics: Dict[str, Any] = {}
        self.detail_logs: List[str] = []

        # Placeholders Streamlit
        self.progress_bar = None
        self.status_text = None
        self.phase_container = None
        self.detail_container = None

        self._init_ui()

    def _init_ui(self):
        """Initialise les elements UI."""
        with self.container:
            self.progress_bar = st.progress(0)
            self.status_text = st.empty()
            self.phase_container = st.container()
            self.detail_container = st.empty()

    def start_phase(self, phase_num: int, name: str, total_phases: int = 8):
        """
        Demarre une nouvelle phase.

        Args:
            phase_num: Numero de la phase (1-indexed)
            name: Nom de la phase
            total_phases: Nombre total de phases
        """
        self.current_phase = phase_num
        self.total_phases = total_phases
        self.phase_start_time = time.time()

        # Mettre a jour la barre de progression
        progress = (phase_num - 1) / total_phases
        self.progress_bar.progress(progress)
        self.status_text.markdown(f"**Phase {phase_num}/{total_phases}:** {name}")

        # Ajouter a la liste des phases
        self.phases_completed.append({
            "phase": phase_num,
            "name": name,
            "status": "running",
            "start_time": time.time(),
        })

    def update_step(
        self,
        step_name: str,
        current: int,
        total: int,
        detail: str = None
    ):
        """
        Met a jour la progression d'une etape dans la phase courante.

        Args:
            step_name: Nom de l'etape
            current: Progression actuelle
            total: Total a atteindre
            detail: Detail optionnel a afficher
        """
        # Calculer la progression intra-phase
        phase_progress = current / total if total > 0 else 0
        base_progress = (self.current_phase - 1) / self.total_phases
        phase_weight = 1 / self.total_phases
        overall_progress = base_progress + (phase_progress * phase_weight)

        self.progress_bar.progress(min(overall_progress, 1.0))

        msg = f"**{step_name}:** {current}/{total}"
        if detail:
            msg += f" - {detail}"
        self.status_text.markdown(msg)

    def log_detail(
        self,
        log_type: str,
        message: str,
        count: int = None,
        total_so_far: int = None
    ):
        """
        Ajoute un log de detail.

        Args:
            log_type: Type de log (keyword, error, etc.)
            message: Message a logger
            count: Compteur optionnel
            total_so_far: Total cumule optionnel
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {log_type}: {message}"

        if count is not None:
            log_entry += f" (+{count})"
        if total_so_far is not None:
            log_entry += f" [Total: {total_so_far}]"

        self.detail_logs.append(log_entry)

        # Afficher les derniers logs
        if len(self.detail_logs) > 0:
            recent_logs = self.detail_logs[-5:]
            self.detail_container.text("\n".join(recent_logs))

    def clear_detail_logs(self):
        """Efface les logs de detail."""
        self.detail_logs = []
        self.detail_container.empty()

    def complete_phase(
        self,
        message: str,
        details: Dict = None,
        stats: Dict = None
    ):
        """
        Complete la phase courante.

        Args:
            message: Message de completion
            details: Details optionnels
            stats: Statistiques optionnelles
        """
        duration = time.time() - self.phase_start_time

        # Mettre a jour la phase dans la liste
        if self.phases_completed:
            self.phases_completed[-1].update({
                "status": "completed",
                "message": message,
                "duration": duration,
                "details": details,
                "stats": stats,
            })

        # Mettre a jour la progression
        progress = self.current_phase / self.total_phases
        self.progress_bar.progress(progress)
        self.status_text.markdown(f"**Phase {self.current_phase} terminee:** {message}")

        # Afficher le resume de la phase
        with self.phase_container:
            st.success(f"Phase {self.current_phase}: {message} ({duration:.1f}s)")

    def update_metric(self, name: str, value: Any):
        """
        Met a jour une metrique.

        Args:
            name: Nom de la metrique
            value: Valeur
        """
        self.metrics[name] = value

    def show_summary(self):
        """Affiche le resume final."""
        total_duration = time.time() - self.start_time

        with self.container:
            st.markdown("---")
            st.markdown("### Resume de la recherche")

            # Metriques principales
            cols = st.columns(4)
            with cols[0]:
                st.metric("Duree totale", f"{total_duration:.1f}s")
            with cols[1]:
                st.metric("Ads trouvees", self.metrics.get("total_ads_found", 0))
            with cols[2]:
                st.metric("Pages trouvees", self.metrics.get("total_pages_found", 0))
            with cols[3]:
                st.metric("Winning Ads", self.metrics.get("winning_ads_count", 0))

            # Resume des phases
            if self.phases_completed:
                with st.expander("Detail des phases", expanded=False):
                    for phase in self.phases_completed:
                        status_icon = "ok" if phase.get("status") == "completed" else "hourglass_flowing_sand"
                        duration = phase.get("duration", 0)
                        message = phase.get("message", "")
                        st.write(f":{status_icon}: **Phase {phase['phase']}** - {phase['name']}: {message} ({duration:.1f}s)")

    def finalize_log(self, status: str = "completed", error_message: str = None):
        """
        Finalise le log de recherche en base de donnees.

        Args:
            status: Statut final (completed, failed, preview, no_results)
            error_message: Message d'erreur optionnel
        """
        # Sauvegarder les phases dans le log
        if self.db and self.log_id:
            try:
                from src.infrastructure.persistence.database import update_search_log_phases
                update_search_log_phases(self.db, self.log_id, self.phases_completed)
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
                    **self.metrics
                )
            except Exception:
                pass

        # Nettoyer le tracker API global
        if self.api_tracker:
            try:
                self.api_tracker.save_calls_to_db()
            except Exception:
                pass
