"""
Page Scans Programmes - Automatisation des recherches.
"""
import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import info_card
from src.infrastructure.config import AVAILABLE_COUNTRIES, AVAILABLE_LANGUAGES
from src.infrastructure.persistence.database import (
    get_scheduled_scans, create_scheduled_scan,
    update_scheduled_scan, delete_scheduled_scan
)


def render_scheduled_scans():
    """Page Scans Programmes - Automatisation des recherches."""
    st.title("🕐 Scans Programmes")
    st.markdown("Automatisez vos recherches recurrentes")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    info_card(
        "Comment fonctionnent les scans programmes ?",
        """
        Les scans programmes vous permettent de :<br>
        - Definir des recherches automatiques par mots-cles<br>
        - Choisir la frequence (quotidien, hebdomadaire, mensuel)<br>
        - Recevoir automatiquement les nouvelles pages detectees<br><br>
        <b>Note :</b> Pour l'execution automatique, un scheduler externe (cron) est necessaire.
        """,
        "🕐"
    )

    # Creer un nouveau scan
    with st.expander("➕ Nouveau scan programme", expanded=False):
        with st.form("new_scan"):
            scan_name = st.text_input("Nom du scan *", placeholder="Ex: Veille mode femme")
            scan_keywords = st.text_area(
                "Mots-cles *",
                placeholder="Un mot-cle par ligne\nEx:\nrobe ete\nmode femme\nsummer dress"
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                scan_countries = st.multiselect("Pays", AVAILABLE_COUNTRIES, default=["FR"])
            with col2:
                scan_languages = st.multiselect("Langues", AVAILABLE_LANGUAGES, default=["fr"])
            with col3:
                scan_frequency = st.selectbox(
                    "Frequence",
                    ["daily", "weekly", "monthly"],
                    format_func=lambda x: {
                        "daily": "Quotidien",
                        "weekly": "Hebdomadaire",
                        "monthly": "Mensuel"
                    }[x]
                )

            if st.form_submit_button("Creer le scan", type="primary"):
                if scan_name and scan_keywords:
                    create_scheduled_scan(
                        db,
                        scan_name,
                        scan_keywords,
                        ",".join(scan_countries),
                        ",".join(scan_languages),
                        scan_frequency
                    )
                    st.success(f"Scan '{scan_name}' cree!")
                    st.rerun()
                else:
                    st.error("Nom et mots-cles requis")

    st.markdown("---")

    # Liste des scans
    scans = get_scheduled_scans(db)

    if scans:
        st.subheader(f"📋 {len(scans)} scan(s) programme(s)")

        for scan in scans:
            scan_id = scan["id"]
            status_icon = "🟢" if scan["is_active"] else "🔴"
            freq_label = {
                "daily": "Quotidien",
                "weekly": "Hebdomadaire",
                "monthly": "Mensuel"
            }.get(scan["frequency"], scan["frequency"])

            with st.expander(f"{status_icon} **{scan['name']}** - {freq_label}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**Mots-cles:** {scan['keywords'][:100]}...")
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
                        st.success("Scan supprime")
                        st.rerun()

                    if st.button("▶️ Executer", key=f"run_scan_{scan_id}"):
                        st.info("Fonctionnalite en cours de developpement")
    else:
        st.info("Aucun scan programme. Creez-en un pour automatiser vos recherches.")
