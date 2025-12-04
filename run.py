#!/usr/bin/env python3
"""
Point d'entrée pour lancer le dashboard Meta Ads Analyzer
"""
import sys
import subprocess


def main():
    """Lance l'application Streamlit"""
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "app/dashboard.py",
            "--server.headless=true",
            "--browser.gatherUsageStats=false"
        ], check=True)
    except KeyboardInterrupt:
        print("\nApplication arrêtée.")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du lancement: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
