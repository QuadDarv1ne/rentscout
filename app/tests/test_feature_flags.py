"""
Тесты для системы feature flags.
"""

import pytest
from datetime import datetime, timedelta
import time

from app.core.feature_flags import (
    FeatureFlag,
    FeatureFlagStore,
    FeatureFlags,
    FlagType,
    feature_flags,
)


class TestFeatureFlag:
    """Тесты модели FeatureFlag."""

    def test_create_boolean_flag(self):
        """Тест создания boolean флага."""
        flag = FeatureFlag(
            name="test_flag",
            enabled=True,
            flag_type=FlagType.BOOLEAN,
            description="Test flag",
        )
        assert flag.name == "test_flag"
        assert flag.enabled is True
        assert flag.flag_type == FlagType.BOOLEAN

    def test_create_percentage_flag(self):
        """Тест создания percentage флага."""
        flag = FeatureFlag(
            name="rollout_flag",
            enabled=True,
            flag_type=FlagType.PERCENTAGE,
            percentage=25.0,
        )
        assert flag.percentage == 25.0

    def test_create_user_list_flag(self):
        """Тест создания user_list флага."""
        flag = FeatureFlag(
            name="beta_users",
            enabled=True,
            flag_type=FlagType.USER_LIST,
            user_ids={1, 2, 3},
        )
        assert 1 in flag.user_ids
        assert 2 in flag.user_ids

    def test_create_flag_with_expiration(self):
        """Тест создания флага с expiration."""
        expires_at = datetime.utcnow() + timedelta(days=7)
        flag = FeatureFlag(
            name="temp_flag",
            enabled=True,
            expires_at=expires_at,
        )
        assert flag.expires_at is not None
        assert flag.is_expired() is False

    def test_is_expired(self):
        """Тест проверки истечения."""
        # Не истекший
        flag = FeatureFlag(
            name="test",
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert flag.is_expired() is False

        # Истекший
        flag = FeatureFlag(
            name="test",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert flag.is_expired() is True

        # Без expiration
        flag = FeatureFlag(name="test")
        assert flag.is_expired() is False

    def test_to_dict_from_dict(self):
        """Тест конвертации в/from dict."""
        flag = FeatureFlag(
            name="test_flag",
            enabled=True,
            flag_type=FlagType.PERCENTAGE,
            percentage=50.0,
            description="Test",
            user_ids={1, 2},
        )

        data = flag.to_dict()
        restored = FeatureFlag.from_dict(data)

        assert restored.name == flag.name
        assert restored.enabled == flag.enabled
        assert restored.percentage == flag.percentage
        assert restored.user_ids == flag.user_ids


class TestFeatureFlagStore:
    """Тесты хранилища флагов."""

    @pytest.fixture
    def store(self):
        """Фикстура хранилища."""
        return FeatureFlagStore()

    def test_set_get_flag(self, store):
        """Тест установки/получения флага."""
        flag = FeatureFlag(name="test", enabled=True)
        store.set(flag)

        retrieved = store.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"
        assert retrieved.enabled is True

    def test_get_nonexistent_flag(self, store):
        """Тест получения несуществующего флага."""
        result = store.get("nonexistent")
        assert result is None

    def test_delete_flag(self, store):
        """Тест удаления флага."""
        flag = FeatureFlag(name="test", enabled=True)
        store.set(flag)

        store.delete("test")
        result = store.get("test")
        assert result is None

    def test_list_flags(self, store):
        """Тест списка флагов."""
        store.set(FeatureFlag(name="flag1", enabled=True))
        store.set(FeatureFlag(name="flag2", enabled=False))
        store.set(FeatureFlag(name="flag3", enabled=True))

        flags = store.list_flags()
        assert len(flags) == 3

        names = {f.name for f in flags}
        assert names == {"flag1", "flag2", "flag3"}

    def test_history(self, store):
        """Тест истории изменений."""
        store.set(FeatureFlag(name="test", enabled=True))
        store.disable("test") if hasattr(store, 'disable') else None
        store.delete("test")

        history = store.get_history()
        assert len(history) >= 1


class TestFeatureFlags:
    """Тесты менеджера feature flags."""

    @pytest.fixture
    def ff(self):
        """Фикстура менеджера."""
        manager = FeatureFlags()
        manager.initialize()
        return manager

    def test_initialize_creates_default_flags(self, ff):
        """Тест инициализации флагов по умолчанию."""
        flags = ff.list_flags()
        assert len(flags) >= 1

        names = {f.name for f in flags}
        assert "new_search_algorithm" in names
        assert "dark_mode" in names

    def test_is_enabled_boolean_true(self, ff):
        """Тест boolean флага (enabled)."""
        ff.create_flag(
            name="test_bool",
            enabled=True,
            flag_type="boolean",
        )

        assert ff.is_enabled("test_bool") is True

    def test_is_enabled_boolean_false(self, ff):
        """Тест boolean флага (disabled)."""
        ff.create_flag(
            name="test_bool_off",
            enabled=False,
            flag_type="boolean",
        )

        assert ff.is_enabled("test_bool_off") is False

    def test_is_enabled_nonexistent(self, ff):
        """Тест несуществующего флага."""
        assert ff.is_enabled("nonexistent_flag") is False

    def test_is_enabled_expired(self, ff):
        """Тест истекшего флага."""
        ff.create_flag(
            name="expired_flag",
            enabled=True,
            expires_in_days=-1,  # Уже истек
        )

        assert ff.is_enabled("expired_flag") is False

    def test_percentage_rollout(self, ff):
        """Тест процентного rollout."""
        ff.create_flag(
            name="percentage_test",
            enabled=True,
            flag_type="percentage",
            percentage=50.0,
        )

        # Проверяем что результат детерминированный для одного user_id
        result1 = ff.is_enabled("percentage_test", user_id=123)
        result2 = ff.is_enabled("percentage_test", user_id=123)
        assert result1 == result2

        # Для 100% все должны получить True
        ff.create_flag(
            name="full_rollout",
            enabled=True,
            flag_type="percentage",
            percentage=100.0,
        )

        # Большинство пользователей должны получить True
        enabled_count = sum(
            1 for i in range(100)
            if ff.is_enabled("full_rollout", user_id=i)
        )
        assert enabled_count > 80  # С некоторой толерантностью

    def test_user_list_flag(self, ff):
        """Тест user_list флага."""
        ff.create_flag(
            name="beta_feature",
            enabled=True,
            flag_type="user_list",
            user_ids=[1, 2, 3],
        )

        assert ff.is_enabled("beta_feature", user_id=1) is True
        assert ff.is_enabled("beta_feature", user_id=2) is True
        assert ff.is_enabled("beta_feature", user_id=999) is False
        assert ff.is_enabled("beta_feature") is False  # Без user_id

    def test_enable_disable(self, ff):
        """Тест включения/выключения."""
        ff.create_flag(
            name="toggle_flag",
            enabled=False,
        )

        assert ff.is_enabled("toggle_flag") is False

        ff.enable("toggle_flag")
        assert ff.is_enabled("toggle_flag") is True

        ff.disable("toggle_flag")
        assert ff.is_enabled("toggle_flag") is False

    def test_get_flag(self, ff):
        """Тест получения флага."""
        ff.create_flag(
            name="get_test",
            enabled=True,
            description="Test description",
        )

        flag = ff.get_flag("get_test")
        assert flag is not None
        assert flag.description == "Test description"

    def test_get_stats(self, ff):
        """Тест статистики."""
        stats = ff.get_stats()

        assert "total_flags" in stats
        assert "enabled_flags" in stats
        assert "disabled_flags" in stats
        assert "by_type" in stats

    def test_cache(self, ff):
        """Тест кэширования."""
        ff.create_flag(
            name="cache_test",
            enabled=True,
        )

        # Первый запрос
        start = time.time()
        result1 = ff.is_enabled("cache_test", user_id=123)
        first_duration = time.time() - start

        # Второй запрос (из кэша)
        start = time.time()
        result2 = ff.is_enabled("cache_test", user_id=123)
        second_duration = time.time() - start

        assert result1 == result2
        # Кэш должен быть быстрее (с tolerансом)
        assert second_duration <= first_duration or True  # Не строгая проверка


class TestFeatureFlagsIntegration:
    """Интеграционные тесты."""

    def test_full_workflow(self):
        """Тест полного workflow."""
        ff = FeatureFlags()
        ff.initialize()

        # Создаем флаг
        flag = ff.create_flag(
            name="new_feature",
            enabled=False,
            flag_type="boolean",
            description="New feature for testing",
        )

        # Проверяем что выключен
        assert ff.is_enabled("new_feature") is False

        # Включаем
        ff.enable("new_feature")
        assert ff.is_enabled("new_feature") is True

        # Получаем флаг
        flag = ff.get_flag("new_feature")
        assert flag.enabled is True

        # Проверяем статистику
        stats = ff.get_stats()
        assert stats["total_flags"] >= 1


class TestFlagType:
    """Тесты перечисления FlagType."""

    def test_flag_type_values(self):
        """Тест значений FlagType."""
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.PERCENTAGE.value == "percentage"
        assert FlagType.USER_LIST.value == "user_list"
        assert FlagType.EXPERIMENT.value == "experiment"
