# Система метрик и мониторинга

## Обзор

Система метрик предоставляет инструменты для мониторинга производительности приложения RentScout. Она включает в себя автоматический сбор метрик HTTP запросов, выполнения парсеров и других ключевых операций.

## Компоненты системы

### 1. MetricsCollector

Основной класс для сбора метрик. Предоставляет методы для записи различных типов метрик:

- HTTP запросы
- Выполнение парсеров
- Активные запросы

### 2. MetricsMiddleware

Middleware для FastAPI, который автоматически собирает метрики для всех HTTP запросов.

### 3. Декоратор @metrics_collector_decorator

Декоратор для автоматического сбора метрик выполнения методов парсеров.

## Метрики Prometheus

Система экспортирует следующие метрики в формате Prometheus:

### HTTP метрики

- `http_requests_total` - Общее количество HTTP запросов
- `http_request_duration_seconds` - Длительность HTTP запросов
- `http_active_requests` - Количество активных HTTP запросов

### Метрики парсеров

- `parser_calls_total` - Общее количество вызовов парсеров
- `parser_duration_seconds` - Длительность выполнения парсеров

## Использование

### Автоматический сбор метрик HTTP запросов

Метрики HTTP запросов собираются автоматически через Middleware, который уже подключен в `app/main.py`.

### Сбор метрик парсеров

Для автоматического сбора метрик выполнения парсеров, используйте декоратор `@metrics_collector_decorator`:

```python
from app.parsers.base_parser import metrics_collector_decorator

class MyParser(BaseParser):
    @metrics_collector_decorator
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Ваш код парсера
        pass
```

### Ручной сбор метрик

Вы также можете вручную записывать метрики через глобальный экземпляр `metrics_collector`:

```python
from app.utils.metrics import metrics_collector

# Запись метрики HTTP запроса
metrics_collector.record_request("GET", "/api/properties", 200, 0.15)

# Запись метрики парсера
metrics_collector.record_parser_call("AvitoParser", "success", 2.5)
```

## Доступ к метрикам

Метрики доступны по endpoint `/metrics` в формате Prometheus. Этот endpoint автоматически создается инструментатором Prometheus.

## Настройка

Система метрик не требует дополнительной настройки. Все метрики автоматически экспортируются при запуске приложения.