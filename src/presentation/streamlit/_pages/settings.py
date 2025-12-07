"""
Page Settings - Configuration complete de l'application.

Ce module centralise tous les parametres de l'application
organises en 5 onglets thematiques.

Barre de statut:
----------------
Indicateurs rapides en haut de page :
- Tokens Meta API (actifs/total)
- Statut base de donnees
- API Gemini (configure ou non)
- Nombre de pages en blacklist

Onglet 1 - API & Connexions:
----------------------------
**Tokens Meta API** :
- Ajout/suppression de tokens avec rotation automatique
- Proxy associe par token (anti-ban)
- Stats par token : appels, erreurs, rate limits
- Actions : verifier, activer/desactiver, debloquer, reset

**Base de donnees** :
- Statut de connexion PostgreSQL
- Metriques : pages, etats, CMS

**Statistiques API (30j)** :
- Appels Meta API, ScraperAPI, Web Direct
- Nombre de rate limits

**Cache API** :
- Entrees valides/expirees
- Total hits
- Nettoyage expire / vider tout

Onglet 2 - Configuration:
-------------------------
**Seuils de detection** :
- min_ads_suivi : Seuil pour table suivi_page
- min_ads_liste : Seuil pour liste_ads_recherche

**Configuration des etats** :
- Seuils XS, S, M, L, XL, XXL
- Apercu visuel des plages

Onglet 3 - Classification:
--------------------------
**API Gemini** :
- Configuration du modele (gemini-1.5-flash, etc.)
- Test de connectivite

**Taxonomie** :
- Gestion categories/sous-categories
- Initialisation taxonomie par defaut
- Stats de classification

**Lancement classification** :
- Classifier les pages non classifiees par batch

Onglet 4 - Blacklist:
---------------------
- Ajout manuel de pages
- Liste avec raison et date
- Suppression individuelle

Onglet 5 - Maintenance:
-----------------------
**Migration** :
- Ajout pays FR aux pages existantes
- Classification Gemini en masse

**Nettoyage doublons** :
- Detection doublons ads_recherche et winning_ads
- Suppression (garde les plus recents)

**Archivage** :
- Stats tables principales vs archives
- Archivage donnees > 90 jours
"""
import os
import streamlit as st
import pandas as pd

from src.presentation.streamlit.shared import get_database
from src.infrastructure.config import (
    MIN_ADS_SUIVI, MIN_ADS_LISTE, DEFAULT_STATE_THRESHOLDS
)
from src.infrastructure.persistence.database import (
    get_suivi_stats, get_blacklist, add_to_blacklist, remove_from_blacklist
)
from src.infrastructure.persistence.repositories import recalculate_all_page_states


def render_settings():
    """Page Settings - Parametres avec navigation par onglets"""
    st.title("⚙️ Settings")

    db = get_database()

    # === STATUS INDICATORS ===
    if db:
        from src.infrastructure.persistence.database import get_all_meta_tokens, get_app_setting, ensure_tables_exist
        ensure_tables_exist(db)
        tokens = get_all_meta_tokens(db)
        active_tokens = len([t for t in tokens if t["is_active"] and not t.get("is_rate_limited")])
        total_tokens = len(tokens)
        gemini_ok = bool(os.getenv("GEMINI_API_KEY", ""))
        blacklist = get_blacklist(db) if db else []

        # Status bar
        status_cols = st.columns(5)
        with status_cols[0]:
            token_status = "✅" if active_tokens > 0 else "❌"
            st.caption(f"🔑 Tokens: {active_tokens}/{total_tokens} {token_status}")
        with status_cols[1]:
            st.caption(f"🗄️ BDD: ✅ Connectee")
        with status_cols[2]:
            gemini_status = "✅" if gemini_ok else "❌"
            st.caption(f"🤖 Gemini: {gemini_status}")
        with status_cols[3]:
            st.caption(f"🚫 Blacklist: {len(blacklist)}")
        with status_cols[4]:
            st.caption(f"📊 Config: ✅")
    else:
        st.warning("🗄️ Base de donnees non connectee")

    st.markdown("---")

    # === NAVIGATION PAR ONGLETS ===
    tab_api, tab_config, tab_classification, tab_blacklist, tab_maintenance = st.tabs([
        "🔑 API & Connexions",
        "📊 Configuration",
        "🤖 Classification",
        "🚫 Blacklist",
        "🛠️ Maintenance"
    ])

    with tab_api:
        render_settings_api_tab(db)

    with tab_config:
        render_settings_config_tab(db)

    with tab_classification:
        render_settings_classification_tab(db)

    with tab_blacklist:
        render_settings_blacklist_tab(db)

    with tab_maintenance:
        render_settings_maintenance_tab(db)


