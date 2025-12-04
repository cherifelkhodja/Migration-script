#!/usr/bin/env python3
"""
Point d'entrée pour lancer le dashboard Meta Ads Analyzer

Usage:
    python3 run.py
    ou
    streamlit run app/dashboard.py
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
