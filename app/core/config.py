from pydantic import ConfigDict, Field, field_validator, HttpUrl
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Конфигурация приложения с валидацией переменных окружения."""
    
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application settings
    APP_NAME: str = Field(default="RentScout", description="Название приложения")
    DEBUG: bool = Field(default=False, description="Режим отладки")
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    
    # Network settings
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
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
    
    # Testing flag
    TESTING: bool = Field(default=False, description="Режим тестирования")
    
    # Parser settings
    PROXY_ENABLED: bool = Field(default=False, description="Включить использование proxy")
    CIAN_MAX_RETRIES: int = Field(default=3, ge=1, le=10, description="Макс повторы для Cian")
    AVITO_RATE_LIMIT: int = Field(default=5, ge=1, le=100, description="Rate limit для Avito")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1, le=3600, description="Окно rate limit в секундах")
    
    # Timeout settings
    REQUEST_TIMEOUT: int = Field(default=30, ge=5, le=300, description="Timeout для HTTP запросов")
    PARSER_TIMEOUT: int = Field(default=60, ge=10, le=600, description="Timeout для парсеров")
    
    # Retry settings
    MAX_RETRIES: int = Field(default=3, ge=1, le=10, description="Макс повторы запросов")
    RETRY_DELAY: float = Field(default=1.0, ge=0.1, le=60.0, description="Базовая задержка retry")
    
    # Cache settings
    CACHE_TTL: int = Field(default=300, ge=0, le=86400, description="TTL кэша в секундах")
    
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


settings = Settings()

