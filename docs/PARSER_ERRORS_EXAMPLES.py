"""
Пример интеграции системы обработки ошибок в парсеры.

Этот файл показывает как использовать app.utils.parser_errors в реальных парсерах.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

# Импортируем нашу систему обработки ошибок
from app.utils.parser_errors import (
    AuthenticationError,
    ErrorClassifier,
    ErrorRetryability,
    ErrorSeverity,
    NetworkError,
    ParsingError,
    ParserErrorHandler,
    RateLimitError,
    SourceUnavailableError,
    TimeoutError as ParserTimeoutError,
    ValidationError,
)
from app.utils.retry import retry

logger = logging.getLogger(__name__)


# ============================================================================
# Пример 1: Простой парсер с обработкой ошибок
# ============================================================================


class SimplePropertyParser:
    """Простой парсер квартир с базовой обработкой ошибок."""

    async def parse(self, url: str) -> Dict[str, Any]:
        """
        Парсит страницу квартиры и возвращает данные.

        Args:
            url: URL страницы квартиры

        Returns:
            Словарь с данными квартиры

        Raises:
            NetworkError: При проблемах с сетью
            ParsingError: При ошибке парсинга
            ValidationError: При невалидных данных
        """
        try:
            # Шаг 1: Получение HTML
            html = await self._fetch_html(url)

            # Шаг 2: Парсинг данных
            data = self._parse_html(html)

            # Шаг 3: Валидация
            self._validate_data(data)

            return data

        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            parser_error = ParserTimeoutError(f"Timeout while parsing {url}: {e}")
            ParserErrorHandler.log_error(parser_error, context="SimplePropertyParser.parse")
            raise parser_error

        except Exception as e:
            # Преобразуем в подходящее исключение
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="SimplePropertyParser.parse")
            raise parser_error

    async def _fetch_html(self, url: str) -> str:
        """Получает HTML страницы."""
        # Имитация фетчинга
        await asyncio.sleep(0.1)
        return "<html>sample</html>"

    def _parse_html(self, html: str) -> Dict[str, Any]:
        """Парсит HTML и извлекает данные."""
        if not html or "<html>" not in html.lower():
            raise ParsingError("Invalid HTML structure")

        return {
            "url": "https://example.com/property/123",
            "price": 5000000,
            "rooms": 3,
        }

    def _validate_data(self, data: Dict[str, Any]) -> None:
        """Валидирует полученные данные."""
        if data.get("price", 0) <= 0:
            raise ValidationError(f"Invalid price: {data.get('price')}")
        if data.get("rooms", 0) <= 0:
            raise ValidationError(f"Invalid rooms: {data.get('rooms')}")


# ============================================================================
# Пример 2: Парсер с retry декоратором и классификацией ошибок
# ============================================================================


class RobustPropertyParser:
    """Устойчивый парсер с автоматическими повторами и fallback."""

    @retry(max_attempts=5, initial_delay=1.0)
    async def parse_with_retries(self, url: str) -> Dict[str, Any]:
        """
        Парсит квартиру с автоматическими повторами.

        @retry декоратор автоматически повторит функцию при исключении.
        """
        try:
            return await self._parse_internal(url)
        except Exception as e:
            # Преобразуем в парсер исключение для правильной обработки @retry
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="RobustPropertyParser.parse")
            raise parser_error

    async def parse_with_fallback(self, url: str, fallback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Парсит с fallback стратегией в зависимости от типа ошибки.

        Args:
            url: Основной URL
            fallback_url: Fallback URL (опционально)

        Returns:
            Данные квартиры

        Raises:
            ParsingError: Если оба источника недоступны
        """
        try:
            return await self._parse_internal(url)

        except Exception as e:
            classification = ErrorClassifier.classify(e)

            # Логируем с учетом классификации
            logger.log(
                logging.ERROR if classification["severity"] == ErrorSeverity.CRITICAL else logging.WARNING,
                f"Parse error ({classification['type']}): {e}",
            )

            # Проверяем нужна ли fallback
            if not fallback_url or classification["retryability"] == ErrorRetryability.NO_RETRY:
                # CRITICAL или NO_RETRY - не пробуем fallback
                raise

            # Пробуем fallback URL
            logger.info(f"Trying fallback URL: {fallback_url}")
            try:
                return await self._parse_internal(fallback_url)
            except Exception as fallback_error:
                # Fallback тоже не сработал
                logger.error(f"Fallback also failed: {fallback_error}")
                raise ParsingError(f"Both primary and fallback sources failed for {url}")

    async def _parse_internal(self, url: str) -> Dict[str, Any]:
        """Внутренний метод парсинга."""
        # Имитация парсинга
        await asyncio.sleep(0.1)
        return {"price": 5000000}


# ============================================================================
# Пример 3: Парсер с обработкой HTTP ошибок
# ============================================================================


