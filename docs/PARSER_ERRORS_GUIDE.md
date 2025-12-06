# Руководство по обработке ошибок парсеров

## Обзор

Новая система обработки ошибок в `app/utils/parser_errors.py` предоставляет:

- **7 типов специфичных ошибок** для разных сценариев сбоя
- **Автоматическую классификацию** ошибок по типам и стратегиям обработки
- **Интеллектуальные стратегии повтора** с разными задержками
- **Единообразное логирование** с учетом серьезности

## Типы ошибок и их характеристики

### 1. NetworkError (Сетевая ошибка)

**Когда использовать**: Проблемы с подключением, потеря сети

```python
from app.utils.parser_errors import NetworkError

try:
    response = requests.get(url)
except requests.ConnectionError as e:
    raise NetworkError(f"Connection failed: {e}")
```

**Стратегия повтора**:

- Max retries: 5
- Base delay: 2.0 сек
- Exponential backoff: да

### 2. RateLimitError (Превышение rate limit)

**Когда использовать**: HTTP 429, слишком много запросов

```python
from app.utils.parser_errors import RateLimitError

if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    raise RateLimitError(f"Rate limited, retry after {retry_after}s")
```

**Стратегия повтора**:

- Max retries: 3
- Base delay: 10.0 сек (большая задержка!)
- Exponential backoff: да

### 3. TimeoutError (Timeout)

**Когда использовать**: Превышено время ожидания соединения

```python
from app.utils.parser_errors import TimeoutError

try:
    response = requests.get(url, timeout=30)
except requests.Timeout as e:
    raise TimeoutError(f"Request timeout after 30s: {e}")
```

**Стратегия повтора**:

- Max retries: 4
- Base delay: 3.0 сек
- Exponential backoff: да

### 4. SourceUnavailableError (Источник недоступен)

**Когда использовать**: HTTP 503, 502, 504, 404

```python
from app.utils.parser_errors import SourceUnavailableError

if response.status_code == 503:
    raise SourceUnavailableError(f"Service unavailable (503)")
elif response.status_code == 404:
    raise SourceUnavailableError(f"Resource not found (404)")
```

**Стратегия повтора**:

- Max retries: 3
- Base delay: 5.0 сек
- Exponential backoff: да

### 5. ParsingError (Ошибка парсинга)

**Когда использовать**: Неверная структура HTML, невалидные данные

```python
from app.utils.parser_errors import ParsingError

try:
    price = soup.find('span', class_='price').text
except (AttributeError, ValueError) as e:
    raise ParsingError(f"Cannot parse price: {e}")
```

**Стратегия повтора**:

- Max retries: 0 (не повторять)
- Severity: WARNING

### 6. ValidationError (Ошибка валидации)

**Когда использовать**: Данные не соответствуют ожиданиям

```python
from app.utils.parser_errors import ValidationError

if not price or price < 0:
    raise ValidationError(f"Invalid price value: {price}")
```

**Стратегия повтора**:

- Max retries: 0 (не повторять)
- Severity: WARNING

### 7. AuthenticationError (Ошибка аутентификации)

**Когда использовать**: HTTP 401, 403, проблемы с credentials

```python
from app.utils.parser_errors import AuthenticationError

if response.status_code == 401:
    raise AuthenticationError("Invalid API token")
elif response.status_code == 403:
    raise AuthenticationError("Access denied")
```

**Стратегия повтора**:

- Max retries: 0 (не повторять)
- Severity: CRITICAL (требует исправления конфигурации)

## Использование в парсерах

### Пример 1: Простой парсер с обработкой ошибок

```python
from app.utils.parser_errors import (
    ParserErrorHandler,
    NetworkError,
    ParsingError,
    TimeoutError as ParserTimeoutError,
)

class CianParser:
    async def parse(self, url: str) -> dict:
        try:
            response = await self._fetch(url)
            return self._extract_data(response)
        except asyncio.TimeoutError as e:
            ParserErrorHandler.log_error(e, context="CianParser.parse")
            raise ParserTimeoutError(f"Timeout: {e}")
        except requests.ConnectionError as e:
            ParserErrorHandler.log_error(e, context="CianParser.parse")
            raise NetworkError(f"Connection failed: {e}")
        except Exception as e:
            ParserErrorHandler.log_error(e, context="CianParser.parse")
            raise ParsingError(f"Parsing failed: {e}")

    async def _fetch(self, url: str) -> str:
        # Fetch with timeout
        ...

    def _extract_data(self, html: str) -> dict:
        # Parse and extract data
        ...
```

### Пример 2: Использование с @retry декоратором

```python
from app.utils.retry import retry
from app.utils.parser_errors import (
    ErrorClassifier,
    ParserErrorHandler,
    RateLimitError,
    NetworkError,
)

class AvitoParser:
    @retry(max_attempts=5, initial_delay=2.0)
    async def parse_property(self, property_id: str) -> dict:
        try:
            response = await self._fetch_property(property_id)
            return response.json()
        except Exception as e:
            # Преобразуем в подходящее исключение
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            
            # Логируем
            ParserErrorHandler.log_error(parser_error, context="parse_property")
            
            # Проверяем нужно ли повторять
            if ErrorClassifier.should_retry(parser_error):
                raise parser_error  # @retry поймет это исключение
            else:
                raise  # Не повторяем
```

### Пример 3: Классификация и выбор стратегии

