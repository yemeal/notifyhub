from fastapi import APIRouter
from celery.result import AsyncResult

from src.app.tasks.celery_app import celery

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery)
    return {
        "state": result.state,
        "result": result.result if result.ready() else None,
    }