def render_settings_api_tab(db):
    """Onglet API & Connexions"""
    if not db:
        st.warning("Base de donnees non connectee")
        return

    from src.infrastructure.persistence.database import (
        get_all_meta_tokens, add_meta_token, delete_meta_token,
        update_meta_token, reset_token_stats, clear_rate_limit,
        get_search_logs_stats, get_cache_stats, clear_expired_cache, clear_all_cache
    )

    # === SECTION: TOKENS META API ===
    st.subheader("🔑 Tokens Meta API")
    st.caption("Gerez vos tokens pour la rotation automatique anti-ban")

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
                                      help="Proxy associe a ce token pour eviter les bans IP")

        if st.button("Ajouter le token", type="primary", key="btn_add_token"):
            if new_token_value and new_token_value.strip():
                token_id = add_meta_token(
                    db,
                    new_token_value.strip(),
                    new_token_name.strip() or None,
                    new_proxy_url.strip() or None
                )
                if token_id:
                    st.success(f"✅ Token ajoute avec succes (ID: {token_id})")
                    st.rerun()
            else:
                st.error("Veuillez entrer un token valide")

    # Liste des tokens existants
    if tokens:
        st.markdown("##### Tokens configures")

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

                # === SECTION EDITION ===
                st.markdown("---")
                st.markdown("**✏️ Modifier le token**")

                # Nom du token
                edit_name = st.text_input(
                    "Nom",
                    value=t["name"],
                    key=f"edit_name_{t['id']}",
                    help="Nom pour identifier ce token"
                )

                # Token avec toggle afficher/masquer
                show_token_key = f"show_token_{t['id']}"
                if show_token_key not in st.session_state:
                    st.session_state[show_token_key] = False

                col_token, col_toggle = st.columns([4, 1])
                with col_token:
                    if st.session_state[show_token_key]:
                        edit_token = st.text_input(
                            "Token Meta API",
                            value=t["token"],
                            key=f"edit_token_{t['id']}",
                            help="Modifiez le token si necessaire"
                        )
                    else:
                        edit_token = st.text_input(
                            "Token Meta API",
                            value=t["token"],
                            type="password",
                            key=f"edit_token_{t['id']}",
                            help="Cliquez sur 👁️ pour afficher le token"
                        )
                with col_toggle:
                    st.write("")  # Espacement
                    if st.button("👁️" if not st.session_state[show_token_key] else "🙈", key=f"toggle_show_{t['id']}"):
                        st.session_state[show_token_key] = not st.session_state[show_token_key]
                        st.rerun()

                # Proxy URL
                current_proxy = t.get("proxy_url") or ""
                edit_proxy = st.text_input(
                    "Proxy URL",
                    value=current_proxy,
                    key=f"edit_proxy_{t['id']}",
                    placeholder="http://user:pass@ip:port",
                    help="Proxy associe a ce token (optionnel)"
                )

                # Bouton sauvegarder les modifications
                if st.button("💾 Sauvegarder les modifications", key=f"save_edit_{t['id']}", type="primary"):
                    changes_made = False
                    if edit_name != t["name"]:
                        update_meta_token(db, t["id"], name=edit_name)
                        changes_made = True
                    if edit_token != t["token"] and edit_token.strip():
                        update_meta_token(db, t["id"], token_value=edit_token.strip())
                        changes_made = True
                    if edit_proxy != current_proxy:
                        update_meta_token(db, t["id"], proxy_url=edit_proxy.strip())
                        changes_made = True

                    if changes_made:
                        st.success("✅ Modifications sauvegardees!")
                        st.rerun()
                    else:
                        st.info("Aucune modification detectee")

                st.markdown("---")

                # Actions rapides
                st.markdown("**⚡ Actions rapides**")
                action_cols = st.columns(5)
                with action_cols[0]:
                    new_active = not t["is_active"]
                    if st.button("🔄 Activer" if not t["is_active"] else "⏸️ Desactiver", key=f"toggle_{t['id']}"):
                        update_meta_token(db, t["id"], is_active=new_active)
                        st.rerun()
                with action_cols[1]:
                    if st.button("✅ Verifier", key=f"verify_{t['id']}"):
                        from src.infrastructure.persistence.database import verify_meta_token
                        with st.spinner("Verification..."):
                            result = verify_meta_token(db, t["id"])
                        if result["valid"]:
                            st.success(f"✅ Token valide ({result['response_time_ms']}ms)")
                        else:
                            st.error(f"❌ {result.get('error', 'Erreur inconnue')}")
                with action_cols[2]:
                    if t.get("is_rate_limited"):
                        if st.button("🔓 Debloquer", key=f"unblock_{t['id']}"):
                            clear_rate_limit(db, t["id"])
                            st.rerun()
                with action_cols[3]:
                    if st.button("📊 Reset", key=f"reset_{t['id']}"):
                        reset_token_stats(db, t["id"])
                        st.rerun()
                with action_cols[4]:
                    if st.button("🗑️", key=f"delete_{t['id']}", help="Supprimer"):
                        delete_meta_token(db, t["id"])
                        st.rerun()

                # Infos supplementaires
                if t["last_used_at"]:
                    st.caption(f"📅 Derniere utilisation: {t['last_used_at'].strftime('%d/%m/%Y %H:%M')}")
                if t["last_error_message"]:
                    st.caption(f"❌ Derniere erreur: {t['last_error_message'][:100]}")
    else:
        st.info("Aucun token configure. Ajoutez votre premier token Meta API ci-dessus.")
        env_token = os.getenv("META_ACCESS_TOKEN", "")
        if env_token:
            if st.button("📥 Importer depuis META_ACCESS_TOKEN", key="import_env_token"):
                add_meta_token(db, env_token, "Token Principal (importe)")
                st.success("Token importe avec succes!")
                st.rerun()

    st.markdown("---")

    # === SECTION: BASE DE DONNEES ===
    st.subheader("🗄️ Base de donnees")
    st.success("✓ Connecte a PostgreSQL")

    try:
        stats = get_suivi_stats(db)
        col1, col2, col3 = st.columns(3)
        col1.metric("Pages en base", stats.get("total_pages", 0))
        col2.metric("Etats differents", len(stats.get("etats", {})))
        col3.metric("CMS differents", len(stats.get("cms", {})))
    except:
        pass

    st.markdown("---")

    # === SECTION: STATISTIQUES API ===
    st.subheader("📡 Statistiques API")
    st.caption("Utilisation des APIs sur les 30 derniers jours")

    api_stats = get_search_logs_stats(db, days=30)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔵 Meta API", f"{api_stats.get('total_meta_api_calls', 0):,}")
    col2.metric("🟠 ScraperAPI", f"{api_stats.get('total_scraper_api_calls', 0):,}")
    col3.metric("🌐 Web Direct", f"{api_stats.get('total_web_requests', 0):,}")
    col4.metric("⚠️ Rate Limits", f"{api_stats.get('total_rate_limit_hits', 0):,}")

    st.markdown("---")

    # === SECTION: CACHE API ===
    st.subheader("💾 Cache API")

    try:
        cache_stats = get_cache_stats(db)

        col1, col2, col3 = st.columns(3)
        col1.metric("Entrees valides", cache_stats.get("valid_entries", 0))
        col2.metric("Entrees expirees", cache_stats.get("expired_entries", 0))
        col3.metric("Total hits", f"{cache_stats.get('total_hits', 0):,}")

        col1, col2, _ = st.columns(3)
        with col1:
            if st.button("🧹 Nettoyer expire", key="clear_expired_cache"):
                deleted = clear_expired_cache(db)
                st.success(f"✅ {deleted} entrees supprimees")
                st.rerun()
        with col2:
            if st.button("🗑️ Vider tout", key="clear_all_cache"):
                deleted = clear_all_cache(db)
                st.success(f"✅ {deleted} entrees supprimees")
                st.rerun()
    except Exception as e:
        st.error(f"Erreur cache: {e}")


