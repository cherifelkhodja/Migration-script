"""
Entites du domaine.

Les entites sont des objets metier avec une identite propre
et un cycle de vie. Contrairement aux Value Objects, deux entites
avec les memes attributs ne sont pas egales si leurs identifiants different.

Entites principales:
    - Page: Page Facebook avec ses metadonnees e-commerce
    - Ad: Annonce publicitaire Meta
    - WinningAd: Annonce performante (reach eleve + recente)
    - Collection: Groupe de pages creees par l'utilisateur
    - User: Utilisateur avec role et permissions
"""

from src.domain.entities.ad import Ad
from src.domain.entities.collection import Collection
from src.domain.entities.page import Page
from src.domain.entities.user import User
from src.domain.entities.winning_ad import WinningAd

__all__ = [
    "Page",
    "Ad",
    "WinningAd",
    "Collection",
    "User",
]
