"""
API endpoints для мониторинга парсеров.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from datetime import datetime

from app.utils.parser_monitor import monitor


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/parsers/summary")
async def get_parsers_summary() -> Dict[str, Any]:
    """
    Получить сводную информацию по всем парсерам.
    
    Returns:
        Сводка метрик всех парсеров
    """
    return monitor.get_summary()


@router.get("/parsers/{parser_name}")
async def get_parser_metrics(parser_name: str) -> Dict[str, Any]:
    """
    Получить детальные метрики конкретного парсера.
    
    Args:
        parser_name: Название парсера
        
    Returns:
        Метрики парсера
        
    Raises:
        HTTPException: Если парсер не найден
    """
    metrics = monitor.get_parser_metrics(parser_name)
    
    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail=f"Parser '{parser_name}' not found"
        )
        
    return metrics.to_dict()


@router.get("/parsers")
async def get_all_parsers_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Получить метрики всех парсеров.
    
    Returns:
        Словарь с метриками всех парсеров
    """
    return monitor.get_all_metrics()


@router.get("/errors")
async def get_recent_errors(
    parser_name: Optional[str] = Query(None, description="Фильтр по парсеру"),
    minutes: int = Query(60, ge=1, le=1440, description="Временное окно в минутах")
) -> Dict[str, Any]:
    """
    Получить недавние ошибки парсеров.
    
    Args:
        parser_name: Название парсера (опционально)
        minutes: Временное окно в минутах (по умолчанию 60)
        
    Returns:
        Список недавних ошибок
    """
    errors = monitor.get_recent_errors(parser_name=parser_name, minutes=minutes)
    
    return {
        "count": len(errors),
        "time_window_minutes": minutes,
        "parser_filter": parser_name,
        "errors": errors
    }


@router.get("/health")
async def get_parsers_health() -> Dict[str, Any]:
    """
    Проверка здоровья парсеров.
    
    Returns:
        Статус здоровья каждого парсера
    """
    all_metrics = monitor.get_all_metrics()
    health_status = {}
    
    for parser_name, metrics in all_metrics.items():
        success_rate = metrics.get('success_rate', 0)
        last_request = metrics.get('last_request_time')
        
        # Определение статуса
        if success_rate >= 95:
            status = "healthy"
        elif success_rate >= 80:
            status = "degraded"
        else:
            status = "unhealthy"
            
        health_status[parser_name] = {
            "status": status,
            "success_rate": success_rate,
            "last_request_time": last_request,
            "total_requests": metrics.get('total_requests', 0)
        }
        
    overall_status = "healthy"
    if any(h["status"] == "unhealthy" for h in health_status.values()):
        overall_status = "unhealthy"
    elif any(h["status"] == "degraded" for h in health_status.values()):
        overall_status = "degraded"
        
    return {
        "overall_status": overall_status,
        "parsers": health_status,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/reset")
async def reset_parser_metrics(
    parser_name: Optional[str] = Query(None, description="Название парсера для сброса")
) -> Dict[str, str]:
    """
    Сбросить метрики парсера.
    
    Args:
        parser_name: Название парсера (если None - сбросить все)
        
    Returns:
        Сообщение об успехе
    """
    monitor.reset_metrics(parser_name=parser_name)
    
    if parser_name:
        return {"message": f"Metrics for parser '{parser_name}' have been reset"}
    else:
        return {"message": "All parser metrics have been reset"}


@router.get("/export")
async def export_metrics_to_json(
    filepath: str = Query(..., description="Путь к файлу для экспорта")
) -> Dict[str, str]:
    """
    Экспортировать метрики в JSON файл.
    
    Args:
        filepath: Путь к файлу
        
    Returns:
        Сообщение об успехе
    """
    try:
        monitor.export_to_json(filepath)
        return {"message": f"Metrics exported to {filepath}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export metrics: {str(e)}"
        )
