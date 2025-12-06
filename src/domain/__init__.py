"""
Domain Layer - Coeur metier de l'application.

Ce module contient:
    - entities/: Entites riches du domaine (Page, Ad, WinningAd)
    - value_objects/: Objets valeur immuables (PageId, Etat, CMS)
    - services/: Services metier purs (detection winning ads, classification)
    - events/: Evenements du domaine
    - exceptions: Exceptions metier

Principes:
    - AUCUNE dependance vers les couches externes
    - Logique metier pure
    - Testable sans infrastructure
"""

from src.domain.exceptions import (
    DomainException,
    InvalidAdIdError,
    InvalidCMSError,
    InvalidEtatError,
    InvalidPageIdError,
)

__all__ = [
    "DomainException",
    "InvalidPageIdError",
    "InvalidAdIdError",
    "InvalidEtatError",
    "InvalidCMSError",
]
