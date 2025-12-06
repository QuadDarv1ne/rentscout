"""API endpoints для управления фоновыми задачами парсинга."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.tasks.celery import (
    parse_city_task,
    batch_parse_task,
    schedule_parse_task,
    get_task_status,
    cancel_task,
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
    
    cities: List[str] = Field(..., min_items=1, max_items=20, description="Список городов (макс 20)")
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
) -> Dict[str, Any]:
    """
    Получить список недавних задач.
    
    Args:
        limit: Максимальное количество задач
        
    Returns:
        Список задач
    """
    # TODO: Реализовать через Celery inspect
    # Для полноценной реализации нужно использовать celery.control.inspect()
    
    return {
        "message": "Task listing not fully implemented yet",
        "tip": "Use /tasks/{task_id} to check specific task status",
    }
