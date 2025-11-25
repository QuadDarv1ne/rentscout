from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    APP_NAME: str = "RentScout"
    REDIS_URL: str = "redis://redis:6379/0"
    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"
    PROXY_ENABLED: bool = False
    CIAN_MAX_RETRIES: int = 3
    AVITO_RATE_LIMIT: int = 5
    RATE_LIMIT_WINDOW: int = 60


settings = Settings()
