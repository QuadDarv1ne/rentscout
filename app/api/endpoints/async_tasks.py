"""
Async task processing for long-running operations.

Provides endpoints for:
- Submitting async tasks
- Checking task status
- Cancelling tasks
- Getting task results
"""
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from app.utils.logger import logger

router = APIRouter(prefix="/tasks", tags=["Async Tasks"])


# In-memory task store (use Redis in production)
task_store: Dict[str, Dict[str, Any]] = {}


class TaskStatus(str):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSubmitRequest(BaseModel):
    """Task submission request."""
    task_type: str = Field(..., description="Type of task to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")


class TaskResponse(BaseModel):
    """Task response."""
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status")
    created_at: str = Field(..., description="Task creation time")
    updated_at: Optional[str] = Field(None, description="Last update time")
    result: Optional[Any] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    progress: int = Field(default=0, description="Progress percentage (0-100)")


class TaskListResponse(BaseModel):
    """Task list response."""
    tasks: List[TaskResponse] = Field(..., description="List of tasks")
    total: int = Field(..., description="Total number of tasks")


def create_task(task_type: str, params: Dict[str, Any]) -> str:
    """Create a new task entry."""
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    task_store[task_id] = {
        "task_id": task_id,
        "task_type": task_type,
        "status": TaskStatus.PENDING,
        "params": params,
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
        "progress": 0,
    }
    
    logger.info(f"Task created: {task_id} ({task_type})")
    return task_id


def update_task(task_id: str, **kwargs):
    """Update task status."""
    if task_id not in task_store:
        raise ValueError(f"Task {task_id} not found")
    
    task_store[task_id]["updated_at"] = datetime.utcnow().isoformat()
    
    for key, value in kwargs.items():
        if key in task_store[task_id]:
            task_store[task_id][key] = value


async def execute_task(task_id: str, task_type: str, params: Dict[str, Any]):
    """Execute a task asynchronously."""
    try:
        update_task(task_id, status=TaskStatus.RUNNING, progress=10)
        
        # Simulate different task types
        if task_type == "bulk_import":
            await execute_bulk_import(task_id, params)
        elif task_type == "data_export":
            await execute_data_export(task_id, params)
        elif task_type == "cache_warm":
            await execute_cache_warm(task_id, params)
        elif task_type == "data_cleanup":
            await execute_data_cleanup(task_id, params)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
        
        update_task(task_id, status=TaskStatus.COMPLETED, progress=100)
        logger.info(f"Task completed: {task_id}")
        
    except asyncio.CancelledError:
        update_task(task_id, status=TaskStatus.CANCELLED)
        logger.info(f"Task cancelled: {task_id}")
        
    except Exception as e:
        update_task(task_id, status=TaskStatus.FAILED, error=str(e))
        logger.error(f"Task failed: {task_id} - {e}")


async def execute_bulk_import(task_id: str, params: Dict[str, Any]):
    """Execute bulk import task."""
    count = params.get("count", 100)
    
    for i in range(count):
        # Check if cancelled
        if task_store[task_id]["status"] == TaskStatus.CANCELLED:
            return
        
        # Simulate import
        await asyncio.sleep(0.01)
        progress = int((i + 1) / count * 100)
        update_task(task_id, progress=progress)
    
    update_task(task_id, result={"imported": count})


async def execute_data_export(task_id: str, params: Dict[str, Any]):
    """Execute data export task."""
    format_type = params.get("format", "csv")
    
    # Simulate export
    for progress in range(0, 101, 10):
        if task_store[task_id]["status"] == TaskStatus.CANCELLED:
            return
        
        await asyncio.sleep(0.1)
        update_task(task_id, progress=progress)
    
    update_task(task_id, result={"format": format_type, "file": "export.csv"})


async def execute_cache_warm(task_id: str, params: Dict[str, Any]):
    """Execute cache warming task."""
    cities = params.get("cities", ["Москва"])
    
    for i, city in enumerate(cities):
        if task_store[task_id]["status"] == TaskStatus.CANCELLED:
            return
        
        # Simulate cache warm
        await asyncio.sleep(0.2)
        progress = int((i + 1) / len(cities) * 100)
        update_task(task_id, progress=progress)
    
    update_task(task_id, result={"warmed_cities": cities})


