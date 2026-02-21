"""
JSON логирование для структурированного вывода логов.

Использует structlog для создания структурированных JSON логов,
которые легко парсятся системами мониторинга (ELK, Loki, Splunk).

Особенности:
- JSON формат для production
- Цветной вывод для development
- Correlation ID для трассировки запросов
- Интеграция с Sentry
"""

import logging
import sys
from typing import Any, Dict
from pathlib import Path

import structlog
from structlog.types import Processor


# =============================================================================
# Configuration
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FILE = "logs/app.log"
LOG_FORMAT = "json"  # "json" или "console"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5


# =============================================================================
# Processors
# =============================================================================

def add_app_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Добавляет контекст приложения к каждому лог-сообщению."""
    event_dict["app"] = "rentscout"
    event_dict["service"] = "api"
    return event_dict


def add_severity_label(
    logger: logging.Logger,
    method_name: str,
    event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Добавляет human-readable уровень лога."""
    level = event_dict.get("level", "INFO")
    event_dict["severity_label"] = level.upper()
    return event_dict


# =============================================================================
# Setup Functions
# =============================================================================

def setup_json_logging(
    log_level: str = LOG_LEVEL,
    log_file: str = LOG_FILE,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT,
) -> None:
    """
    Настраивает JSON логирование для production.
    
    Args:
        log_level: Уровень логирования
        log_file: Путь к файлу логов
        max_bytes: Максимальный размер файла
        backup_count: Количество резервных файлов
    """
    # Создаём директорию для логов
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Настройка logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[
            # Console handler (JSON)
            logging.StreamHandler(sys.stdout),
            # File handler (JSON)
            logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            ),
        ],
    )

    # Настройка structlog
    structlog.configure(
        processors=[
            # Добавляем контекст
            add_app_context,
            
            # Добавляем метку уровня
            add_severity_label,
            
            # Стандартные процессоры structlog
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            
            # JSON форматирование
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_console_logging(
    log_level: str = LOG_LEVEL,
) -> None:
    """
    Настраивает цветной консольный вывод для development.
    
    Args:
        log_level: Уровень логирования
    """
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Настройка structlog для console
    structlog.configure(
        processors=[
            add_app_context,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


# =============================================================================
# Logger Factory
# =============================================================================

def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Создаёт структурированный логгер.
    
    Args:
        name: Название логгера
        
    Returns:
        structlog BoundLogger
    """
    return structlog.get_logger(name)


# =============================================================================
# Alert Functions
# =============================================================================

async def send_telegram_alert(
    message: str,
    chat_id: str = None,
    bot_token: str = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Отправляет алерт в Telegram.
    
    Args:
        message: Текст сообщения
        chat_id: ID чата для отправки
        bot_token: Токен бота
        parse_mode: Режим парсинга (HTML или Markdown)
        
    Returns:
        True если успешно отправлено
    """
    import httpx
    
    if not chat_id or not bot_token:
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
        
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Telegram alert failed: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Telegram alert error: {e}")
        return False


async def send_slack_alert(
    message: str,
    webhook_url: str = None,
    channel: str = None,
    username: str = "RentScout Bot",
) -> bool:
    """
    Отправляет алерт в Slack.
    
    Args:
        message: Текст сообщения
        webhook_url: URL вебхука Slack
        channel: Канал для отправки
        username: Имя отправителя
        
    Returns:
        True если успешно отправлено
    """
    import httpx
    
    if not webhook_url:
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json={
                    "text": message,
                    "channel": channel,
                    "username": username,
                    "icon_emoji": ":warning:",
                },
                timeout=10,
            )
        
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Slack alert failed: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Slack alert error: {e}")
        return False


async def send_alert(
    message: str,
    level: str = "error",
    service: str = "rentscout-api",
) -> None:
    """
    Отправляет алерт во все настроенные каналы.
    
    Args:
        message: Текст сообщения
        level: Уровень алерта (info, warning, error, critical)
        service: Название сервиса
    """
    from app.core.config import settings
    
    # Форматируем сообщение
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }.get(level, "📢")
    
    formatted_message = f"""
{emoji} <b>{level.upper()}</b> - {service}

{message}

<i>Time: {logging.getLogger().handlers[0].formatter.formatTime(logging.LogRecord('', 0, '', 0, '', (), None))}</i>
"""
    
    # Отправляем в Telegram
    telegram_chat_id = getattr(settings, "TELEGRAM_ALERT_CHAT_ID", None)
    telegram_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    
    if telegram_chat_id and telegram_token:
        await send_telegram_alert(
            formatted_message,
            chat_id=telegram_chat_id,
            bot_token=telegram_token,
        )
    
    # Отправляем в Slack
    slack_webhook = getattr(settings, "SLACK_WEBHOOK_URL", None)
    
    if slack_webhook:
        await send_slack_alert(
            f"{emoji} *{level.upper()}* - {service}\n\n{message}",
            webhook_url=slack_webhook,
        )


# =============================================================================
# Alert Handler для логирования
# =============================================================================

class AlertHandler(logging.Handler):
    """
    Handler для отправки алертов при критических ошибках.
    """
    
    def __init__(
        self,
        level: int = logging.CRITICAL,
        enabled: bool = True,
    ):
        super().__init__(level)
        self.enabled = enabled
    
    def emit(self, record: logging.LogRecord) -> None:
        if not self.enabled:
            return
        
        try:
            # Получаем сообщение
            message = self.format(record)
            
            # Отправляем алерт асинхронно
            import asyncio
            
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    send_alert(
                        message,
                        level="critical" if record.levelno >= logging.CRITICAL else "error",
                    )
                )
            else:
                asyncio.run(
                    send_alert(
                        message,
                        level="critical" if record.levelno >= logging.CRITICAL else "error",
                    )
                )
                
        except Exception:
            self.handleError(record)


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "setup_json_logging",
    "setup_console_logging",
    "get_logger",
    "send_telegram_alert",
    "send_slack_alert",
    "send_alert",
    "AlertHandler",
]
