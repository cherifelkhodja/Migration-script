"""
Tests unitaires pour le TenantContext.

Le TenantContext gere l'isolation des donnees par utilisateur.
Il fournit:
- Le user_id courant
- La verification si l'utilisateur est admin (voit tout)
- Le filtrage des requetes selon le tenant

Patterns:
---------
- Port/Adapter: TenantContext est un port, StreamlitTenantContext est l'adapter
- Context Pattern: Le tenant est propage via le contexte de session
"""

import pytest
from uuid import uuid4


class TestTenantContext:
    """Tests pour le port TenantContext."""

    def test_current_user_id_returns_user_id(self):
        """current_user_id retourne le UserId de l'utilisateur courant."""
        from src.domain.ports.tenant_context import TenantContext
        from src.domain.value_objects.user_id import UserId

        # Mock implementation
        class MockTenantContext(TenantContext):
            def __init__(self, user_id):
                self._user_id = user_id
                self._is_admin = False

            @property
            def current_user_id(self):
                return self._user_id

            @property
            def is_admin(self):
                return self._is_admin

        uid = UserId(uuid4())
        ctx = MockTenantContext(uid)

        assert ctx.current_user_id == uid

    def test_is_admin_returns_boolean(self):
        """is_admin retourne True si l'utilisateur est admin."""
        from src.domain.ports.tenant_context import TenantContext
        from src.domain.value_objects.user_id import UserId

        class MockTenantContext(TenantContext):
            def __init__(self, user_id, is_admin=False):
                self._user_id = user_id
                self._is_admin = is_admin

            @property
            def current_user_id(self):
                return self._user_id

            @property
            def is_admin(self):
                return self._is_admin

        uid = UserId(uuid4())
        ctx = MockTenantContext(uid, is_admin=True)

        assert ctx.is_admin is True

    def test_should_filter_returns_true_for_non_admin(self):
        """should_filter retourne True pour les non-admins."""
        from src.domain.ports.tenant_context import TenantContext
        from src.domain.value_objects.user_id import UserId

        class MockTenantContext(TenantContext):
            def __init__(self, user_id, is_admin=False):
                self._user_id = user_id
                self._is_admin = is_admin

            @property
            def current_user_id(self):
                return self._user_id

            @property
            def is_admin(self):
                return self._is_admin

        uid = UserId(uuid4())
        ctx = MockTenantContext(uid, is_admin=False)

        assert ctx.should_filter is True

    def test_should_filter_returns_false_for_admin(self):
        """should_filter retourne False pour les admins."""
        from src.domain.ports.tenant_context import TenantContext
        from src.domain.value_objects.user_id import UserId

        class MockTenantContext(TenantContext):
            def __init__(self, user_id, is_admin=False):
                self._user_id = user_id
                self._is_admin = is_admin

            @property
            def current_user_id(self):
                return self._user_id

            @property
            def is_admin(self):
                return self._is_admin

        uid = UserId(uuid4())
        ctx = MockTenantContext(uid, is_admin=True)

        assert ctx.should_filter is False


class TestTenantAwareMixin:
    """Tests pour le mixin TenantAware applique aux entites."""

    def test_entity_has_owner_id(self):
        """Une entite TenantAware a un owner_id."""
        from src.domain.ports.tenant_context import TenantAwareMixin
        from src.domain.value_objects.user_id import UserId
        from dataclasses import dataclass

        @dataclass
        class MyEntity(TenantAwareMixin):
            name: str
            owner_id: UserId = None

        uid = UserId(uuid4())
        entity = MyEntity(name="test", owner_id=uid)

        assert entity.owner_id == uid

    def test_belongs_to_checks_ownership(self):
        """belongs_to verifie si l'entite appartient a un utilisateur."""
        from src.domain.ports.tenant_context import TenantAwareMixin
        from src.domain.value_objects.user_id import UserId
        from dataclasses import dataclass

        @dataclass
        class MyEntity(TenantAwareMixin):
            name: str
            owner_id: UserId = None

        uid = UserId(uuid4())
        other_uid = UserId(uuid4())
        entity = MyEntity(name="test", owner_id=uid)

        assert entity.belongs_to(uid) is True
        assert entity.belongs_to(other_uid) is False

    def test_belongs_to_system_user_is_public(self):
        """Une entite sans owner (SYSTEM_USER) est accessible a tous."""
        from src.domain.ports.tenant_context import TenantAwareMixin
        from src.domain.value_objects.user_id import UserId, SYSTEM_USER
        from dataclasses import dataclass

        @dataclass
        class MyEntity(TenantAwareMixin):
            name: str
            owner_id: UserId = None

        entity = MyEntity(name="test", owner_id=SYSTEM_USER)
        random_user = UserId(uuid4())

        # System-owned entities are accessible to everyone
        assert entity.is_public is True
