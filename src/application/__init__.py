"""
Application Layer - Orchestration des Use Cases.

Cette couche contient:
    - ports/: Interfaces (abstractions) pour les adapters
    - use_cases/: Cas d'utilisation de l'application
    - dto/: Data Transfer Objects

Principes:
    - Depend uniquement du domaine
    - Definit les interfaces (ports) que les adapters implementent
    - Orchestre les entites du domaine via les use cases
"""

__all__ = []
