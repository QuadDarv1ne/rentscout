import os

import pytest
from unittest.mock import patch

from app.core.config import Settings, settings


def test_settings_default_values():
    """Тест значений конфигурации по умолчанию."""
    # Проверяем значения по умолчанию
    assert settings.APP_NAME == "RentScout"
    # REDIS_URL может быть либо для Docker, либо для localhost (в зависимости от окружения)
    assert settings.REDIS_URL in ["redis://redis:6379/0", "redis://localhost:6379/0"]
    # Elasticsearch может быть в Docker или по умолчанию
    assert "elasticsearch" in settings.ELASTICSEARCH_URL or "localhost" in settings.ELASTICSEARCH_URL
    assert settings.PROXY_ENABLED is False
    assert settings.CIAN_MAX_RETRIES == 3
    assert settings.AVITO_RATE_LIMIT == 5
    assert settings.RATE_LIMIT_WINDOW == 60


def test_settings_from_environment_variables():
    """Тест загрузки конфигурации из переменных окружения."""
    # Мокаем переменные окружения
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "TestApp",
            "REDIS_URL": "redis://localhost:6379/1",
            "ELASTICSEARCH_URL": "http://localhost:9200",
            "PROXY_ENABLED": "True",
            "CIAN_MAX_RETRIES": "5",
            "AVITO_RATE_LIMIT": "10",
            "RATE_LIMIT_WINDOW": "120",
        },
    ):
        # Создаем новый экземпляр Settings для теста
        test_settings = Settings()

        # Проверяем, что значения загрузились из переменных окружения
        assert test_settings.APP_NAME == "TestApp"
        assert test_settings.REDIS_URL == "redis://localhost:6379/1"
        assert test_settings.ELASTICSEARCH_URL == "http://localhost:9200"
        assert test_settings.PROXY_ENABLED is True
        assert test_settings.CIAN_MAX_RETRIES == 5
        assert test_settings.AVITO_RATE_LIMIT == 10
        assert test_settings.RATE_LIMIT_WINDOW == 120


def test_settings_type_validation():
    """Тест валидации типов в конфигурации."""
    # Проверяем, что числовые значения имеют правильный тип
    assert isinstance(settings.CIAN_MAX_RETRIES, int)
    assert isinstance(settings.AVITO_RATE_LIMIT, int)
    assert isinstance(settings.RATE_LIMIT_WINDOW, int)

    # Проверяем, что булевы значения имеют правильный тип
    assert isinstance(settings.PROXY_ENABLED, bool)

    # Проверяем, что строковые значения имеют правильный тип
    assert isinstance(settings.APP_NAME, str)
    assert isinstance(settings.REDIS_URL, str)
    assert isinstance(settings.ELASTICSEARCH_URL, str)


def test_settings_singleton():
    """Тест того, что settings является синглтоном."""
    from app.core.config import settings as settings1
    from app.core.config import settings as settings2

    # Проверяем, что оба импорта ссылаются на один и тот же объект
    assert settings1 is settings2
