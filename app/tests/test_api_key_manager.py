"""
Тесты для API Key Manager.
"""
import pytest
import time
from app.utils.api_key_manager import (
    api_key_manager,
    APIKeyManager,
    APIKey,
)


class TestAPIKeyGeneration:
    """Тесты генерации API ключей."""

    def test_key_format(self):
        """Тест формата ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test Key"
        )
        
        assert plain_key.startswith("rs_api_")
        assert len(plain_key) == 40  # rs_api_ (8) + 32 hex символа

    def test_key_uniqueness(self):
        """Тест уникальности ключей."""
        manager = APIKeyManager()
        
        keys = set()
        for i in range(100):
            plain_key, _ = manager.create_key(
                user_id=i,
                name=f"Key {i}"
            )
            keys.add(plain_key)
        
        assert len(keys) == 100  # Все ключи уникальны

    def test_key_prefix(self):
        """Тест префикса ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test"
        )
        
        assert api_key.key_prefix == plain_key[8:16]
        assert len(api_key.key_prefix) == 8


class TestAPIKeyVerification:
    """Тесты проверки ключей."""

    def test_valid_key(self):
        """Тест валидного ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test"
        )
        
        result = manager.verify_key(plain_key)
        
        assert result is not None
        assert result.user_id == 1
        assert result.name == "Test"
        assert result.is_active is True

    def test_invalid_key(self):
        """Тест неверного ключа."""
        manager = APIKeyManager()
        
        result = manager.verify_key("rs_api_invalidkey123")
        
        assert result is None

    def test_wrong_format_key(self):
        """Тест ключа неверного формата."""
        manager = APIKeyManager()
        
        result = manager.verify_key("invalid_key_format")
        
        assert result is None

    def test_key_usage_count(self):
        """Тест счётчика использования."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test"
        )
        
        # Используем ключ 5 раз
        for i in range(5):
            manager.verify_key(plain_key)
        
        # Проверяем счётчик
        result = manager.verify_key(plain_key)
        assert result.usage_count == 6  # 5 + последняя проверка

    def test_key_last_used(self):
        """Тест времени последнего использования."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test"
        )
        
        assert api_key.last_used_at is None
        
        manager.verify_key(plain_key)
        
        result = manager.verify_key(plain_key)
        assert result.last_used_at is not None


class TestAPIKeyExpiration:
    """Тесты истечения срока действия."""

    def test_expiring_key(self):
        """Тест ключа с сроком действия."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            expires_in_days=30
        )
        
        assert api_key.expires_at is not None
        assert api_key.is_expired() is False
        assert api_key.is_valid() is True

    def test_expired_key(self):
        """Тест истёкшего ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            expires_in_days=0  # Истекает сразу
        )
        
        # Устанавливаем время в прошлое
        api_key.expires_at = time.time() - 1
        
        assert api_key.is_expired() is True
        assert api_key.is_valid() is False
        
        result = manager.verify_key(plain_key)
        assert result is None

    def test_non_expiring_key(self):
        """Тест бессрочного ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            expires_in_days=None
        )
        
        assert api_key.expires_at is None
        assert api_key.is_expired() is False


class TestAPIKeyIPRestriction:
    """Тесты ограничения по IP."""

    def test_allowed_ip(self):
        """Тест разрешённого IP."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            allowed_ips=["192.168.1.1", "10.0.0.1"]
        )
        
        result = manager.verify_key(plain_key, ip="192.168.1.1")
        assert result is not None

    def test_disallowed_ip(self):
        """Тест неразрешённого IP."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            allowed_ips=["192.168.1.1"]
        )
        
        result = manager.verify_key(plain_key, ip="192.168.1.2")
        assert result is None

    def test_no_ip_restriction(self):
        """Тест без ограничения по IP."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            allowed_ips=None
        )
        
        result = manager.verify_key(plain_key, ip="any.ip.address")
        assert result is not None


class TestAPIKeyRevocation:
    """Тесты отзыва ключей."""

    def test_revoke_key(self):
        """Тест отзыва ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test"
        )
        
        # Отзываем ключ
        result = manager.revoke_key(user_id=1, key_hash=api_key.key_hash)
        assert result is True
        
        # Проверяем что ключ не работает
        verify_result = manager.verify_key(plain_key)
        assert verify_result is None

    def test_revoke_nonexistent_key(self):
        """Тест отзыва несуществующего ключа."""
        manager = APIKeyManager()
        
        result = manager.revoke_key(user_id=1, key_hash="nonexistent")
        assert result is False


