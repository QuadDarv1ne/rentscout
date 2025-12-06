"""Тесты для Celery задач и фонового парсинга."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.tasks.celery import (
    celery_app,
    get_task_status,
    cancel_task,
)


def test_celery_app_config():
    """Тест конфигурации Celery приложения."""
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.task_time_limit == 300
    assert celery_app.conf.task_acks_late is True


def test_celery_beat_schedule():
    """Тест наличия периодических задач."""
    schedule = celery_app.conf.beat_schedule
    
    assert "warm-cache-popular-cities" in schedule
    assert "cleanup-old-cache" in schedule
    assert "update-top-cities" in schedule
    
    # Проверяем задачу прогрева кеша
    warm_task = schedule["warm-cache-popular-cities"]
    assert warm_task["task"] == "app.tasks.celery.warm_cache_task"
    assert "schedule" in warm_task


def test_get_task_status():
    """Тест получения статуса задачи."""
    with patch.object(celery_app, "AsyncResult") as mock_result:
        # Настраиваем мок
        mock_task = Mock()
        mock_task.id = "test-task-123"
        mock_task.status = "SUCCESS"
        mock_task.ready.return_value = True
        mock_task.successful.return_value = True
        mock_task.result = {"data": "test"}
        
        mock_result.return_value = mock_task
        
        # Получаем статус
        status = get_task_status("test-task-123")
        
        assert status["task_id"] == "test-task-123"
        assert status["status"] == "SUCCESS"
        assert status["ready"] is True
        assert status["successful"] is True
        assert status["result"] == {"data": "test"}


def test_get_task_status_pending():
    """Тест статуса задачи в состоянии PENDING."""
    with patch.object(celery_app, "AsyncResult") as mock_result:
        mock_task = Mock()
        mock_task.id = "test-task-456"
        mock_task.status = "PENDING"
        mock_task.ready.return_value = False
        
        mock_result.return_value = mock_task
        
        status = get_task_status("test-task-456")
        
        assert status["status"] == "PENDING"
        assert status["ready"] is False
        assert status["successful"] is None


def test_get_task_status_failure():
    """Тест статуса провалившейся задачи."""
    with patch.object(celery_app, "AsyncResult") as mock_result:
        mock_task = Mock()
        mock_task.id = "test-task-789"
        mock_task.status = "FAILURE"
        mock_task.ready.return_value = True
        mock_task.successful.return_value = False
        mock_task.result = Exception("Task failed")
        
        mock_result.return_value = mock_task
        
        status = get_task_status("test-task-789")
        
        assert status["status"] == "FAILURE"
        assert status["successful"] is False
        assert "error" in status


def test_cancel_task():
    """Тест отмены задачи."""
    with patch.object(celery_app.control, "revoke") as mock_revoke:
        result = cancel_task("test-task-cancel")
        
        mock_revoke.assert_called_once_with("test-task-cancel", terminate=True)
        assert result["task_id"] == "test-task-cancel"
        assert result["status"] == "cancelled"


@pytest.mark.parametrize("city,property_type", [
    ("Москва", "Квартира"),
    ("Санкт-Петербург", "Квартира"),
    ("Казань", "Дом"),
])
def test_parse_city_task_params(city, property_type):
    """Тест параметров задачи парсинга города."""
    from app.tasks.celery import parse_city_task
    
    # Проверяем что задача зарегистрирована
    assert parse_city_task.name == "app.tasks.celery.parse_city_task"
    assert parse_city_task.max_retries == 3


def test_batch_parse_task_registration():
    """Тест регистрации задачи пакетного парсинга."""
    from app.tasks.celery import batch_parse_task
    
    assert batch_parse_task.name == "app.tasks.celery.batch_parse_task"


def test_warm_cache_task_registration():
    """Тест регистрации задачи прогрева кеша."""
    from app.tasks.celery import warm_cache_task
    
    assert warm_cache_task.name == "app.tasks.celery.warm_cache_task"


def test_cleanup_cache_task_registration():
    """Тест регистрации задачи очистки кеша."""
    from app.tasks.celery import cleanup_cache_task
    
    assert cleanup_cache_task.name == "app.tasks.celery.cleanup_cache_task"


def test_schedule_parse_task_registration():
    """Тест регистрации задачи запланированного парсинга."""
    from app.tasks.celery import schedule_parse_task
    
    assert schedule_parse_task.name == "app.tasks.celery.schedule_parse_task"
