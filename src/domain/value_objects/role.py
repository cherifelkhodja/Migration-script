"""
Value Object Role - Roles utilisateur et permissions.

Definit les differents niveaux d'acces dans l'application
avec leurs permissions associees.

Roles disponibles:
------------------
- admin: Acces complet, gestion utilisateurs
- analyst: Recherche, analyse, modification
- viewer: Consultation seule

Permissions:
------------
Les permissions sont definies par page/fonctionnalite :
- search: Lancer des recherches Meta API
- pages_edit: Modifier les pages (tags, notes, favoris)
- pages_view: Consulter les pages
- winning_view: Voir les winning ads
- settings: Acceder aux parametres
- users_manage: Gerer les utilisateurs
- blacklist: Gerer la blacklist
- scheduled_scans: Gerer les scans programmes
- export: Exporter les donnees
"""

from dataclasses import dataclass
from enum import Enum


class RoleLevel(Enum):
    """Niveaux de role utilisateur."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

    def __str__(self) -> str:
        return self.value


# Matrice des permissions par role
ROLE_PERMISSIONS: dict[RoleLevel, set[str]] = {
    RoleLevel.ADMIN: {
        "dashboard_view",
        "search",
        "search_background",
        "pages_view",
        "pages_edit",
        "winning_view",
        "analytics_view",
        "monitoring_view",
        "favorites_edit",
        "collections_edit",
        "tags_edit",
        "blacklist_edit",
        "scheduled_scans_edit",
        "settings_view",
        "settings_edit",
        "users_manage",
        "export",
        "maintenance",
    },
    RoleLevel.ANALYST: {
        "dashboard_view",
        "search",
        "search_background",
        "pages_view",
        "pages_edit",
        "winning_view",
        "analytics_view",
        "monitoring_view",
        "favorites_edit",
        "collections_edit",
        "tags_edit",
        "blacklist_edit",
        "export",
    },
    RoleLevel.VIEWER: {
        "dashboard_view",
        "pages_view",
        "winning_view",
        "analytics_view",
        "monitoring_view",
    },
}

# Pages accessibles par role
PAGE_PERMISSIONS: dict[str, set[str]] = {
    "Dashboard": {"dashboard_view"},
    "Search Ads": {"search"},
    "Historique": {"search"},
    "Background Searches": {"search_background"},
    "Pages / Shops": {"pages_view"},
    "Watchlists": {"pages_view"},
    "Alerts": {"monitoring_view"},
    "Favoris": {"favorites_edit"},
    "Collections": {"collections_edit"},
    "Tags": {"tags_edit"},
    "Monitoring": {"monitoring_view"},
    "Analytics": {"analytics_view"},
    "Winning Ads": {"winning_view"},
    "Creative Analysis": {"analytics_view"},
    "Scheduled Scans": {"scheduled_scans_edit"},
    "Blacklist": {"blacklist_edit"},
    "Settings": {"settings_view"},
    "Users": {"users_manage"},
}


@dataclass(frozen=True)
class Role:
    """
    Role utilisateur avec ses permissions.

    Value Object immutable representant le niveau d'acces
    d'un utilisateur dans l'application.

    Attributes:
        level: Niveau du role (admin, analyst, viewer).

    Example:
        >>> role = Role.admin()
        >>> role.can("search")
        True
        >>> role.can("users_manage")
        True
        >>> viewer = Role.viewer()
        >>> viewer.can("search")
        False
    """

    level: RoleLevel

    @classmethod
    def admin(cls) -> "Role":
        """Cree un role administrateur."""
        return cls(level=RoleLevel.ADMIN)

    @classmethod
    def analyst(cls) -> "Role":
        """Cree un role analyste."""
        return cls(level=RoleLevel.ANALYST)

    @classmethod
    def viewer(cls) -> "Role":
        """Cree un role lecteur."""
        return cls(level=RoleLevel.VIEWER)

    @classmethod
    def from_string(cls, role_str: str) -> "Role":
        """
        Cree un Role depuis une chaine.

        Args:
            role_str: Nom du role (admin, analyst, viewer).

        Returns:
            Instance de Role correspondante.

        Raises:
            ValueError: Si le role est inconnu.
        """
        try:
            level = RoleLevel(role_str.lower().strip())
            return cls(level=level)
        except ValueError:
            raise ValueError(f"Role inconnu: {role_str}")

    @property
    def permissions(self) -> set[str]:
        """Retourne l'ensemble des permissions du role."""
        return ROLE_PERMISSIONS.get(self.level, set())

    def can(self, permission: str) -> bool:
        """
        Verifie si le role a une permission.

        Args:
            permission: Nom de la permission a verifier.

        Returns:
            True si le role a cette permission.
        """
        return permission in self.permissions

    def can_access_page(self, page_name: str) -> bool:
        """
        Verifie si le role peut acceder a une page.

        Args:
            page_name: Nom de la page Streamlit.

        Returns:
            True si le role peut acceder a cette page.
        """
        required_permissions = PAGE_PERMISSIONS.get(page_name, set())
        if not required_permissions:
            # Page sans restriction = acces libre
            return True
        return bool(self.permissions & required_permissions)

    @property
    def is_admin(self) -> bool:
        """True si role administrateur."""
        return self.level == RoleLevel.ADMIN

    @property
    def is_analyst(self) -> bool:
        """True si role analyste."""
        return self.level == RoleLevel.ANALYST

    @property
    def is_viewer(self) -> bool:
        """True si role lecteur."""
        return self.level == RoleLevel.VIEWER

    @property
    def display_name(self) -> str:
        """Nom affichable du role."""
        names = {
            RoleLevel.ADMIN: "Administrateur",
            RoleLevel.ANALYST: "Analyste",
            RoleLevel.VIEWER: "Lecteur",
        }
        return names.get(self.level, str(self.level))

    @property
    def icon(self) -> str:
        """Icone du role."""
        icons = {
            RoleLevel.ADMIN: "👑",
            RoleLevel.ANALYST: "📊",
            RoleLevel.VIEWER: "👁️",
        }
        return icons.get(self.level, "👤")

    def __str__(self) -> str:
        return str(self.level)

    def __repr__(self) -> str:
        return f"Role({self.level.value})"