def render_settings_config_tab(db):
    """Onglet Configuration - Seuils et Etats"""
    if not db:
        st.warning("Base de donnees non connectee")
        return

    from src.infrastructure.persistence.database import get_app_setting, set_app_setting

    # === SECTION: SEUILS DE DETECTION ===
    st.subheader("📊 Seuils de detection")
    st.caption("Ces seuils determinent quelles pages sont sauvegardees dans les differentes tables.")

    detection = st.session_state.detection_thresholds

    col1, col2 = st.columns(2)

    with col1:
        new_min_suivi = st.number_input(
            "Min. ads pour Suivi (suivi_page)",
            min_value=1,
            max_value=100,
            value=detection.get("min_ads_suivi", MIN_ADS_SUIVI),
            help="Nombre minimum d'ads pour qu'une page soit ajoutee a la table de suivi.",
            key="config_min_suivi"
        )
        st.caption("📈 **Table suivi_page** : Historique d'evolution des pages")

    with col2:
        new_min_liste = st.number_input(
            "Min. ads pour Liste Ads (liste_ads_recherche)",
            min_value=1,
            max_value=100,
            value=detection.get("min_ads_liste", MIN_ADS_LISTE),
            help="Nombre minimum d'ads pour qu'une page ait ses annonces detaillees sauvegardees.",
            key="config_min_liste"
        )
        st.caption("📋 **Table liste_ads_recherche** : Detail de chaque annonce")

    if st.button("💾 Sauvegarder les seuils de detection", key="save_detection_config"):
        st.session_state.detection_thresholds = {
            "min_ads_suivi": new_min_suivi,
            "min_ads_liste": new_min_liste,
        }
        # Persister en BDD
        set_app_setting(db, "min_ads_suivi", str(new_min_suivi), "Seuil minimum pour suivi_page")
        set_app_setting(db, "min_ads_liste", str(new_min_liste), "Seuil minimum pour liste_ads_recherche")
        st.success("✓ Seuils de detection sauvegardes !")

    with st.expander("ℹ️ Comment fonctionnent ces seuils ?"):
        st.markdown("""
        **Lors d'une recherche, les pages sont filtrees par ces seuils :**

        | Table | Seuil | Contenu |
        |-------|-------|---------|
        | `liste_page_recherche` | Toutes | Toutes les pages trouvees avec infos de base |
        | `suivi_page` | Min. Suivi | Pages pour le monitoring (evolution historique) |
        | `liste_ads_recherche` | Min. Liste Ads | Detail des annonces individuelles |
        """)

    st.markdown("---")

    # === SECTION: CONFIGURATION DES ETATS ===
    st.subheader("🏷️ Configuration des etats")
    st.caption("Definissez les seuils minimums d'ads actives pour chaque etat:")

    thresholds = st.session_state.state_thresholds

    col1, col2, col3 = st.columns(3)

    with col1:
        new_xs = st.number_input("XS (min)", min_value=1, max_value=1000, value=thresholds.get("XS", 1), key="state_xs")
        new_m = st.number_input("M (min)", min_value=1, max_value=1000, value=thresholds.get("M", 20), key="state_m")

    with col2:
        new_s = st.number_input("S (min)", min_value=1, max_value=1000, value=thresholds.get("S", 10), key="state_s")
        new_l = st.number_input("L (min)", min_value=1, max_value=1000, value=thresholds.get("L", 35), key="state_l")

    with col3:
        new_xl = st.number_input("XL (min)", min_value=1, max_value=1000, value=thresholds.get("XL", 80), key="state_xl")
        new_xxl = st.number_input("XXL (min)", min_value=1, max_value=1000, value=thresholds.get("XXL", 150), key="state_xxl")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 Sauvegarder", type="primary", key="save_states_config"):
            new_thresholds = {"XS": new_xs, "S": new_s, "M": new_m, "L": new_l, "XL": new_xl, "XXL": new_xxl}
            if new_xs < new_s < new_m < new_l < new_xl < new_xxl:
                st.session_state.state_thresholds = new_thresholds
                set_app_setting(db, "state_thresholds", str(new_thresholds), "Seuils des etats")

                # Recalculer automatiquement tous les etats
                with st.spinner("Recalcul des etats en cours..."):
                    recalc_stats = recalculate_all_page_states(db, new_thresholds)

                st.success(f"✓ Seuils sauvegardes ! {recalc_stats['updated']}/{recalc_stats['total_pages']} pages mises a jour.")
            else:
                st.error("Les seuils doivent etre strictement croissants (XS < S < M < L < XL < XXL)")

    with col2:
        if st.button("🔄 Reinitialiser", key="reset_states_config"):
            st.session_state.state_thresholds = DEFAULT_STATE_THRESHOLDS.copy()
            st.rerun()

    # Apercu des etats
    st.markdown("---")
    st.markdown("**Apercu des etats actuels:**")
    current = st.session_state.state_thresholds
    preview_data = [
        {"Etat": "Inactif", "Plage": "0 ads"},
        {"Etat": "XS", "Plage": f"{current['XS']}-{current['S']-1} ads"},
        {"Etat": "S", "Plage": f"{current['S']}-{current['M']-1} ads"},
        {"Etat": "M", "Plage": f"{current['M']}-{current['L']-1} ads"},
        {"Etat": "L", "Plage": f"{current['L']}-{current['XL']-1} ads"},
        {"Etat": "XL", "Plage": f"{current['XL']}-{current['XXL']-1} ads"},
        {"Etat": "XXL", "Plage": f"≥{current['XXL']} ads"},
    ]
    st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)


