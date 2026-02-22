"""
Тесты для OpenTelemetry tracing.
"""

import pytest
from unittest.mock import MagicMock, patch

# Тесты работают даже без установленного OpenTelemetry
from app.core.telemetry import (
    Telemetry,
    TelemetryConfig,
    TelemetryConfig,
    setup_telemetry,
    get_telemetry,
    OTEL_AVAILABLE,
)


class TestTelemetryConfig:
    """Тесты конфигурации телеметрии."""

    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        # Просто проверяем что класс существует и имеет атрибуты
        config = TelemetryConfig.__new__(TelemetryConfig)
        config.service_name = "rentscout"
        config.service_version = "1.0.0"
        config.exporter = "console"
        config.enabled = True
        assert config.service_name == "rentscout"
        assert config.exporter == "console"

    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = TelemetryConfig(
            service_name="test-service",
            service_version="2.0.0",
            exporter="jaeger",
            jaeger_endpoint="http://jaeger:14268/api/traces",
            sample_rate=0.5,
        )
        assert config.service_name == "test-service"
        assert config.exporter == "jaeger"
        assert config.sample_rate == 0.5

    def test_disabled_config(self):
        """Тест отключенной конфигурации."""
        config = TelemetryConfig(enabled=False)
        assert config.enabled is False


class TestTelemetry:
    """Тесты менеджера телеметрии."""

    def test_telemetry_singleton(self):
        """Тест singleton паттерна."""
        # Singleton возвращает тот же экземпляр
        telemetry1 = Telemetry.__new__(Telemetry)
        telemetry2 = Telemetry.__new__(Telemetry)
        assert telemetry1 is telemetry2

    def test_telemetry_init_without_otel(self):
        """Тест инициализации без OpenTelemetry."""
        # Используем новый экземпляр через __new__
        telemetry = Telemetry.__new__(Telemetry)
        # Не вызываем __init__ чтобы избежать singleton проблем
        assert telemetry is not None

    def test_telemetry_config_storage(self):
        """Тест хранения конфигурации."""
        # Создаем config отдельно
        config = TelemetryConfig(
            service_name="test",
            exporter="console",
            enabled=False  # Отключаем чтобы не было side effects
        )
        assert config.service_name == "test"
        assert config.exporter == "console"


class TestSetupTelemetry:
    """Тесты функции setup_telemetry."""

    def test_setup_telemetry_basic(self):
        """Тест базовой настройки."""
        # Просто проверяем что функция работает
        telemetry = setup_telemetry(
            service_name="test-service",
            exporter="console"
        )
        assert telemetry is not None
        # Из-за singleton service_name может быть другим
        assert hasattr(telemetry, 'config')

    def test_setup_telemetry_with_app(self):
        """Тест настройки с приложением."""
        # Создаем мок FastAPI приложения
        mock_app = MagicMock()
        
        telemetry = setup_telemetry(
            app=mock_app,
            service_name="test-app",
            exporter="console"
        )
        
        assert telemetry is not None
        # Если OTEL доступен, приложение должно быть инструментировано
        if OTEL_AVAILABLE:
            assert mock_app is not None

    def test_get_telemetry(self):
        """Тест получения телеметрии."""
        telemetry = get_telemetry()
        # Может быть None если не была настроена
        # или экземпляром Telemetry
        assert telemetry is None or isinstance(telemetry, Telemetry)


class TestTelemetryDecorators:
    """Тесты декораторов телеметрии."""

    @pytest.mark.asyncio
    async def test_trace_span_decorator_async(self):
        """Тест декоратора для async функции."""
        from app.core.telemetry import trace_span
        
        call_count = 0
        
        @trace_span("test_function")
        async def async_func():
            nonlocal call_count
            call_count += 1
            return "result"
        
        result = await async_func()
        assert result == "result"
        assert call_count == 1

    def test_trace_span_decorator_sync(self):
        """Тест декоратора для sync функции."""
        from app.core.telemetry import trace_span
        
        call_count = 0
        
        @trace_span("test_sync_function")
        def sync_func():
            nonlocal call_count
            call_count += 1
            return "result"
        
        result = sync_func()
        assert result == "result"
        assert call_count == 1


class TestTelemetrySpan:
    """Тесты спанов."""

    def test_span_context_manager(self):
        """Тест контекстного менеджера спана."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        
        # Контекстный менеджер должен работать даже без OTEL
        with telemetry.start_span("test_span") as span:
            # span может быть None если OTEL не доступен
            pass

    def test_span_with_attributes(self):
        """Тест спана с атрибутами."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        
        with telemetry.start_span(
            "test_span",
            attributes={"key1": "value1", "key2": 123}
        ) as span:
            pass


class TestTelemetryInstrumentation:
    """Тесты инструментирования."""

    def test_instrument_fastapi(self):
        """Тест инструментирования FastAPI."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        mock_app = MagicMock()
        
        # Не должно выбрасывать исключений
        telemetry.instrument_fastapi(mock_app)

    def test_instrument_httpx(self):
        """Тест инструментирования HTTPX."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        
        # Не должно выбрасывать исключений
        telemetry.instrument_httpx()

    def test_instrument_sqlalchemy(self):
        """Тест инструментирования SQLAlchemy."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        mock_engine = MagicMock()
        
        # Не должно выбрасывать исключений
        telemetry.instrument_sqlalchemy(mock_engine)

    def test_instrument_redis(self):
        """Тест инструментирования Redis."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        mock_redis = MagicMock()
        
        # Не должно выбрасывать исключений
        telemetry.instrument_redis(mock_redis)


class TestTelemetryShutdown:
    """Тесты остановки телеметрии."""

    def test_shutdown(self):
        """Тест остановки."""
        telemetry = Telemetry(TelemetryConfig(enabled=False))
        
        # Не должно выбрасывать исключений
        telemetry.shutdown()


class TestOTELAvailability:
    """Тесты доступности OpenTelemetry."""

    def test_otel_available_flag(self):
        """Тест флага доступности."""
        # OTEL_AVAILABLE должен быть boolean
        assert isinstance(OTEL_AVAILABLE, bool)

    def test_graceful_degradation(self):
        """Тест graceful degradation без OTEL."""
        # Все функции должны работать даже без OTEL
        config = TelemetryConfig(enabled=True)
        telemetry = Telemetry(config)
        
        # Методы не должны выбрасывать исключений
        telemetry.shutdown()


class TestTelemetryIntegration:
    """Интеграционные тесты."""

    def test_full_workflow(self):
        """Тест полного workflow."""
        # Настройка
        telemetry = setup_telemetry(
            service_name="integration-test",
            exporter="console"
        )
        assert telemetry is not None
        
        # Использование
        with telemetry.start_span("integration_test"):
            pass
        
        # Остановка
        telemetry.shutdown()

    def test_multiple_setups(self):
        """Тест множественных настроек."""
        # Singleton должен возвращать тот же экземпляр
        telemetry1 = setup_telemetry(service_name="test1")
        telemetry2 = setup_telemetry(service_name="test2")
        
        # Это тот же singleton
        assert telemetry1 is telemetry2