async def execute_data_cleanup(task_id: str, params: Dict[str, Any]):
    """Execute data cleanup task."""
    days = params.get("days", 30)
    
    # Simulate cleanup
    for progress in range(0, 101, 20):
        if task_store[task_id]["status"] == TaskStatus.CANCELLED:
            return
        
        await asyncio.sleep(0.1)
        update_task(task_id, progress=progress)
    
    update_task(task_id, result={"cleaned_days": days})


@router.post("/submit", response_model=TaskResponse)
async def submit_task(request: TaskSubmitRequest, background_tasks: BackgroundTasks):
    """
    Submit a new async task.

    Args:
        request: Task submission request
        background_tasks: FastAPI background tasks

    Returns:
        Task information with ID
    """
    task_id = create_task(request.task_type, request.params)
    
    # Schedule task execution
    background_tasks.add_task(
        execute_task,
        task_id,
        request.task_type,
        request.params
    )
    
    task_data = task_store[task_id]
    
    return TaskResponse(
        task_id=task_data["task_id"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        updated_at=task_data["updated_at"],
        result=task_data["result"],
        error=task_data["error"],
        progress=task_data["progress"],
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    Get task status and progress.

    Args:
        task_id: Task ID

    Returns:
        Task status and result
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = task_store[task_id]
    
    return TaskResponse(
        task_id=task_data["task_id"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        updated_at=task_data["updated_at"],
        result=task_data["result"],
        error=task_data["error"],
        progress=task_data["progress"],
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List tasks with optional filtering.

    Args:
        status: Filter by status
        limit: Maximum tasks to return
        offset: Offset for pagination

    Returns:
        List of tasks
    """
    tasks = list(task_store.values())
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    # Sort by created_at descending
    tasks.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Apply pagination
    total = len(tasks)
    tasks = tasks[offset:offset + limit]
    
    task_responses = [
        TaskResponse(
            task_id=t["task_id"],
            status=t["status"],
            created_at=t["created_at"],
            updated_at=t["updated_at"],
            result=t["result"],
            error=t["error"],
            progress=t["progress"],
        )
        for t in tasks
    ]
    
    return TaskListResponse(tasks=task_responses, total=total)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str):
    """
    Cancel a running task.

    Args:
        task_id: Task ID

    Returns:
        Updated task status
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = task_store[task_id]
    
    if task_data["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Task already finished")
    
    update_task(task_id, status=TaskStatus.CANCELLED)
    
    return TaskResponse(
        task_id=task_data["task_id"],
        status=TaskStatus.CANCELLED,
        created_at=task_data["created_at"],
        updated_at=task_data["updated_at"],
        result=task_data["result"],
        error=task_data["error"],
        progress=task_data["progress"],
    )


@router.delete("/{task_id}", response_model=Dict[str, bool])
async def delete_task(task_id: str):
    """
    Delete a task from the store.

    Args:
        task_id: Task ID

    Returns:
        Deletion result
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del task_store[task_id]
    
    return {"deleted": True}


@router.post("/cleanup")
async def cleanup_tasks(
    older_than_hours: int = Body(default=24, embed=True),
    status_filter: Optional[str] = Body(default=None, embed=True),
):
    """
    Clean up old completed/failed tasks.

    Args:
        older_than_hours: Remove tasks older than this many hours
        status_filter: Only remove tasks with this status

    Returns:
        Cleanup result
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    removed = 0
    
    task_ids_to_remove = []
    
    for task_id, task_data in task_store.items():
        created_at = datetime.fromisoformat(task_data["created_at"])
        
        if created_at < cutoff:
            if status_filter is None or task_data["status"] == status_filter:
                task_ids_to_remove.append(task_id)
    
    for task_id in task_ids_to_remove:
        del task_store[task_id]
        removed += 1
    
    logger.info(f"Cleaned up {removed} tasks")
    
    return {
        "removed": removed,
        "cutoff_hours": older_than_hours,
    }


__all__ = ["router"]
