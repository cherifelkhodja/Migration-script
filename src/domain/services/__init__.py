"""
Services du domaine.

Les services du domaine contiennent la logique metier
qui n'appartient pas naturellement a une entite specifique.
Ils sont purs et n'ont aucune dependance externe.
"""

from src.domain.services.page_state_calculator import PageStateCalculator
from src.domain.services.winning_ad_detector import WinningAdDetector

__all__ = [
    "WinningAdDetector",
    "PageStateCalculator",
]
