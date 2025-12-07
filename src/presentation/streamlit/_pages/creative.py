"""
Page Creative Analysis - Analyse des creatives publicitaires.

Ce module fournit deux fonctionnalites principales :
1. Analyse textuelle des creatives (render_creative_analysis)
2. Suivi des recherches en arriere-plan (render_background_searches)

Analyse Creative:
-----------------
Extrait et analyse le contenu textuel des winning ads pour identifier
les patterns gagnants :

- **Mots-cles frequents** : Termes les plus utilises dans les textes
  publicitaires (filtres des stopwords francais)
- **Emojis populaires** : Detection via regex Unicode pour identifier
  les emojis qui performent
- **CTAs detectes** : Liste predefinies de call-to-actions recherchees
  ("acheter maintenant", "livraison gratuite", etc.)
- **Statistiques de longueur** : Moyenne des caracteres pour textes/titres

Galerie des creatifs:
---------------------
Affiche les winning ads avec apercu :
- Tri par reach, age ou page
- Limite configurable (6 a 30 ads)
- Apercu du texte (80 caracteres)
- Lien direct vers l'ad

Recherches en arriere-plan:
---------------------------
Interface de monitoring temps reel des recherches lancees :
- Auto-refresh toutes les 5 secondes (si streamlit_autorefresh installe)
- Progression par phase (1-9)
- Journal d'activite detaille avec durees
- Gestion des recherches interrompues (reprise/suppression)

Dependances:
------------
- streamlit_autorefresh (optionnel) : Pour le refresh automatique
- background_worker : Worker de recherche asynchrone
"""
from datetime import datetime
from collections import Counter
import re
import json

import streamlit as st

from src.presentation.streamlit.shared import get_database
from src.presentation.streamlit.components import (
    CHART_COLORS, info_card, chart_header, create_horizontal_bar_chart
)
from src.infrastructure.persistence.database import get_winning_ads


