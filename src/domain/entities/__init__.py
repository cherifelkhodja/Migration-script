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
"""

from src.domain.entities.page import Page
from src.domain.entities.ad import Ad
from src.domain.entities.winning_ad import WinningAd
from src.domain.entities.collection import Collection

__all__ = [
    "Page",
    "Ad",
    "WinningAd",
    "Collection",
]