```python
from app.utils.parser_errors import ErrorClassifier, ErrorRetryability

class RobustParser:
    async def parse_with_fallback(self, url: str) -> dict:
        try:
            return await self._primary_source(url)
        except Exception as e:
            classification = ErrorClassifier.classify(e)
            
            # Выбираем стратегию на основе классификации
            if classification["retryability"] == ErrorRetryability.MUST_RETRY:
                logger.warning(f"Will retry: {classification['type']}")
                return await self._fallback_source(url)
            
            elif classification["retryability"] == ErrorRetryability.SHOULD_RETRY:
                logger.info(f"Could retry: {classification['type']}")
                try:
                    return await self._fallback_source(url)
                except:
                    raise e  # Вернем оригинальную ошибку
            
            else:
                logger.error(f"Cannot retry: {classification['type']}")
                raise e
```

## Интеграция с REST API

### В endpoints/properties.py

Замените старую обработку ошибок:

```python
# ДО: Обычная обработка
@app.get("/api/properties")
async def search_properties(q: str, ...):
    try:
        results = await search_service.search(q, ...)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Search failed")
```

На новую обработку:

```python
from app.utils.parser_errors import ErrorClassifier, ErrorSeverity

@app.get("/api/properties")
async def search_properties(q: str, ...):
    try:
        results = await search_service.search(q, ...)
    except Exception as e:
        classification = ErrorClassifier.classify(e)
        
        # Определяем HTTP статус на основе классификации
        if classification["severity"] == ErrorSeverity.CRITICAL:
            logger.error(f"Critical error: {classification['type']}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )
        else:
            logger.warning(f"Search error: {classification['type']}")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable"
            )
```

## Логирование

Автоматическое логирование в зависимости от типа ошибки:

```python
from app.utils.parser_errors import ParserErrorHandler

# Critical
error = AuthenticationError("Invalid token")
ParserErrorHandler.log_error(error, context="parse_url")
# LOG: CRITICAL - parse_url: [AuthenticationError] Invalid token

# Warning
error = NetworkError("Connection refused")
ParserErrorHandler.log_error(error, context="fetch_html")
# LOG: WARNING - fetch_html: [NetworkError] Connection refused

# Info
error = ParsingError("Invalid HTML")
ParserErrorHandler.log_error(error, context="extract_price")
# LOG: INFO - extract_price: [ParsingError] Invalid HTML
```

## Тестирование

Система включает 35 comprehensive тестов:

```bash
# Запуск всех тестов
pytest app/tests/test_parser_errors.py -v

# Запуск конкретного теста
pytest app/tests/test_parser_errors.py::TestErrorClassifier::test_classify_rate_limit_error -v

# С покрытием
pytest app/tests/test_parser_errors.py --cov=app.utils.parser_errors
```

### Покрытие тестами

- ✅ Создание всех 7 типов ошибок
- ✅ Классификация каждого типа ошибки
- ✅ Проверка стратегий повтора
- ✅ Конвертация обычных Exception в ParserException
- ✅ HTTP ошибки (429, 503, 502, 504, 401, 403, 404)
- ✅ Network ошибки (timeout, connection)
- ✅ Edge cases (пустые сообщения, очень длинные, спецсимволы)
- ✅ Консистентность классификации

## Миграция существующих парсеров

### Шаг 1: Добавить импорты

```python
from app.utils.parser_errors import (
    ParserErrorHandler,
    NetworkError,
    RateLimitError,
    TimeoutError as ParserTimeoutError,
    SourceUnavailableError,
    ParsingError,
    ValidationError,
    AuthenticationError,
    ErrorClassifier,
)
```

### Шаг 2: Заменить базовые try-except блоки

```python
# ДО
try:
    response = requests.get(url)
except Exception as e:
    logger.error(f"Error: {e}")
    raise

# ПОСЛЕ
try:
    response = requests.get(url)
except Exception as e:
    parser_error = ParserErrorHandler.convert_to_parser_exception(e)
    ParserErrorHandler.log_error(parser_error, context="fetch_url")
    raise parser_error
```

### Шаг 3: Добавить специфичные проверки

```python
# Проверка HTTP статусов
if response.status_code == 429:
    raise RateLimitError(f"Rate limited: {response.headers.get('Retry-After')}")
elif response.status_code == 503:
    raise SourceUnavailableError("Service unavailable")
elif response.status_code in (401, 403):
    raise AuthenticationError(f"Auth failed: {response.status_code}")
```

## Best Practices

1. **Используйте специфичные типы ошибок**
   - Помогает выбрать правильную стратегию повтора
   - Упрощает тестирование

2. **Логируйте с контекстом**
   ```python
   ParserErrorHandler.log_error(error, context="parse_property_123")
   ```

3. **Проверяйте нужность повтора перед тем как повторять**
   ```python
   if ErrorClassifier.should_retry(error):
       # повторить запрос
   ```

4. **Используйте @retry декоратор для автоматических повторов**
   ```python
   @retry(max_attempts=5)
   async def fetch_and_parse(url):
       ...
   ```

5. **Преобразуйте исключения на границах слоев**
   - Parser слой → ParserException
   - API слой → HTTPException

## Производительность

- **Нулевой overhead**: Классификация - это простой поиск в словаре O(1)
- **Lazy evaluation**: Тяжелые операции логирования только при необходимости
- **Memory efficient**: Не хранит историю ошибок, только классификацию

## Дальнейшие улучшения

- [ ] Метрики для каждого типа ошибок
- [ ] Алерты на критичные ошибки (AuthenticationError)
- [ ] Dashboard для мониторинга частоты ошибок по типам
- [ ] Автоматическое отключение источника при частых ошибках
- [ ] Кэширование успешных результатов при временных ошибках

## Ссылки

- [retry.py](../app/utils/retry.py) - Декоратор для автоматических повторов
- [logger.py](../app/utils/logger.py) - Система логирования
- [test_parser_errors.py](../app/tests/test_parser_errors.py) - 35 тестов системы
