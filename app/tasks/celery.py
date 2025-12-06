"""Celery конфигурация и задачи для фонового парсинга."""

from celery import Celery
from celery.schedules import crontab
import asyncio
from typing import List, Dict, Any
import logging

from app.core.config import settings
from app.services.search import SearchService
from app.services.advanced_cache import advanced_cache_manager
from app.models.schemas import PropertyCreate

logger = logging.getLogger(__name__)

# Создаем Celery приложение
celery_app = Celery(
    "rentscout",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 минут максимум на задачу
    task_soft_time_limit=240,  # 4 минуты предупреждение
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,  # Результаты хранятся 1 час
)

# Периодические задачи (Celery Beat)
celery_app.conf.beat_schedule = {
    # Обновление кеша для популярных городов каждые 30 минут
    "warm-cache-popular-cities": {
        "task": "app.tasks.celery.warm_cache_task",
        "schedule": crontab(minute="*/30"),
        "args": (["Москва", "Санкт-Петербург", "Новосибирск"],),
    },
    # Очистка старого кеша каждый день в 3:00
    "cleanup-old-cache": {
        "task": "app.tasks.celery.cleanup_cache_task",
        "schedule": crontab(hour=3, minute=0),
    },
    # Обновление данных для топ-5 городов каждый час
    "update-top-cities": {
        "task": "app.tasks.celery.batch_parse_task",
        "schedule": crontab(minute=0),  # Каждый час
        "args": (
            [
                "Москва",
                "Санкт-Петербург",
                "Новосибирск",
                "Екатеринбург",
                "Казань",
            ],
        ),
    },
}


@celery_app.task(name="app.tasks.celery.parse_city_task", bind=True, max_retries=3)
def parse_city_task(self, city: str, property_type: str = "Квартира") -> Dict[str, Any]:
    """
    Фоновая задача парсинга города.
    
    Args:
        city: Название города
        property_type: Тип недвижимости
        
    Returns:
        Словарь с результатами парсинга
    """
    try:
        logger.info(f"Starting background parse task for {city}")
        
        # Запускаем асинхронный парсинг в event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            search_service = SearchService()
            properties = loop.run_until_complete(
                search_service.search(city, property_type)
            )
            
            result = {
                "status": "success",
                "city": city,
                "property_type": property_type,
                "count": len(properties),
                "properties": [
                    {
                        "id": prop.id,
                        "source": prop.source,
                        "title": prop.title,
                        "price": prop.price,
                        "rooms": prop.rooms,
                        "area": prop.area,
                    }
                    for prop in properties[:100]  # Лимит для результата
                ],
            }
            
            logger.info(
                f"Parse task completed for {city}: {len(properties)} properties found"
            )
            return result
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Parse task failed for {city}: {exc}", exc_info=True)
        
        # Retry с exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.celery.batch_parse_task")
def batch_parse_task(cities: List[str], property_type: str = "Квартира") -> Dict[str, Any]:
    """
    Пакетная задача парсинга нескольких городов.
    
    Args:
        cities: Список городов
        property_type: Тип недвижимости
        
    Returns:
        Сводка результатов
    """
    logger.info(f"Starting batch parse for {len(cities)} cities")
    
    results = []
    for city in cities:
        try:
            # Запускаем отдельную задачу для каждого города асинхронно
            task = parse_city_task.apply_async(
                args=[city, property_type],
                countdown=0,
            )
            results.append({
                "city": city,
                "task_id": task.id,
                "status": "queued",
            })
        except Exception as e:
            logger.error(f"Failed to queue task for {city}: {e}")
            results.append({
                "city": city,
                "status": "failed",
                "error": str(e),
            })
    
    return {
        "status": "batch_queued",
        "total_cities": len(cities),
        "results": results,
    }


@celery_app.task(name="app.tasks.celery.warm_cache_task")
def warm_cache_task(cities: List[str]) -> Dict[str, Any]:
    """
    Задача предварительного прогрева кеша.
    
    Args:
        cities: Список городов для прогрева
        
    Returns:
        Результат операции
    """
    logger.info(f"Starting cache warming for {len(cities)} cities")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Подключаемся к Redis
        loop.run_until_complete(advanced_cache_manager.connect())
        
        search_service = SearchService()
        
        # Прогреваем кеш
        loop.run_until_complete(
            advanced_cache_manager.warm_cache(
                search_service.search,
                cities=cities,
            )
        )
        
        logger.info(f"Cache warming completed for {len(cities)} cities")
        
        return {
            "status": "success",
            "cities_warmed": len(cities),
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }
    finally:
        loop.run_until_complete(advanced_cache_manager.disconnect())
        loop.close()


@celery_app.task(name="app.tasks.celery.cleanup_cache_task")
def cleanup_cache_task() -> Dict[str, Any]:
    """
    Задача очистки старого кеша.
    
    Returns:
        Результат очистки
    """
    logger.info("Starting cache cleanup task")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(advanced_cache_manager.connect())
        
        # Очищаем все ключи парсеров старше определенного времени
        cleared = loop.run_until_complete(
            advanced_cache_manager.clear_pattern("parser:*")
        )
        
        logger.info(f"Cache cleanup completed: {cleared} keys cleared")
        
        return {
            "status": "success",
            "keys_cleared": cleared,
        }
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }
    finally:
        loop.run_until_complete(advanced_cache_manager.disconnect())
        loop.close()


@celery_app.task(name="app.tasks.celery.schedule_parse_task")
def schedule_parse_task(
    city: str,
    property_type: str = "Квартира",
    eta_seconds: int = 0,
) -> Dict[str, str]:
    """
    Запланировать задачу парсинга на определенное время.
    
    Args:
        city: Город
        property_type: Тип недвижимости
        eta_seconds: Через сколько секунд запустить
        
    Returns:
        Task ID и статус
    """
    task = parse_city_task.apply_async(
        args=[city, property_type],
        countdown=eta_seconds,
    )
    
    logger.info(f"Scheduled parse task for {city} in {eta_seconds}s: {task.id}")
    
    return {
        "task_id": task.id,
        "status": "scheduled",
        "city": city,
        "eta_seconds": eta_seconds,
    }


# Утилиты для работы с задачами

def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Получить статус задачи по ID.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Информация о задаче
    """
    task = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": task.status,
        "ready": task.ready(),
        "successful": task.successful() if task.ready() else None,
        "result": task.result if task.ready() and task.successful() else None,
        "error": str(task.result) if task.ready() and not task.successful() else None,
    }


def cancel_task(task_id: str) -> Dict[str, Any]:
    """
    Отменить задачу.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Результат отмены
    """
    celery_app.control.revoke(task_id, terminate=True)
    
    logger.info(f"Task {task_id} cancelled")
    
    return {
        "task_id": task_id,
        "status": "cancelled",
    }
