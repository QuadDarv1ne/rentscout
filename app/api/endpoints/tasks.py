"""API endpoints для управления фоновыми задачами парсинга."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from celery.app.control import Inspect

from app.tasks.celery import (
    parse_city_task,
    batch_parse_task,
    schedule_parse_task,
    get_task_status,
    cancel_task,
    celery_app,
)
from app.utils.logger import logger

router = APIRouter()


# Pydantic модели для запросов

class ParseRequest(BaseModel):
    """Запрос на парсинг города."""
    
    city: str = Field(..., min_length=2, description="Название города")
    property_type: str = Field("Квартира", description="Тип недвижимости")


class BatchParseRequest(BaseModel):
    """Запрос на пакетный парсинг."""
    
    cities: List[str] = Field(..., min_length=1, max_length=20, description="Список городов (макс 20)")
    property_type: str = Field("Квартира", description="Тип недвижимости")


class ScheduleParseRequest(BaseModel):
    """Запрос на запланированный парсинг."""
    
    city: str = Field(..., min_length=2, description="Название города")
    property_type: str = Field("Квартира", description="Тип недвижимости")
    eta_seconds: int = Field(0, ge=0, le=86400, description="Через сколько секунд запустить (макс 24 часа)")


# Endpoints

@router.post("/tasks/parse", tags=["tasks"])
async def create_parse_task(request: ParseRequest) -> Dict[str, Any]:
    """
    Создать фоновую задачу парсинга города.
    
    Args:
        request: Параметры парсинга
        
    Returns:
        Информация о созданной задаче
    """
    try:
        task = parse_city_task.apply_async(
            args=[request.city, request.property_type]
        )
        
        logger.info(f"Created parse task {task.id} for {request.city}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "city": request.city,
            "property_type": request.property_type,
        }
        
    except Exception as e:
        logger.error(f"Failed to create parse task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create task: {str(e)}",
        )


@router.post("/tasks/parse/batch", tags=["tasks"])
async def create_batch_parse_task(request: BatchParseRequest) -> Dict[str, Any]:
    """
    Создать пакетную задачу парсинга нескольких городов.
    
    Args:
        request: Параметры пакетного парсинга
        
    Returns:
        Информация о созданных задачах
    """
    try:
        result = batch_parse_task.apply_async(
            args=[request.cities, request.property_type]
        )
        
        logger.info(
            f"Created batch parse task {result.id} for {len(request.cities)} cities"
        )
        
        return {
            "batch_task_id": result.id,
            "status": "queued",
            "cities_count": len(request.cities),
            "cities": request.cities,
        }
        
    except Exception as e:
        logger.error(f"Failed to create batch parse task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create batch task: {str(e)}",
        )


@router.post("/tasks/parse/schedule", tags=["tasks"])
async def create_scheduled_parse_task(request: ScheduleParseRequest) -> Dict[str, Any]:
    """
    Запланировать задачу парсинга на определенное время.
    
    Args:
        request: Параметры запланированного парсинга
        
    Returns:
        Информация о запланированной задаче
    """
    try:
        result = schedule_parse_task(
            city=request.city,
            property_type=request.property_type,
            eta_seconds=request.eta_seconds,
        )
        
        logger.info(
            f"Scheduled parse task for {request.city} in {request.eta_seconds}s"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to schedule parse task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule task: {str(e)}",
        )


@router.get("/tasks/{task_id}", tags=["tasks"])
async def get_task_info(task_id: str) -> Dict[str, Any]:
    """
    Получить информацию о задаче по ID.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Статус и результат задачи
    """
    try:
        status = get_task_status(task_id)
        return status
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Task not found or error: {str(e)}",
        )


@router.delete("/tasks/{task_id}", tags=["tasks"])
async def cancel_task_endpoint(task_id: str) -> Dict[str, Any]:
    """
    Отменить задачу.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Подтверждение отмены
    """
    try:
        result = cancel_task(task_id)
        logger.info(f"Cancelled task {task_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get("/tasks", tags=["tasks"])
async def list_tasks(
    limit: int = Query(10, ge=1, le=100, description="Количество задач"),
    status: Optional[str] = Query(None, description="Фильтр по статусу (PENDING, STARTED, SUCCESS, FAILURE)"),
) -> Dict[str, Any]:
    """
    Получить список активных и недавних задач через Celery Inspect.
    
    Args:
        limit: Максимальное количество задач
        status: Фильтр по статусу (опционально)
        
    Returns:
        Словарь с информацией о задачах
    """
    try:
        # Используем Celery Inspect для получения информации о задачах
        inspector = Inspect(app=celery_app)
        
        # Получаем активные задачи
        active_tasks = inspector.active() or {}
        # Получаем зарезервированные задачи (в очереди)
        reserved_tasks = inspector.reserved() or {}
        # Получаем зарегистрированные задачи
        registered_tasks = inspector.registered() or {}
        
        # Собираем информацию о задачах
        all_tasks = []
        
        # Обработка активных задач
        for worker_name, tasks in active_tasks.items():
            for task_info in tasks:
                task_data = {
                    "task_id": task_info.get("id"),
                    "name": task_info.get("name"),
                    "status": "STARTED",
                    "worker": worker_name,
                    "args": task_info.get("args"),
                    "kwargs": task_info.get("kwargs"),
                    "time_start": task_info.get("time_start"),
                }
                all_tasks.append(task_data)
        
        # Обработка зарезервированных задач
        for worker_name, tasks in reserved_tasks.items():
            for task_info in tasks:
                task_data = {
                    "task_id": task_info.get("id"),
                    "name": task_info.get("name"),
                    "status": "PENDING",
                    "worker": worker_name,
                    "args": task_info.get("args"),
                    "kwargs": task_info.get("kwargs"),
                }
                all_tasks.append(task_data)
        
        # Фильтруем по статусу если указан
        if status:
            all_tasks = [t for t in all_tasks if t["status"] == status.upper()]
        
        # Сортируем по времени начала (новые первыми)
        all_tasks.sort(
            key=lambda x: x.get("time_start", 0), 
            reverse=True
        )
        
        # Ограничиваем количество результатов
        all_tasks = all_tasks[:limit]
        
        logger.info(f"Retrieved {len(all_tasks)} tasks from Celery")
        
        return {
            "total": len(all_tasks),
            "limit": limit,
            "status_filter": status,
            "tasks": all_tasks,
            "workers": list(inspector.stats().keys()) if inspector.stats() else [],
            "registered_tasks": registered_tasks.get(
                list(registered_tasks.keys())[0] if registered_tasks else None, 
                []
            ),
        }
        
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return {
            "total": 0,
            "limit": limit,
            "status_filter": status,
            "tasks": [],
            "workers": [],
            "error": str(e),
            "tip": "Убедитесь, что Celery worker запущен",
        }


@router.get("/tasks/workers/stats", tags=["tasks"])
async def get_workers_stats() -> Dict[str, Any]:
    """
    Получить статистику по всем Celery рабочим.
    
    Returns:
        Информация о рабочих и их статусе
    """
    try:
        inspector = Inspect(app=celery_app)
        
        # Получаем статистику по рабочим
        stats = inspector.stats() or {}
        active_tasks = inspector.active() or {}
        registered = inspector.registered() or {}
        
        workers_info = []
        for worker_name, worker_stats in stats.items():
            worker_data = {
                "name": worker_name,
                "status": "online",
                "pool": worker_stats.get("pool", {}).get("implementation"),
                "max_concurrency": worker_stats.get("pool", {}).get("max-concurrency", 0),
                "active_tasks": len(active_tasks.get(worker_name, [])),
                "processed_tasks": worker_stats.get("total", 0),
                "system": worker_stats.get("rusage", {}),
            }
            workers_info.append(worker_data)
        
        return {
            "online_workers": len(workers_info),
            "workers": workers_info,
            "total_active_tasks": sum(len(tasks) for tasks in active_tasks.values()),
            "registered_task_count": sum(
                len(tasks) for tasks in registered.values() if isinstance(tasks, list)
            ),
        }
        
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        return {
            "online_workers": 0,
            "workers": [],
            "error": str(e),
            "tip": "Убедитесь, что Celery worker запущен",
        }