def render_settings_classification_tab(db):
    """Onglet Classification - Gemini et Taxonomie"""
    if not db:
        st.warning("Base de donnees non connectee")
        return

    from src.infrastructure.persistence.database import (
        get_app_setting, set_app_setting, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT,
        get_all_taxonomy, add_taxonomy_entry, update_taxonomy_entry,
        delete_taxonomy_entry, init_default_taxonomy, get_taxonomy_categories,
        get_classification_stats
    )

    gemini_key = os.getenv("GEMINI_API_KEY", "")

    # === SECTION: GEMINI API ===
    st.subheader("🤖 API Gemini")

    if gemini_key:
        st.success("✅ Cle API Gemini configuree")
    else:
        st.warning("⚠️ Cle API Gemini non configuree. Ajoutez GEMINI_API_KEY dans les variables d'environnement.")

    st.markdown("##### Modele Gemini")
    st.caption("Les modeles Gemini evoluent regulierement. Modifiez si le modele actuel devient obsolete.")

    current_model = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)

    model_options = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro", "gemini-2.0-flash-exp", "gemini-exp-1206"]
    if current_model and current_model not in model_options:
        model_options.insert(0, current_model)

    col_model, col_btn = st.columns([3, 1])
    with col_model:
        new_model = st.text_input("Nom du modele", value=current_model, key="gemini_model_class")

    with col_btn:
        st.write("")
        if st.button("💾 Sauvegarder", key="save_gemini_model_class"):
            if new_model and new_model.strip():
                set_app_setting(db, SETTING_GEMINI_MODEL, new_model.strip(), "Modele Gemini pour la classification")
                st.success(f"✅ Modele mis a jour: {new_model}")
                st.rerun()

    st.caption(f"**Modeles suggeres:** {', '.join(model_options[:4])}")

    # Test API
    st.markdown("##### Tester l'API Gemini")
    if st.button("🧪 Tester API", key="test_gemini_class", type="primary"):
        if not gemini_key:
            st.error("❌ Cle API Gemini non configuree")
        else:
            with st.spinner("Test en cours..."):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=gemini_key)
                    test_model_name = get_app_setting(db, SETTING_GEMINI_MODEL, SETTING_GEMINI_MODEL_DEFAULT)
                    model = genai.GenerativeModel(test_model_name)
                    test_prompt = "Reponds juste 'OK' pour confirmer que tu fonctionnes."
                    response = model.generate_content(test_prompt)
                    if response and response.text:
                        st.success(f"✅ API Gemini fonctionne! Modele: {test_model_name}")
                    else:
                        st.warning("⚠️ API accessible mais reponse vide")
                except ImportError:
                    st.error("❌ Librairie `google-generativeai` non installee")
                except Exception as e:
                    st.error(f"❌ Erreur: {str(e)[:200]}")

    st.markdown("---")

    # === SECTION: TAXONOMIE ===
    st.subheader("📚 Taxonomie de classification")

    if st.button("🔄 Initialiser taxonomie par defaut", key="init_taxonomy_class"):
        added = init_default_taxonomy(db)
        if added > 0:
            st.success(f"✅ {added} categories ajoutees")
            st.rerun()
        else:
            st.info("La taxonomie est deja initialisee")

    # Stats de classification
    try:
        class_stats = get_classification_stats(db)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Classifiees", class_stats["classified"])
        col2.metric("Non classifiees", class_stats["unclassified"])
        col3.metric("Taux", f"{class_stats['classification_rate']}%")
        col4.metric("Total pages", class_stats["total"])
    except Exception:
        pass

    # Afficher la taxonomie
    taxonomy = get_all_taxonomy(db, active_only=False)

    if taxonomy:
        categories = {}
        for entry in taxonomy:
            if entry.category not in categories:
                categories[entry.category] = []
            categories[entry.category].append(entry)

        st.markdown(f"**{len(taxonomy)} entrees dans {len(categories)} categories**")

        for cat_name, entries in categories.items():
            with st.expander(f"📁 **{cat_name}** ({len(entries)} sous-categories)"):
                for entry in entries:
                    col1, col2, col3, col4 = st.columns([3, 3, 1, 1])

                    with col1:
                        new_subcat = st.text_input("Sous-categorie", value=entry.subcategory, key=f"subcat_{entry.id}", label_visibility="collapsed")

                    with col2:
                        new_desc = st.text_input("Description", value=entry.description or "", key=f"desc_{entry.id}", label_visibility="collapsed")

                    with col3:
                        is_active = st.checkbox("Actif", value=entry.is_active, key=f"active_{entry.id}")

                    with col4:
                        if st.button("🗑️", key=f"del_tax_{entry.id}"):
                            delete_taxonomy_entry(db, entry.id)
                            st.rerun()

                    if new_subcat != entry.subcategory or new_desc != (entry.description or "") or is_active != entry.is_active:
                        update_taxonomy_entry(db, entry.id, subcategory=new_subcat, description=new_desc if new_desc else None, is_active=is_active)

    # Ajouter une nouvelle entree
    st.markdown("---")
    st.markdown("**➕ Ajouter une categorie/sous-categorie**")

    col1, col2, col3 = st.columns(3)

    with col1:
        existing_cats = get_taxonomy_categories(db)
        cat_options = existing_cats + ["➕ Nouvelle categorie..."]
        selected_cat = st.selectbox("Categorie", options=cat_options, key="new_tax_cat_class")

        if selected_cat == "➕ Nouvelle categorie...":
            new_cat_name = st.text_input("Nouvelle categorie", key="new_cat_name_class")
        else:
            new_cat_name = selected_cat

    with col2:
        new_subcat_name = st.text_input("Sous-categorie", key="new_subcat_name_class")

    with col3:
        new_tax_desc = st.text_input("Description", key="new_tax_desc_class")

    if st.button("➕ Ajouter", key="add_taxonomy_class"):
        if new_cat_name and new_subcat_name:
            entry_id = add_taxonomy_entry(db, new_cat_name, new_subcat_name, new_tax_desc or None)
            st.success(f"✅ Entree ajoutee (ID: {entry_id})")
            st.rerun()
        else:
            st.error("Categorie et sous-categorie requises")

    # Lancer la classification
    st.markdown("---")
    st.markdown("**🚀 Classifier les pages non classifiees**")

    col1, col2 = st.columns([1, 2])
    with col1:
        batch_size = st.number_input("Nombre de pages", min_value=10, max_value=500, value=50, step=10, key="batch_size_class")

    with col2:
        if st.button("🚀 Lancer la classification", key="run_classification_class", type="primary"):
            if not gemini_key:
                st.error("Configurez GEMINI_API_KEY d'abord")
            else:
                with st.spinner(f"Classification de {batch_size} pages en cours..."):
                    try:
                        from src.infrastructure.external_services.gemini_classifier import classify_and_save
                        result = classify_and_save(db, limit=batch_size)
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success(f"✅ {result['classified']} pages classifiees ({result.get('errors', 0)} erreurs)")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erreur: {e}")


