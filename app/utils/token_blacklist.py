"""
JWT Token Blacklist для Redis.

Реализует механизм отзыва токенов:
- Добавление токенов в blacklist при logout
- Проверка токенов на наличие в blacklist
- Автоматическая очистка expired токенов
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """
    Менеджер blacklist для JWT токенов.
    
    Использует Redis для хранения отозванных токенов с TTL.
    """
    
    def __init__(self):
        self.redis_client = None
        self.prefix = "token_blacklist"
    
    async def connect(self, redis_client):
        """Инициализация Redis клиента."""
        self.redis_client = redis_client
        logger.info("TokenBlacklist connected to Redis")
    
    async def add_token(
        self,
        token: str,
        expires_at: datetime,
        token_type: str = "access"
    ) -> bool:
        """
        Добавить токен в blacklist.
        
        Args:
            token: JWT токен для добавления в blacklist
            expires_at: Время истечения токена (для установки TTL)
            token_type: Тип токена (access/refresh)
            
        Returns:
            True если успешно добавлен
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized, skipping blacklist")
            return False
        
        try:
            # Используем хеш токена как ключ для экономии памяти
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"{self.prefix}:{token_type}:{token_hash}"
            
            # Вычисляем TTL в секундах
            now = datetime.now(timezone.utc)
            ttl = int((expires_at - now).total_seconds())
            
            if ttl <= 0:
                # Токен уже истёк, нет смысла добавлять
                return False
            
            # Добавляем в Redis с TTL
            # Максимальный TTL - 7 дней (для refresh токенов)
            ttl = min(ttl, 7 * 24 * 60 * 60)
            
            await self.redis_client.setex(key, ttl, "1")
            
            logger.debug(f"Added token to blacklist: {token_type} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error adding token to blacklist: {e}")
            return False
    
    async def is_blacklisted(self, token: str, token_type: str = "access") -> bool:
        """
        Проверить, находится ли токен в blacklist.
        
        Args:
            token: JWT токен для проверки
            token_type: Тип токена (access/refresh)
            
        Returns:
            True если токен в blacklist
        """
        if not self.redis_client:
            # Если Redis недоступен, считаем что токен не в blacklist
            # В production можно настроить строгий режим
            return False
        
        try:
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"{self.prefix}:{token_type}:{token_hash}"
            
            result = await self.redis_client.get(key)
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            # В случае ошибки считаем токен валидным (fail-open)
            # В production можно изменить на fail-close
            return False
    
    async def remove_token(self, token: str, token_type: str = "access") -> bool:
        """
        Удалить токен из blacklist (если нужно восстановить).
        
        Args:
            token: JWT токен для удаления
            token_type: Тип токена
            
        Returns:
            True если успешно удалён
        """
        if not self.redis_client:
            return False
        
        try:
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"{self.prefix}:{token_type}:{token_hash}"
            
            result = await self.redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error removing token from blacklist: {e}")
            return False
    
    async def blacklist_refresh_tokens(
        self,
        access_token: str,
        refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime
    ) -> bool:
        """
        Добавить оба токена в blacklist.
        
        Args:
            access_token: Access токен
            refresh_token: Refresh токен
            access_expires_at: Время истечения access токена
            refresh_expires_at: Время истечения refresh токена
            
        Returns:
            True если оба токена успешно добавлены
        """
        access_result = await self.add_token(
            access_token, access_expires_at, "access"
        )
        refresh_result = await self.add_token(
            refresh_token, refresh_expires_at, "refresh"
        )
        
        return access_result and refresh_result
    
    async def get_stats(self) -> dict:
        """
        Получить статистику blacklist.
        
        Returns:
            Dict со статистикой
        """
        if not self.redis_client:
            return {
                "total_blacklisted": 0,
                "redis_connected": False
            }
        
        try:
            # Считаем количество ключей blacklist
            pattern = f"{self.prefix}:*"
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            return {
                "total_blacklisted": len(keys),
                "redis_connected": True
            }
            
        except Exception as e:
            logger.error(f"Error getting blacklist stats: {e}")
            return {
                "total_blacklisted": 0,
                "redis_connected": True,
                "error": str(e)
            }


# Глобальный экземпляр
token_blacklist = TokenBlacklist()


async def get_token_blacklist() -> TokenBlacklist:
    """Dependency для получения token blacklist."""
    return token_blacklist
