"""
StateStorage Port - Interface pour le stockage d'etats temporaires.

Responsabilite unique:
----------------------
Definir le contrat pour stocker/recuperer des etats (OAuth, CSRF, etc).

Usage:
------
En production, utiliser Redis. En dev, utiliser un dict en memoire.
"""

from abc import ABC, abstractmethod
from typing import Optional


class StateStorage(ABC):
    """
    Interface pour le stockage d'etats temporaires.

    Utilisee pour les states OAuth, tokens CSRF, etc.
    """

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int = 600) -> None:
        """
        Stocke une valeur avec TTL.

        Args:
            key: Cle unique.
            value: Valeur a stocker.
            ttl_seconds: Duree de vie en secondes (defaut: 10 min).
        """
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """
        Recupere une valeur.

        Args:
            key: Cle a recuperer.

        Returns:
            Valeur si existe, None sinon.
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Supprime une valeur.

        Args:
            key: Cle a supprimer.

        Returns:
            True si supprime, False si inexistant.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Verifie si une cle existe.

        Args:
            key: Cle a verifier.

        Returns:
            True si existe, False sinon.
        """
        pass