def render_creative_analysis():
    """Page Creative Analysis - Analyse des créatives publicitaires"""
    st.title("🎨 Creative Analysis")
    st.markdown("Analysez les tendances créatives des annonces")

    db = get_database()
    if not db:
        st.warning("Base de donnees non connectee")
        return

    info_card(
        "Comment utiliser cette analyse ?",
        """
        Cette page analyse le contenu textuel des annonces pour identifier :<br>
        - Les <b>mots-cles</b> les plus utilises dans les titres et textes<br>
        - Les <b>emojis</b> les plus populaires<br>
        - Les <b>call-to-actions</b> (CTA) les plus frequents<br>
        - Les <b>longueurs de texte</b> optimales
        """,
        "info"
    )

    try:
        # Recuperer les winning ads pour analyse
        winning_ads = get_winning_ads(db, limit=500, days=30)

        if not winning_ads:
            st.warning("Pas assez de donnees. Lancez des recherches pour collecter des annonces.")
            return

        st.success(f"Analyse basee sur {len(winning_ads)} winning ads")

        # Analyse des textes
        all_bodies = []
        all_titles = []
        all_captions = []
        emojis = []

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

        col1.metric("Longueur moyenne texte", f"{avg_body_len:.0f} car.")
        col2.metric("Longueur moyenne titre", f"{avg_title_len:.0f} car.")
        col3.metric("Total emojis trouves", len(emojis))
        col4.metric("Ads analysees", len(winning_ads))

        st.markdown("---")

        # Top mots-cles
        col1, col2 = st.columns(2)

        with col1:
            chart_header("Mots-cles frequents", "Mots les plus utilises dans les textes")

            # Compter les mots
            all_text = " ".join(all_bodies + all_titles).lower()
            words = re.findall(r'\b[a-z\u00e0\u00e2\u00e4\u00e9\u00e8\u00ea\u00eb\u00ef\u00ee\u00f4\u00f9\u00fb\u00fc\u00e7]{4,}\b', all_text)

            # Stopwords francais basiques
            stopwords = {"pour", "dans", "avec", "vous", "votre", "nous", "cette", "plus", "tout", "tous", "faire", "comme", "etre", "avoir", "sans"}
            words = [w for w in words if w not in stopwords]

            word_counts = Counter(words).most_common(10)

            if word_counts:
                labels = [w[0] for w in word_counts]
                values = [w[1] for w in word_counts]
                fig = create_horizontal_bar_chart(labels, values, colors=[CHART_COLORS["primary"]] * len(labels))
                st.plotly_chart(fig, key="word_freq", width="stretch")

        with col2:
            chart_header("Emojis populaires", "Emojis les plus utilises")

            emoji_counts = Counter(emojis).most_common(10)

            if emoji_counts:
                for emoji, count in emoji_counts:
                    st.write(f"{emoji} : {count} fois")
            else:
                st.caption("Pas assez d'emojis trouves")

        # CTAs frequents
        st.markdown("---")
        chart_header("Call-to-Actions detectes", "Phrases d'action les plus frequentes")

        cta_patterns = [
            "acheter maintenant", "commander", "decouvrir", "profiter", "en savoir plus",
            "cliquez", "obtenez", "telecharger", "essayer", "reserver",
            "shop now", "buy now", "order now", "get yours", "learn more",
            "livraison gratuite", "offre limitee", "promo", "soldes", "-50%", "-30%"
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
                st.write(f"- **{cta}** : {count} occurrence(s)")
        else:
            st.caption("Aucun CTA commun detecte")

        # GALERIE DES CREATIFS
        st.markdown("---")
        chart_header(
            "Galerie des creatifs",
            "Apercu visuel des publicites performantes",
            "Cliquez sur une ad pour voir les details"
        )

        # Filtrer les ads avec des URLs d'apercu
        ads_with_preview = [ad for ad in winning_ads if ad.get("ad_snapshot_url")]

        if ads_with_preview:
            # Controles de la galerie
            col_filter, col_sort = st.columns(2)
            with col_filter:
                gallery_limit = st.slider("Nombre d'ads", 6, 30, 12, 6, key="gallery_limit")
            with col_sort:
                sort_by = st.selectbox("Trier par", ["Reach", "Age (recent)", "Page"], key="gallery_sort")

            # Trier
            if sort_by == "Reach":
                ads_with_preview = sorted(ads_with_preview, key=lambda x: x.get("eu_total_reach", 0) or 0, reverse=True)
            elif sort_by == "Age (recent)":
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
                                <div style="font-size: 12px; color: #888;">{reach_str} reach - {age}j</div>
                                <div style="font-size: 14px; font-weight: bold; margin: 5px 0;">{page_name}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Texte de l'ad (apercu)
                            body = ad.get("ad_creative_bodies", "") or ""
                            if body:
                                st.caption(body[:80] + ("..." if len(body) > 80 else ""))

                            # Lien vers l'ad
                            ad_url = ad.get("ad_snapshot_url", "")
                            if ad_url:
                                st.link_button("Voir", ad_url, use_container_width=True)
        else:
            st.info("Aucune ad avec apercu disponible")

    except Exception as e:
        st.error(f"Erreur: {e}")


def render_background_searches():
    """Page de suivi des recherches en arriere-plan - uniquement les recherches actives"""
    # Auto-refresh toutes les 5 secondes si des recherches sont en cours
    try:
        from streamlit_autorefresh import st_autorefresh
        # Ne pas auto-refresh si pas de recherches actives (verifie plus bas)
        auto_refresh_enabled = st.session_state.get("bg_has_active_searches", False)
        if auto_refresh_enabled:
            st_autorefresh(interval=5000, limit=None, key="bg_autorefresh")
    except ImportError:
        pass  # Package non installe, refresh manuel

    st.title("🔄 Recherches en cours")
    st.markdown("Suivi en temps réel des recherches en arrière-plan.")

    db = get_database()
    if not db:
        st.error("Base de donnees non connectee")
        return

    # Initialiser le worker
    try:
        from src.infrastructure.workers.background_worker import get_worker, init_worker
        from src.infrastructure.persistence.database import (
            get_interrupted_searches, restart_search_queue,
            cancel_search_queue, SearchQueue
        )
        worker = init_worker()
    except Exception as e:
        st.error(f"Erreur initialisation worker: {e}")
        return

    # Recherches interrompues (apres redemarrage)
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
                st.write(f"**Recherche #{search.id}** - {search.created_at:%d/%m %H:%M} - Phase {search.current_phase}/9")
                st.caption(f"Mots-cles: {keywords_display}")
            with col2:
                if st.button("Reprendre", key=f"resume_{search.id}"):
                    restart_search_queue(db, search.id)
                    st.success("Recherche relancee!")
                    st.rerun()
            with col3:
                if st.button("Supprimer", key=f"delete_int_{search.id}"):
                    with db.get_session() as session:
                        session.query(SearchQueue).filter(SearchQueue.id == search.id).delete()
                    st.rerun()

        st.divider()

    # Recherches actives
    active_searches = worker.get_active_searches()

    # Stocker l'etat pour l'auto-refresh
    st.session_state["bg_has_active_searches"] = len(active_searches) > 0

    if active_searches:
        # Bouton de rafraichissement manuel
        col_refresh, col_info = st.columns([1, 3])
        with col_refresh:
            if st.button("Rafraichir", width="stretch"):
                st.rerun()
        with col_info:
            st.caption("Rafraichissement automatique toutes les 5 secondes")

        st.divider()

        for search in active_searches:
            keywords = search.get("keywords", [])
            keywords_display = ", ".join(keywords[:5])
            if len(keywords) > 5:
                keywords_display += f"... (+{len(keywords) - 5})"

            # Container avec bordure visuelle
            with st.container():
                # En-tete avec statut
                if search["status"] == "running":
                    phase = search.get("phase", 0)
                    phase_name = search.get("phase_name", "")
                    progress = search.get("progress", 0)
                    message = search.get("message", "")
                    phases_data = search.get("phases_data", [])

                    # Titre avec phase et temps ecoule
                    header_col1, header_col2 = st.columns([3, 1])
                    with header_col1:
                        st.markdown(f"### Recherche #{search['id']} - En cours")
                    with header_col2:
                        if search.get("started_at"):
                            started = search["started_at"]
                            elapsed = datetime.now() - started.replace(tzinfo=None)
                            minutes = int(elapsed.total_seconds() // 60)
                            seconds = int(elapsed.total_seconds() % 60)
                            st.markdown(f"**{minutes}m {seconds}s**")

                    # Informations de la phase actuelle
                    phase_col1, phase_col2 = st.columns([3, 1])
                    with phase_col1:
                        st.markdown(f"**Phase {phase}/9:** {phase_name}")
                    with phase_col2:
                        st.markdown(f"**{progress}%**")

                    # Barre de progression
                    st.progress(progress / 100)

                    # Message de progression detaille
                    if message:
                        st.info(f"{message}")

                    # Journal d'activite detaille
                    st.markdown("##### Journal d'activite")

                    # Afficher les phases completees
                    if phases_data:
                        for phase_info in phases_data:
                            phase_num = phase_info.get("num", "?")
                            phase_name_log = phase_info.get("name", "")
                            phase_result = phase_info.get("result", "")
                            phase_duration = phase_info.get("duration", "")

                            # Formater la duree
                            duration_str = ""
                            if phase_duration:
                                if phase_duration >= 60:
                                    duration_str = f" ({phase_duration/60:.1f}m)"
                                else:
                                    duration_str = f" ({phase_duration:.1f}s)"

                            st.markdown(f"**Phase {phase_num}:** {phase_name_log} -> {phase_result}{duration_str}")

                    # Phase en cours (non encore completee)
                    if phase and phase_name:
                        st.markdown(f"**Phase {phase}:** {phase_name} ...")

                    # Afficher les mots-cles
                    st.caption(f"Mots-cles: {keywords_display}")

                else:
                    # Recherche en attente
                    st.markdown(f"### Recherche #{search['id']} - En attente")
                    st.write(f"**Mots-cles:** {keywords_display}")

                    if search.get("created_at"):
                        st.caption(f"Creee: {search['created_at']:%d/%m/%Y %H:%M}")

                    # Bouton d'annulation
                    if st.button("Annuler cette recherche", key=f"cancel_{search['id']}"):
                        worker.cancel_search(search["id"])
                        st.success("Recherche annulee")
                        st.rerun()

                st.divider()

    else:
        st.info("Aucune recherche en cours actuellement.")
        st.markdown("""
        **Pour lancer une recherche en arriere-plan:**
        1. Allez dans **Search Ads**
        2. Configurez vos criteres de recherche
        3. Cochez **Lancer en arriere-plan**
        4. Cliquez sur **Lancer la recherche**

        La recherche continuera meme si vous quittez la page.
        """)
