"""
Value Objects du domaine.

Les Value Objects sont des objets immuables qui encapsulent
des valeurs avec leur logique de validation.

Caracteristiques:
    - Immuables (frozen dataclasses)
    - Valides par construction
    - Comparaison par valeur
    - Aucun identifiant propre
"""

from src.domain.value_objects.ad_id import AdId
from src.domain.value_objects.cms import CMS
from src.domain.value_objects.currency import Currency
from src.domain.value_objects.etat import Etat
from src.domain.value_objects.page_id import PageId
from src.domain.value_objects.reach import Reach
from src.domain.value_objects.role import Role, RoleLevel
from src.domain.value_objects.thematique import Thematique, ThematiqueClassification
from src.domain.value_objects.url import Url

__all__ = [
    "PageId",
    "AdId",
    "Etat",
    "CMS",
    "Thematique",
    "ThematiqueClassification",
    "Url",
    "Reach",
    "Currency",
    "Role",
    "RoleLevel",
]