def render_settings_blacklist_tab(db):
    """Onglet Blacklist - Gestion de la blacklist"""
    if not db:
        st.warning("Base de donnees non connectee")
        return

    st.subheader("🚫 Gestion de la Blacklist")
    st.caption("Les pages en blacklist seront ignorees lors des recherches.")

    # Ajouter manuellement une page
    with st.expander("➕ Ajouter une page a la blacklist", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_bl_page_id = st.text_input("Page ID", key="new_bl_page_id_bl")
        with col2:
            new_bl_page_name = st.text_input("Nom de la page (optionnel)", key="new_bl_page_name_bl")

        new_bl_raison = st.text_input("Raison (optionnel)", key="new_bl_raison_bl")

        if st.button("➕ Ajouter a la blacklist", key="add_bl_btn"):
            if new_bl_page_id:
                if add_to_blacklist(db, new_bl_page_id, new_bl_page_name, new_bl_raison):
                    st.success(f"✓ Page {new_bl_page_id} ajoutee a la blacklist")
                    st.rerun()
                else:
                    st.warning("Cette page est deja dans la blacklist")
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
                        st.caption(f"Ajoute: {entry['added_at'].strftime('%Y-%m-%d %H:%M')}")

                with col3:
                    if st.button("🗑️ Retirer", key=f"rm_bl_{entry['page_id']}_bl"):
                        if remove_from_blacklist(db, entry['page_id']):
                            st.success("✓ Retire")
                            st.rerun()
        else:
            st.info("Aucune page en blacklist")

    except Exception as e:
        st.error(f"Erreur: {e}")


def render_settings_maintenance_tab(db):
    """Onglet Maintenance - Migration, Doublons, Archivage"""
    if not db:
        st.warning("Base de donnees non connectee")
        return

    from src.infrastructure.persistence.database import (
        get_pages_count, migration_add_country_to_all_pages,
        update_pages_classification_batch,
        build_taxonomy_prompt, init_default_taxonomy, get_archive_stats, archive_old_data
    )
    from sqlalchemy import func
    from src.infrastructure.persistence.database import AdsRecherche, WinningAds

    gemini_key = os.getenv("GEMINI_API_KEY", "")

    # === SECTION: MIGRATION ===
    st.subheader("🔄 Migration des donnees existantes")
    st.caption("Appliquer la classification et le pays France aux pages deja enregistrees.")

    try:
        migration_stats = get_pages_count(db)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total pages", migration_stats["total"])
        col2.metric("Classifiees", migration_stats["classified"])
        col3.metric("Avec pays FR", migration_stats["with_fr"])
        col4.metric("Sans pays FR", migration_stats["without_fr"])
    except Exception:
        migration_stats = {"total": 0, "classified": 0, "with_fr": 0, "without_fr": 0, "unclassified": 0}

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🇫🇷 Ajouter France**")
        st.caption(f"{migration_stats.get('without_fr', 0)} pages sans FR")
        if st.button("Ajouter FR a toutes les pages", key="migration_add_fr_maint"):
            if migration_stats.get('without_fr', 0) == 0:
                st.info("✓ Toutes les pages ont deja FR")
            else:
                with st.spinner("Ajout de FR en cours..."):
                    try:
                        updated = migration_add_country_to_all_pages(db, "FR")
                        st.success(f"✅ {updated} pages mises a jour avec FR")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur: {e}")

    with col2:
        st.markdown("**🤖 Classification Gemini**")
        unclassified = migration_stats.get('unclassified', 0)
        st.caption(f"{unclassified} pages non classifiees")
        if st.button("Lancer la classification", key="migration_classify_maint"):
            if not gemini_key:
                st.error("Configurez GEMINI_API_KEY d'abord")
            elif unclassified == 0:
                st.info("✓ Aucune page a classifier")
            else:
                st.info(f"⏱️ Classification de {unclassified} pages en cours...")
                try:
                    from src.infrastructure.external_services.gemini_classifier import classify_and_save
                    result = classify_and_save(db, limit=unclassified)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"✅ {result['classified']} pages classifiees")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {e}")

    st.markdown("---")

    # === SECTION: MIGRATION FORMAT WINNING ADS ===
    st.subheader("🏆 Migration format Winning Ads")
    st.caption("Convertir les criteres au format lisible (≤4d & >15k)")

    from src.infrastructure.persistence.repositories import migrate_matched_criteria_format

    if st.button("🔄 Migrer le format des criteres", key="migrate_winning_format"):
        with st.spinner("Migration en cours..."):
            try:
                result = migrate_matched_criteria_format(db)
                st.success(f"✅ Migration terminee: {result['updated']}/{result['total']} winning ads mises a jour ({result['skipped']} deja au bon format)")
            except Exception as e:
                st.error(f"Erreur: {e}")

    st.markdown("---")

    # === SECTION: NETTOYAGE DES DOUBLONS ===
    st.subheader("🧹 Nettoyage des doublons")
    st.caption("Supprimez les entrees en doublon (garde les plus recentes).")

    with db.get_session() as session:
        ads_duplicates = session.query(
            AdsRecherche.ad_id,
            func.count(AdsRecherche.id).label('count')
        ).group_by(AdsRecherche.ad_id).having(func.count(AdsRecherche.id) > 1).count()

        winning_duplicates = session.query(
            WinningAds.ad_id,
            func.count(WinningAds.id).label('count')
        ).group_by(WinningAds.ad_id).having(func.count(WinningAds.id) > 1).count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Doublons Ads Recherche", ads_duplicates)
    col2.metric("Doublons Winning Ads", winning_duplicates)
    col3.metric("Total doublons", ads_duplicates + winning_duplicates)

    if ads_duplicates + winning_duplicates > 0:
        st.warning(f"⚠️ {ads_duplicates + winning_duplicates} doublons detectes")

        if st.button("🧹 Nettoyer les doublons", type="primary", key="cleanup_duplicates_maint"):
            with st.spinner("Nettoyage en cours..."):
                total_deleted = 0

                with db.get_session() as session:
                    duplicates_ads = session.query(AdsRecherche.ad_id).group_by(AdsRecherche.ad_id).having(func.count(AdsRecherche.id) > 1).all()
                    for (ad_id,) in duplicates_ads:
                        entries = session.query(AdsRecherche).filter(AdsRecherche.ad_id == ad_id).order_by(AdsRecherche.date_scan.desc()).all()
                        for entry in entries[1:]:
                            session.delete(entry)
                            total_deleted += 1
                    session.commit()

                with db.get_session() as session:
                    duplicates_winning = session.query(WinningAds.ad_id).group_by(WinningAds.ad_id).having(func.count(WinningAds.id) > 1).all()
                    for (ad_id,) in duplicates_winning:
                        entries = session.query(WinningAds).filter(WinningAds.ad_id == ad_id).order_by(WinningAds.date_scan.desc()).all()
                        for entry in entries[1:]:
                            session.delete(entry)
                            total_deleted += 1
                    session.commit()

                st.success(f"✅ {total_deleted} doublons supprimes")
                st.rerun()
    else:
        st.success("✅ Aucun doublon detecte")

    st.markdown("---")

    # === SECTION: ARCHIVAGE ===
    st.subheader("📦 Archivage des anciennes donnees")
    st.caption("Deplacez les donnees de plus de 90 jours vers les tables d'archive.")

    try:
        archive_stats = get_archive_stats(db)

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

        total_archivable = (
            archive_stats.get("suivi_page_archivable", 0) +
            archive_stats.get("liste_ads_recherche_archivable", 0) +
            archive_stats.get("winning_ads_archivable", 0)
        )

        if total_archivable > 0:
            st.warning(f"⚠️ {total_archivable:,} entrees peuvent etre archivees")

            col1, col2 = st.columns([1, 2])
            with col1:
                days_threshold = st.number_input("Seuil (jours)", min_value=30, max_value=365, value=90, key="archive_days_maint")

            if st.button("📦 Lancer l'archivage", type="primary", key="archive_btn_maint"):
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

    st.markdown("---")

    # === SECTION: RESET DATABASE ===
    st.subheader("⚠️ Reset de la base de donnees")
    st.caption("Supprime TOUTES les donnees sauf les utilisateurs. Cette action est irreversible!")

    st.error("**ATTENTION:** Cette action supprimera definitivement toutes les pages, ads, winning ads, favoris, collections, tags, blacklist, historiques de recherche, etc.")

    col1, col2 = st.columns(2)
    with col1:
        confirm_text = st.text_input(
            "Tapez 'RESET' pour confirmer",
            key="reset_confirm_input",
            placeholder="RESET"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        reset_disabled = confirm_text != "RESET"

        if st.button("🗑️ Reset Database", type="primary", disabled=reset_disabled, key="reset_db_btn"):
            with st.spinner("Suppression en cours..."):
                try:
                    from src.infrastructure.persistence.models import (
                        PageRecherche, SuiviPage, AdsRecherche, WinningAds,
                        SearchLog, SearchQueue, APICallLog,
                        PageSearchHistory, WinningAdSearchHistory,
                        Tag, PageTag, PageNote, Favorite, Collection, CollectionPage,
                        Blacklist, SavedFilter, ScheduledScan, ClassificationTaxonomy
                    )

                    tables_to_clear = [
                        PageSearchHistory, WinningAdSearchHistory,
                        APICallLog, SearchQueue, SearchLog,
                        WinningAds, AdsRecherche, SuiviPage,
                        PageTag, PageNote, CollectionPage, Collection,
                        Tag, Favorite, Blacklist, SavedFilter, ScheduledScan,
                        ClassificationTaxonomy, PageRecherche
                    ]

                    deleted_counts = {}
                    with db.get_session() as session:
                        for table in tables_to_clear:
                            try:
                                count = session.query(table).delete()
                                deleted_counts[table.__tablename__] = count
                            except Exception as table_error:
                                deleted_counts[table.__tablename__] = f"Erreur: {table_error}"

                    st.success("✅ Base de donnees reinitalisee (utilisateurs conserves)")
                    st.json(deleted_counts)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors du reset: {e}")