class AdvancedPropertyParser:
    """Продвинутый парсер с обработкой HTTP статусов."""

    async def parse(self, url: str) -> Dict[str, Any]:
        """Парсит с обработкой HTTP ошибок."""
        try:
            response = await self._fetch(url)
            return self._extract_data(response)

        except Exception as e:
            # Конвертируем и логируем
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="AdvancedPropertyParser.parse")

            # Проверяем нужно ли повторять
            if ErrorClassifier.should_retry(parser_error):
                logger.info(f"Retryable error, will attempt again: {type(parser_error).__name__}")
                # Здесь можно добавить логику повтора
            else:
                logger.error(f"Non-retryable error: {type(parser_error).__name__}")

            raise parser_error

    async def _fetch(self, url: str) -> Dict[str, Any]:
        """Имитирует фетчинг с различными ошибками."""

        class Response:
            def __init__(self, status_code: int, data: Dict[str, Any]):
                self.status_code = status_code
                self.data = data
                self.headers = {"Retry-After": "60"}

            def json(self):
                return self.data

        # Имитация различных ответов
        return Response(200, {"price": 5000000})

    def _extract_data(self, response) -> Dict[str, Any]:
        """Извлекает данные из ответа."""
        # Проверяем HTTP статус
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif response.status_code == 503:
            raise SourceUnavailableError("Service temporarily unavailable")
        elif response.status_code in (401, 403):
            raise AuthenticationError("Invalid API credentials")
        elif response.status_code == 404:
            raise SourceUnavailableError("Property not found")
        elif response.status_code >= 400:
            raise NetworkError(f"HTTP error {response.status_code}")

        return response.json()


# ============================================================================
# Пример 4: Парсер с стратегией выбора на основе классификации
# ============================================================================


class SmartPropertyParser:
    """Умный парсер с выбором стратегии на основе типа ошибки."""

    async def parse_batch(self, urls: list) -> Dict[str, Dict[str, Any]]:
        """
        Парсит набор квартир с умной обработкой ошибок.

        Использует разные стратегии для разных типов ошибок:
        - MUST_RETRY: пытается несколько раз с задержкой
        - SHOULD_RETRY: пытается один раз с fallback
        - NO_RETRY: логирует ошибку и переходит дальше
        """
        results = {}
        failed = {}

        for url in urls:
            try:
                result = await self.parse_single(url)
                results[url] = result

            except Exception as e:
                classification = ErrorClassifier.classify(e)
                failed[url] = classification

                # Выбираем стратегию на основе классификации
                if classification["retryability"] == ErrorRetryability.MUST_RETRY:
                    logger.warning(f"MUST_RETRY error for {url}: {classification['type']}")
                    # Здесь можно добавить логику для повтора с очередью

                elif classification["retryability"] == ErrorRetryability.SHOULD_RETRY:
                    logger.info(f"SHOULD_RETRY error for {url}: {classification['type']}")
                    # Можно попробовать fallback

                else:
                    logger.error(f"NO_RETRY error for {url}: {classification['type']}")
                    # Просто пропускаем

        logger.info(f"Processed {len(results)} successful, {len(failed)} failed")
        return results

    async def parse_single(self, url: str) -> Dict[str, Any]:
        """Парсит одну квартиру."""
        # Имитация
        await asyncio.sleep(0.1)
        return {"url": url, "price": 5000000}


# ============================================================================
# Пример 5: Интеграция с @retry декоратором
# ============================================================================


class CacheAwareParser:
    """Парсер с кэшем и умной обработкой ошибок."""

    def __init__(self):
        self._cache = {}

    @retry(max_attempts=3, initial_delay=1.0, max_delay=10.0)
    async def parse_with_cache(self, url: str) -> Dict[str, Any]:
        """
        Парсит с кэшем и автоматическими повторами.

        @retry будет автоматически повторять при исключении.
        """
        # Проверяем кэш
        if url in self._cache:
            logger.debug(f"Cache hit for {url}")
            return self._cache[url]

        # Парсим
        try:
            result = await self._parse_internal(url)
            self._cache[url] = result
            return result

        except Exception as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="CacheAwareParser.parse_with_cache")

            # Если это ошибка которую нужно повторять, пробросим дальше
            # @retry поймет это исключение и повторит
            if ErrorClassifier.should_retry(parser_error):
                raise parser_error
            else:
                # Для ошибок которые не нужно повторять - можем логировать и вернуть None
                logger.error(f"Cannot retry {type(parser_error).__name__}, skipping {url}")
                raise

    async def _parse_internal(self, url: str) -> Dict[str, Any]:
        """Внутренний парсинг."""
        await asyncio.sleep(0.1)
        return {"url": url, "price": 5000000}


# ============================================================================
# Пример использования
# ============================================================================


async def main():
    """Демонстрирует использование парсеров."""

    # Пример 1: Простой парсер
    parser1 = SimplePropertyParser()
    try:
        result = await parser1.parse("https://example.com/property/1")
        print(f"✅ Parsed: {result}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Пример 2: Устойчивый парсер
    parser2 = RobustPropertyParser()
    try:
        result = await parser2.parse_with_retries("https://example.com/property/2")
        print(f"✅ Parsed with retries: {result}")
    except Exception as e:
        print(f"❌ Failed after retries: {e}")

    # Пример 3: Продвинутый парсер
    parser3 = AdvancedPropertyParser()
    try:
        result = await parser3.parse("https://example.com/property/3")
        print(f"✅ Parsed with HTTP handling: {result}")
    except Exception as e:
        print(f"❌ Failed with HTTP error: {e}")

    # Пример 4: Умный парсер для батча
    parser4 = SmartPropertyParser()
    results = await parser4.parse_batch([
        "https://example.com/property/4",
        "https://example.com/property/5",
        "https://example.com/property/6",
    ])
    print(f"✅ Batch parsed: {len(results)} successful")

    # Пример 5: Парсер с кэшем
    parser5 = CacheAwareParser()
    try:
        result = await parser5.parse_with_cache("https://example.com/property/7")
        print(f"✅ Parsed with cache: {result}")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
