"""
Интеграция Sentry для мониторинга ошибок и производительности.

Sentry предоставляет:
- Отслеживание ошибок в реальном времени
- Трассировка производительности
- Мониторинг release health
- Оповещения о критических ошибках
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

from app.core.config import settings
from app.utils.logger import logger


def init_sentry() -> bool:
    """
    Инициализирует Sentry мониторинг.

    Returns:
        True если Sentry успешно инициализирован, False иначе
    """
    # Проверяем наличие SENTRY_DSN в конфигурации
    sentry_dsn = getattr(settings, "SENTRY_DSN", None)

    if not sentry_dsn:
        logger.info("Sentry не настроен: SENTRY_DSN отсутствует в конфигурации")
        return False

    if not sentry_dsn.startswith("https://"):
        logger.warning(
            f"Невалидный SENTRY_DSN: {sentry_dsn[:20]}... "
            "Ожидается формат https://<key>@sentry.io/<project_id>"
        )
        return False

    try:
        # Определяем окружение
        environment = "production"
        if settings.DEBUG:
            environment = "development"
        elif settings.TESTING:
            environment = "testing"

        # Настраиваем Sentry
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint",  # Группировка по endpoint'ам
                ),
                LoggingIntegration(
                    level=logging.INFO,  # Отправлять info и выше
                    event_level=logging.ERROR,  # Ошибки как события
                ),
                RedisIntegration(),
                SqlalchemyIntegration(),
                CeleryIntegration(),
            ],
            # Трассировка производительности
            traces_sample_rate=0.1 if environment == "production" else 1.0,
            # Профилирование (опционально)
            profiles_sample_rate=0.1 if environment == "production" else 1.0,
            # Окружение
            environment=environment,
            # Release (версия приложения)
            release=f"rentscout@{settings.APP_NAME or 'unknown'}",
            # Теги для всех событий
            default_tags={
                "service": "rentscout-api",
                "environment": environment,
            },
            # Настройка отправки данных
            send_default_pii=False,  # Не отправлять персональные данные
            # Фильтрация чувствительных данных
            before_send=before_send_processor,
            # Обработка транзакций
            before_send_transaction=before_transaction_processor,
        )

        logger.info(
            f"Sentry успешно инициализирован (environment={environment})"
        )
        return True

    except Exception as e:
        logger.error(f"Ошибка инициализации Sentry: {e}")
        return False


def before_send_processor(event: dict, hint: dict) -> dict | None:
    """
    Обработчик событий перед отправкой в Sentry.

    Фильтрует чувствительные данные и игнорируемые ошибки.

    Args:
        event: Событие Sentry
        hint: Дополнительная информация

    Returns:
        Обработанное событие или None для игнорирования
    """
    # Игнорируем определённые типы ошибок
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]

        # Игнорируемые ошибки (не критичные)
        ignored_exceptions = [
            "ValidationError",  # Ошибки валидации Pydantic
            "HTTPException",  # Ошибки FastAPI 4xx
        ]

        if exc_type.__name__ in ignored_exceptions:
            # Не отправлять в Sentry
            return None

        # Игнорируем 4xx ошибки
        if hasattr(exc_value, "status_code"):
            if 400 <= exc_value.status_code < 500:
                return None

    # Фильтрация чувствительных данных в контексте
    if "extra" in event:
        extra = event["extra"]

        # Удаляем пароли и токены
        sensitive_keys = [
            "password",
            "secret",
            "token",
            "api_key",
            "authorization",
            "credit_card",
        ]

        for key in sensitive_keys:
            if key in extra:
                extra[key] = "***REDACTED***"

    # Фильтрация данных пользователя
    if "user" in event:
        user_data = event.get("user", {})
        # Оставляем только ID, удаляем email и username
        if "email" in user_data:
            user_data["email"] = "***REDACTED***"
        if "username" in user_data:
            user_data["username"] = "***REDACTED***"

    return event


def before_transaction_processor(event: dict, hint: dict) -> dict | None:
    """
    Обработчик транзакций перед отправкой в Sentry.

    Args:
        event: Событие транзакции
        hint: Дополнительная информация

    Returns:
        Обработанное событие или None
    """
    # Фильтрация чувствительных данных в транзакциях
    if "request" in event:
        request_data = event["request"]

        # Удаляем заголовки авторизации
        if "headers" in request_data:
            headers = request_data["headers"]
            if "Authorization" in headers:
                headers["Authorization"] = "***REDACTED***"
            if "Cookie" in headers:
                headers["Cookie"] = "***REDACTED***"

    return event


def set_user_context(user_id: int = None, username: str = None) -> None:
    """
    Устанавливает контекст пользователя для текущей сессии.

    Args:
        user_id: ID пользователя
        username: Имя пользователя
    """
    sentry_sdk.set_user({
        "id": user_id,
        "username": username,
    })


def set_tag(key: str, value: str) -> None:
    """
    Добавляет тег к текущей сессии.

    Args:
        key: Ключ тега
        value: Значение тега
    """
    sentry_sdk.set_tag(key, value)


def set_context(name: str, data: dict) -> None:
    """
    Добавляет контекст к текущей сессии.

    Args:
        name: Название контекста
        data: Данные контекста
    """
    sentry_sdk.set_context(name, data)


def capture_exception(exception: Exception, context: dict = None) -> str | None:
    """
    Отправляет исключение в Sentry.

    Args:
        exception: Исключение для отправки
        context: Дополнительный контекст

    Returns:
        ID события или None если Sentry не настроен
    """
    if context:
        set_context("custom", context)

    event_id = sentry_sdk.capture_exception(exception)
    logger.debug(f"Исключение отправлено в Sentry: {event_id}")
    return event_id


def capture_message(message: str, level: str = "info", context: dict = None) -> str | None:
    """
    Отправляет сообщение в Sentry.

    Args:
        message: Текст сообщения
        level: Уровень (debug, info, warning, error)
        context: Дополнительный контекст

    Returns:
        ID события или None если Sentry не настроен
    """
    if context:
        set_context("custom", context)

    event_id = sentry_sdk.capture_message(message, level=level)
    logger.debug(f"Сообщение отправлено в Sentry: {event_id}")
    return event_id


def start_transaction(name: str, op: str = "function") -> sentry_sdk.Transaction:
    """
    Начинает транзакцию для трассировки производительности.

    Args:
        name: Название транзакции
        op: Операция (function, db.query, http.request, etc.)

    Returns:
        Объект транзакции
    """
    return sentry_sdk.start_transaction(name=name, op=op)


# Импорт logging для использования в LoggingIntegration
import logging

# Инициализация при загрузке модуля (опционально)
# Вызовите init_sentry() в main.py при старте приложения
