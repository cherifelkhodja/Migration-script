"""
Tests unitaires pour le Value Object UserId.

Verifie le comportement du UserId pour le multi-tenancy:
- Creation depuis UUID
- Creation depuis string
- Egalite et hash
- Cas SYSTEM_USER pour les operations systeme
"""

import pytest
from uuid import UUID, uuid4


class TestUserId:
    """Tests pour le Value Object UserId."""

    def test_create_from_uuid(self):
        """UserId peut etre cree depuis un UUID."""
        from src.domain.value_objects.user_id import UserId

        uid = uuid4()
        user_id = UserId(uid)

        assert user_id.value == uid

    def test_create_from_string(self):
        """UserId peut etre cree depuis une string UUID."""
        from src.domain.value_objects.user_id import UserId

        uid_str = "550e8400-e29b-41d4-a716-446655440000"
        user_id = UserId.from_string(uid_str)

        assert str(user_id.value) == uid_str

    def test_create_from_invalid_string_raises(self):
        """UserId leve une erreur si la string est invalide."""
        from src.domain.value_objects.user_id import UserId

        with pytest.raises(ValueError):
            UserId.from_string("not-a-uuid")

    def test_equality_same_uuid(self):
        """Deux UserId avec le meme UUID sont egaux."""
        from src.domain.value_objects.user_id import UserId

        uid = uuid4()
        user_id1 = UserId(uid)
        user_id2 = UserId(uid)

        assert user_id1 == user_id2

    def test_equality_different_uuid(self):
        """Deux UserId avec des UUID differents ne sont pas egaux."""
        from src.domain.value_objects.user_id import UserId

        user_id1 = UserId(uuid4())
        user_id2 = UserId(uuid4())

        assert user_id1 != user_id2

    def test_hash_same_uuid(self):
        """Deux UserId avec le meme UUID ont le meme hash."""
        from src.domain.value_objects.user_id import UserId

        uid = uuid4()
        user_id1 = UserId(uid)
        user_id2 = UserId(uid)

        assert hash(user_id1) == hash(user_id2)

    def test_can_be_used_in_set(self):
        """UserId peut etre utilise dans un set."""
        from src.domain.value_objects.user_id import UserId

        uid = uuid4()
        user_id1 = UserId(uid)
        user_id2 = UserId(uid)

        s = {user_id1, user_id2}
        assert len(s) == 1

    def test_str_representation(self):
        """UserId a une representation string lisible."""
        from src.domain.value_objects.user_id import UserId

        uid_str = "550e8400-e29b-41d4-a716-446655440000"
        user_id = UserId.from_string(uid_str)

        assert str(user_id) == uid_str

    def test_system_user_constant(self):
        """SYSTEM_USER est un UserId special pour les operations systeme."""
        from src.domain.value_objects.user_id import UserId, SYSTEM_USER

        assert isinstance(SYSTEM_USER, UserId)
        assert SYSTEM_USER.is_system

    def test_regular_user_is_not_system(self):
        """Un UserId normal n'est pas le SYSTEM_USER."""
        from src.domain.value_objects.user_id import UserId

        user_id = UserId(uuid4())
        assert not user_id.is_system

    def test_from_any_uuid(self):
        """from_any accepte un UUID."""
        from src.domain.value_objects.user_id import UserId

        uid = uuid4()
        user_id = UserId.from_any(uid)
        assert user_id.value == uid

    def test_from_any_string(self):
        """from_any accepte une string."""
        from src.domain.value_objects.user_id import UserId

        uid_str = "550e8400-e29b-41d4-a716-446655440000"
        user_id = UserId.from_any(uid_str)
        assert str(user_id.value) == uid_str

    def test_from_any_user_id(self):
        """from_any accepte un UserId existant."""
        from src.domain.value_objects.user_id import UserId

        original = UserId(uuid4())
        user_id = UserId.from_any(original)
        assert user_id == original

    def test_from_any_none_returns_system(self):
        """from_any avec None retourne SYSTEM_USER."""
        from src.domain.value_objects.user_id import UserId, SYSTEM_USER

        user_id = UserId.from_any(None)
        assert user_id == SYSTEM_USER
