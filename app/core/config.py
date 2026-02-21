import re
import warnings
from pydantic import ConfigDict, Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Конфигурация приложения с валидацией переменных окружения."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application settings
    APP_NAME: str = Field(default="RentScout", description="Название приложения")
    DEBUG: bool = Field(default=False, description="Режим отладки")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Security settings
    SECRET_KEY: str = Field(
        default="",
        description="Секретный ключ для подписи токенов и сессий"
    )
    JWT_SECRET: str = Field(
        default="",
        description="Секретный ключ для JWT токенов"
    )

    # Network settings
    REDIS_URL: str = Field(
        default="redis://:redis_password@redis:6379/0",
        description="URL для подключения к Redis"
    )
    ELASTICSEARCH_URL: str = Field(
        default="http://elasticsearch:9200",
        description="URL для подключения к Elasticsearch"
    )
    ELASTICSEARCH_HOST: str = Field(
        default="localhost",
        description="Хост Elasticsearch"
    )
    ELASTICSEARCH_PORT: int = Field(
        default=9200,
        description="Порт Elasticsearch"
    )
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rentscout",
        description="URL для подключения к PostgreSQL"
    )
    
    # Connection Pool settings
    DB_POOL_SIZE: int = Field(default=20, ge=5, le=100, description="Размер пула соединений БД")
    DB_MAX_OVERFLOW: int = Field(default=30, ge=10, le=100, description="Дополнительные соединения БД")
    DB_POOL_TIMEOUT: int = Field(default=30, ge=5, le=120, description="Timeout получения соединения БД")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, ge=10, le=200, description="Максимум соединений Redis")
    HTTP_MAX_CONNECTIONS: int = Field(default=100, ge=20, le=500, description="Максимум HTTP соединений")
    
    # Testing flag
    TESTING: bool = Field(default=False, description="Режим тестирования")
    
    # Parser settings
    PROXY_ENABLED: bool = Field(default=False, description="Включить использование proxy")
    PROXY_FILE: str = Field(default="proxies.txt", description="Файл со списком прокси")
    USE_RANDOM_HEADERS: bool = Field(default=True, description="Использовать случайные заголовки")
    MIN_REQUEST_DELAY: float = Field(default=2.0, ge=0, le=60, description="Минимальная задержка между запросами (сек)")
    MAX_REQUEST_DELAY: float = Field(default=5.0, ge=0, le=60, description="Максимальная задержка между запросами (сек)")
    CIAN_MAX_RETRIES: int = Field(default=3, ge=1, le=10, description="Макс повторы для Cian")
    AVITO_RATE_LIMIT: int = Field(default=5, ge=1, le=100, description="Rate limit для Avito")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1, le=3600, description="Окно rate limit в секундах")
    
    # Timeout settings
    REQUEST_TIMEOUT: int = Field(default=30, ge=5, le=300, description="Timeout для HTTP запросов")
    PARSER_TIMEOUT: int = Field(default=60, ge=10, le=600, description="Timeout для парсеров")
    SEARCH_TIMEOUT: int = Field(default=120, ge=30, le=600, description="Общий timeout для поиска")
    
    # Retry settings
    MAX_RETRIES: int = Field(default=3, ge=1, le=10, description="Макс повторы запросов")
    RETRY_DELAY: float = Field(default=1.0, ge=0.1, le=60.0, description="Базовая задержка retry")
    
    # Cache settings
    CACHE_TTL: int = Field(default=300, ge=0, le=86400, description="TTL кэша в секундах")
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Валидация URL PostgreSQL."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL должен начинаться с postgresql:// или postgresql+asyncpg://")
        return v
    
    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Валидация URL Redis."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL должен начинаться с redis:// или rediss://")
        return v
    
    @field_validator("ELASTICSEARCH_URL")
    @classmethod
    def validate_es_url(cls, v: str) -> str:
        """Валидация URL Elasticsearch."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("ELASTICSEARCH_URL должен начинаться с http:// или https://")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Валидация уровня логирования."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL должен быть одним из: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        """
        Валидация секретного ключа.
        
        Проверяет:
        - Длина не менее 32 символов
        - Не является дефолтным значением
        """
        if not v or len(v) < 32:
            warnings.warn(
                "SECRET_KEY слишком короткий или отсутствует! "
                "Используйте 'python scripts/generate_secrets.py' для генерации безопасного ключа. "
                "В production это критическая уязвимость.",
                UserWarning,
                stacklevel=2
            )
        # Проверка на дефолтные значения
        weak_keys = [
            "your_very_long_random_secret_key_change_this",
            "change_this",
            "secret",
            "secret_key",
            "changeme",
        ]
        if v.lower() in weak_keys:
            raise ValueError(
                f"SECRET_KEY не должен быть дефолтным значением! "
                f"Текущее значение '{v[:20]}...' небезопасно."
            )
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str, info: ValidationInfo) -> str:
        """
        Валидация JWT секрета.
        
        Проверяет:
        - Длина не менее 32 символов
        - Не является дефолтным значением
        """
        if not v or len(v) < 32:
            warnings.warn(
                "JWT_SECRET слишком короткий или отсутствует! "
                "Используйте 'python scripts/generate_secrets.py' для генерации безопасного ключа.",
                UserWarning,
                stacklevel=2
            )
        weak_secrets = [
            "another_secret_key_for_jwt",
            "jwt_secret",
            "jwt",
            "changeme",
        ]
        if v.lower() in weak_secrets:
            raise ValueError(
                f"JWT_SECRET не должен быть дефолтным значением! "
                f"Текущее значение '{v[:20]}...' небезопасно."
            )
        return v

    def validate_password_in_url(self, url: str, url_name: str) -> None:
        """
        Проверяет сложность пароля в URL подключения.
        
        Args:
            url: URL для проверки (postgresql://user:password@host:port/db)
            url_name: Название URL для сообщения об ошибке
        """
        # Извлекаем пароль из URL
        # Формат: scheme://user:password@host:port/db
        try:
            # Для PostgreSQL
            if "://" in url:
                auth_part = url.split("://")[1].split("@")[0]
                if ":" in auth_part:
                    password = auth_part.split(":")[-1]
                    self._check_password_strength(password, url_name)
        except (IndexError, AttributeError):
            pass  # Не удалось извлечь пароль, пропускаем проверку

    def _check_password_strength(self, password: str, field_name: str) -> None:
        """
        Проверяет сложность пароля.
        
        Args:
            password: Пароль для проверки
            field_name: Название поля для сообщения
        """
        if len(password) < 16:
            warnings.warn(
                f"Пароль в {field_name} слишком короткий ({len(password)} символов). "
                "Рекомендуется минимум 16 символов. "
                "Используйте 'python scripts/generate_secrets.py' для генерации.",
                UserWarning,
                stacklevel=2
            )
        
        # Проверка на слабые пароли
        weak_passwords = [
            "password", "postgres", "redis_password", "admin", "root",
            "your_password", "your_secure_password", "changeme",
        ]
        if password.lower() in weak_passwords:
            raise ValueError(
                f"Пароль в {field_name} является дефолтным или слишком слабым! "
                f"Используйте 'python scripts/generate_secrets.py' для генерации безопасного пароля."
            )

    def model_post_init(self, __context) -> None:
        """
        Пост-обработка после инициализации модели.
        Проверяет безопасность паролей и секретов.
        """
        # Проверяем пароли в URL
        self.validate_password_in_url(self.DATABASE_URL, "DATABASE_URL")
        self.validate_password_in_url(self.REDIS_URL, "REDIS_URL")


# Глобальный экземпляр настроек
settings = Settings()