class TestAPIKeyRotation:
    """Тесты ротации ключей."""

    def test_rotate_key(self):
        """Тест ротации ключа."""
        manager = APIKeyManager()
        old_plain_key, old_api_key = manager.create_key(
            user_id=1,
            name="Original"
        )
        
        # Ротируем ключ
        result = manager.rotate_key(
            user_id=1,
            old_key_hash=old_api_key.key_hash
        )
        
        assert result is not None
        new_plain_key, new_api_key = result
        
        # Старый ключ не работает
        assert manager.verify_key(old_plain_key) is None
        
        # Новый ключ работает
        verify_result = manager.verify_key(new_plain_key)
        assert verify_result is not None
        assert verify_result.name == "Original (rotated)"

    def test_rotate_nonexistent_key(self):
        """Тест ротации несуществующего ключа."""
        manager = APIKeyManager()
        
        result = manager.rotate_key(
            user_id=1,
            old_key_hash="nonexistent"
        )
        
        assert result is None


class TestAPIKeyManagement:
    """Тесты управления ключами."""

    def test_get_keys_for_user(self):
        """Тест получения ключей пользователя."""
        manager = APIKeyManager()
        
        # Создаём 3 ключа
        for i in range(3):
            manager.create_key(user_id=1, name=f"Key {i}")
        
        keys = manager.get_keys_for_user(user_id=1)
        assert len(keys) == 3

    def test_get_active_keys(self):
        """Тест получения активных ключей."""
        manager = APIKeyManager()
        
        # Создаём 2 активных и 1 отозванный
        plain_key1, api_key1 = manager.create_key(user_id=1, name="Active 1")
        manager.create_key(user_id=1, name="Active 2")
        plain_key2, api_key2 = manager.create_key(user_id=1, name="Revoked")
        manager.revoke_key(user_id=1, key_hash=api_key2.key_hash)
        
        active_keys = manager.get_active_keys(user_id=1)
        assert len(active_keys) == 2

    def test_delete_key(self):
        """Тест удаления ключа."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(user_id=1, name="Test")
        
        # Удаляем ключ
        result = manager.delete_key(user_id=1, key_hash=api_key.key_hash)
        assert result is True
        
        # Ключ удалён
        keys = manager.get_keys_for_user(user_id=1)
        assert len(keys) == 0

    def test_get_usage_stats(self):
        """Тест статистики использования."""
        manager = APIKeyManager()
        
        # Создаём ключи
        plain_key1, api_key1 = manager.create_key(user_id=1, name="Key 1")
        manager.create_key(user_id=1, name="Key 2")
        
        # Используем первый ключ
        manager.verify_key(plain_key1)
        manager.verify_key(plain_key1)
        
        stats = manager.get_usage_stats(user_id=1)
        
        assert stats["total_keys"] == 2
        assert stats["active_keys"] == 2
        assert stats["total_usage"] == 2


class TestAPIKeyModel:
    """Тесты модели APIKey."""

    def test_to_dict(self):
        """Тест конвертации в словарь."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(
            user_id=1,
            name="Test",
            expires_in_days=30
        )
        
        data = api_key.to_dict()
        
        assert "key_prefix" in data
        assert "user_id" in data
        assert "name" in data
        assert "created_at" in data
        assert "key_hash" not in data  # Не включаем хеш по умолчанию

    def test_to_dict_with_hash(self):
        """Тест конвертации с хешем."""
        manager = APIKeyManager()
        plain_key, api_key = manager.create_key(user_id=1, name="Test")
        
        data = api_key.to_dict(include_hash=True)
        
        assert "key_hash" in data
        assert data["key_hash"] == api_key.key_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
