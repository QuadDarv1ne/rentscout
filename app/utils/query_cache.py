"""
Query Cache для кэширования SQL запросов.

LRU-кеш для часто выполняемых запросов к базе данных.
Снижает нагрузку на PostgreSQL и ускоряет ответы API.
"""

import asyncio
import hashlib
import time
import json
from typing import Optional, Any, Dict, List, Callable, Awaitable, TypeVar, Union
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta
import logging

from app.utils.logger import logger

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Элемент кэша."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    query_hash: str = ""
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Проверить истёк ли срок жизни."""
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Обновить время доступа."""
        self.last_accessed = time.time()
        self.hits += 1


@dataclass
class CacheStats:
    """Статистика кэша."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entries_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Коэффициент попаданий."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QueryCache:
    """
    LRU Query Cache для SQL запросов.

    Особенности:
    - LRU eviction при достижении лимита
    - TTL для каждого элемента
    - Автоматическая очистка просроченных
    - Статистика использования
    - Поддержка async

    Пример использования:
        cache = QueryCache(max_size=1000, default_ttl=300)

        @cache.cached(ttl=60)
        async def get_properties(city: str):
            return await db.execute(...)
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,  # 5 минут
        max_memory_mb: int = 100,
        cleanup_interval: int = 60  # секунды
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"QueryCache initialized: max_size={max_size}, "
            f"ttl={default_ttl}s, max_memory={max_memory_mb}MB"
        )

    async def start(self) -> None:
        """Запустить фоновую очистку."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("QueryCache cleanup task started")

    async def stop(self) -> None:
        """Остановить фоновую очистку."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("QueryCache stopped")

    async def _cleanup_loop(self) -> None:
        """Фоновый цикл очистки просроченных записей."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"QueryCache cleanup error: {e}")

    async def _cleanup_expired(self) -> int:
        """
        Очистить просроченные записи.

        Returns:
            Количество удалённых записей
        """
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                self._remove_key(key)
                self._stats.evictions += 1

            if expired_keys:
                logger.debug(f"QueryCache: cleaned {len(expired_keys)} expired entries")

            return len(expired_keys)

    def _generate_key(self, query: str, params: Optional[Dict] = None) -> str:
        """
        Сгенерировать уникальный ключ для запроса.

        Args:
            query: SQL запрос
            params: Параметры запроса

        Returns:
            MD5 хеш запроса
        """
        key_data = f"{query}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _estimate_size(self, value: Any) -> int:
        """Оценить размер значения в байтах."""
        try:
            return len(json.dumps(value).encode())
        except (TypeError, ValueError):
            return 1024  # Оценка по умолчанию

    async def get(
        self,
        key: str,
        default: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Получить значение из кэша.

        Args:
            key: Ключ
            default: Значение по умолчанию

        Returns:
            Значение или None
        """
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                logger.debug(f"QueryCache miss: {key}")
                return default

            entry = self._cache[key]

            # Проверка на истечение
            if entry.is_expired():
                self._remove_key(key)
                self._stats.evictions += 1
                self._stats.misses += 1
                logger.debug(f"QueryCache expired: {key}")
                return default

            # LRU: переместить в конец (свежий)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats.hits += 1

            logger.debug(f"QueryCache hit: {key} (hits={entry.hits})")
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Сохранить значение в кэш.

        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни (секунды)
        """
        ttl = ttl if ttl is not None else self.default_ttl
        now = time.time()
        size_bytes = self._estimate_size(value)

        async with self._lock:
            # Если ключ существует - обновляем
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.total_size_bytes -= old_entry.size_bytes
                self._cache.move_to_end(key)

            else:
                # Проверка лимита размера
                while (
                    len(self._cache) >= self.max_size or
                    self._stats.total_size_bytes + size_bytes > self.max_memory_bytes
                ):
                    self._evict_lru()

            # Создаём запись
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl,
                query_hash=key,
                size_bytes=size_bytes
            )

            self._cache[key] = entry
            self._stats.total_size_bytes += size_bytes
            self._stats.entries_count = len(self._cache)
            self._stats.sets += 1

            logger.debug(
                f"QueryCache set: {key} (ttl={ttl}s, size={size_bytes}B)"
            )

    async def delete(self, key: str) -> bool:
        """
        Удалить значение из кэша.

        Args:
            key: Ключ

        Returns:
            True если удалено
        """
        async with self._lock:
            if key in self._cache:
                self._remove_key(key)
                self._stats.deletes += 1
                logger.debug(f"QueryCache delete: {key}")
                return True
            return False

    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()
            self._stats.total_size_bytes = 0
            self._stats.entries_count = 0
            logger.info("QueryCache cleared")

    def _remove_key(self, key: str) -> None:
        """Удалить ключ (без блокировки)."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.entries_count = len(self._cache)

    def _evict_lru(self) -> None:
        """Вытеснить наименее используемую запись (LRU)."""
        if self._cache:
            # Первый элемент - самый старый (LRU)
            oldest_key = next(iter(self._cache))
            self._remove_key(oldest_key)
            self._stats.evictions += 1
            logger.debug(f"QueryCache LRU eviction: {oldest_key}")

    def cached(
        self,
        ttl: Optional[int] = None,
        key_prefix: str = ""
    ) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
        """
        Декоратор для кэширования результатов функции.

        Args:
            ttl: Время жизни кэша
            key_prefix: Префикс для ключа

        Пример:
            @query_cache.cached(ttl=60, key_prefix="properties")
            async def get_properties(city: str):
                return await db.query(...)
        """
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            async def wrapper(*args, **kwargs) -> T:
                # Генерируем ключ из аргументов
                args_key = ":".join(str(a) for a in args)
                kwargs_key = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{func.__name__}:{args_key}:{kwargs_key}"

                # Пробуем получить из кэша
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value  # type: ignore

                # Выполняем функцию
                result = await func(*args, **kwargs)

                # Сохраняем в кэш
                await self.set(cache_key, result, ttl=ttl)

                return result

            return wrapper

        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша."""
        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "evictions": self._stats.evictions,
            "hit_rate": f"{self._stats.hit_rate * 100:.2f}%",
            "entries_count": self._stats.entries_count,
            "total_size_bytes": self._stats.total_size_bytes,
            "total_size_mb": f"{self._stats.total_size_bytes / 1024 / 1024:.2f}",
            "max_size": self.max_size,
            "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
        }

    async def get_entry(self, key: str) -> Optional[CacheEntry]:
        """Получить информацию о записи."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return entry
            return None

    async def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Получить список ключей.

        Args:
            pattern: Опциональный паттерн (startswith)

        Returns:
            Список ключей
        """
        async with self._lock:
            keys = list(self._cache.keys())
            if pattern:
                keys = [k for k in keys if k.startswith(pattern)]
            return keys


# ============================================================================
# Глобальный экземпляр
# ============================================================================

query_cache = QueryCache(
    max_size=5000,
    default_ttl=300,
    max_memory_mb=50,
    cleanup_interval=60
)


# ============================================================================
# Интеграция с SQLAlchemy
# ============================================================================

class CachedQueryExecutor:
    """
    Обёртка для выполнения SQL запросов с кэшированием.

    Пример:
        executor = CachedQueryExecutor(db_session, query_cache)

        results = await executor.execute(
            "SELECT * FROM properties WHERE city = :city",
            {"city": "Москва"},
            ttl=60
        )
    """

    def __init__(self, db_session, cache: QueryCache):
        self.db = db_session
        self.cache = cache

    async def execute(
        self,
        query: str,
        params: Optional[Dict] = None,
        ttl: Optional[int] = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Выполнить SQL запрос с кэшированием.

        Args:
            query: SQL запрос
            params: Параметры
            ttl: Время жизни кэша
            use_cache: Использовать кэш

        Returns:
            Результаты запроса
        """
        if not use_cache:
            return await self._execute_query(query, params)

        # Генерируем ключ
        cache_key = f"sql:{self.cache._generate_key(query, params)}"

        # Пробуем кэш
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Выполняем запрос
        results = await self._execute_query(query, params)

        # Кэшируем
        await self.cache.set(cache_key, results, ttl=ttl)

        return results

    async def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Выполнить SQL запрос."""
        from sqlalchemy import text

        async with self.db.begin() as conn:
            result = await conn.execute(text(query), params or {})
            return [dict(row) for row in result]


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    "QueryCache",
    "CacheEntry",
    "CacheStats",
    "CachedQueryExecutor",
    "query_cache",
]
