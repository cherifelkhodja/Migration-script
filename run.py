#!/usr/bin/env python3
"""
Point d'entree principal pour lancer le dashboard Meta Ads Analyzer.

Ce script est le lanceur recommande pour demarrer l'application
Streamlit en mode developpement ou production locale.

Usage:
------
    python3 run.py
    # ou directement:
    streamlit run app/dashboard.py

Comportement:
-------------
1. Verifie que le fichier dashboard.py existe
2. Lance Streamlit avec les options par defaut
3. Desactive la collecte de statistiques Streamlit

Options Streamlit passees:
--------------------------
- --browser.gatherUsageStats=false : Desactive la telemetrie

Erreurs courantes:
------------------
- "dashboard.py introuvable" : Verifier la structure du projet
- "Streamlit non trouve" : pip install streamlit
- "FileNotFoundError" : pip install -r requirements.txt

Note:
-----
Pour le deploiement Railway/production, utiliser plutot:
    streamlit run src/presentation/streamlit/dashboard.py --server.port $PORT
"""
import sys
import subprocess
from pathlib import Path


def main():
    """Lance l'application Streamlit"""
    # S'assurer qu'on est dans le bon répertoire
    script_dir = Path(__file__).parent
    dashboard_path = script_dir / "app" / "dashboard.py"

    if not dashboard_path.exists():
        print(f"Erreur: {dashboard_path} introuvable")
        sys.exit(1)

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(dashboard_path),
            "--browser.gatherUsageStats=false"
        ], check=True)
    except KeyboardInterrupt:
        print("\nApplication arrêtée.")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du lancement: {e}")
        print("\nAssurez-vous que Streamlit est installé:")
        print("  pip3 install streamlit")
        sys.exit(1)
    except FileNotFoundError:
        print("Python ou Streamlit non trouvé.")
        print("\nInstallez les dépendances:")
        print("  pip3 install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
