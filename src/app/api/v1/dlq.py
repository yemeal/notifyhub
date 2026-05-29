from typing import Annotated

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.database import get_async_session
from src.app.models.failed_task import FailedTask
from src.app.schemas.failed_task import (
    FailedTaskResponse,
    FailedTaskListResponse,
    RetryResponse,
)

# определяем, какую задачу нужно повторить
# маппинг имён задач на Celery-функции
from src.app.tasks.email import send_email

task_registry = {
    "tasks.send_email": send_email,
}


router = APIRouter(prefix="/api/v1/dlq", tags=["dlq"])


@router.get("/tasks", response_model=FailedTaskListResponse)
async def list_failed_tasks(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    # считаем общее количество
    total = (
        await session.execute(select(func.count()).select_from(FailedTask))
    ).scalar_one()

    # получаем записи с пагинацией
    result = await session.execute(
        select(FailedTask)
        .order_by(FailedTask.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = result.scalars().all()

    return FailedTaskListResponse(
        items=[FailedTaskResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/tasks/{task_id}/retry", response_model=RetryResponse)
async def retry_failed_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    failed_task = await session.get(FailedTask, task_id)
    if not failed_task:
        raise HTTPException(status_code=404, detail="Failed task not found")

    celery_task = task_registry.get(str(failed_task.task_name))
    if not celery_task:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task: {failed_task.task_name}",
        )

    # ставим задачу в основную очередь
    result = celery_task.apply_async(
        args=failed_task.args or [],
        kwargs=failed_task.kwargs or {},
    )

    await session.commit()

    return RetryResponse(
        status="retried",
        new_task_id=result.id,
        original_task_id=str(failed_task.original_task_id),
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_failed_task(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    failed_task = await session.get(FailedTask, task_id)
    if not failed_task:
        raise HTTPException(status_code=404, detail="Failed task not found")

    await session.delete(failed_task)
    await session.commit()
