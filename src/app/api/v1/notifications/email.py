from typing import Annotated

from fastapi import APIRouter, Body, Depends, status, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.app.core.database import get_async_session
from src.app.schemas.email_task import EmailTaskCreate
from src.app.models.email_task import EmailTask as EmailTaskModel, EmailStatus
from src.app.tasks.email import send_email

router = APIRouter(prefix="/api/v1/notifications/email", tags=["notifications"])


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def send(
    body: Annotated[EmailTaskCreate, Body(...)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    new_email_task = EmailTaskModel(**body.model_dump(), status=EmailStatus.PENDING)
    session.add(new_email_task)
    await session.commit()

    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    result = send_email.apply_async(
        args=[str(new_email_task.id)],
        headers={"X-Request-Id": str(request_id)},
    )
    new_email_task.task_id = result.id
    await session.commit()
    return {
        "email_task_id": new_email_task.id,
        "task_id": new_email_task.task_id,
        "status": new_email_task.status.value,
    }


@router.get("/{email_task_id}", status_code=status.HTTP_200_OK)
async def get_email_task_status_from_database(
    email_task_id: Annotated[str, Path(...)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    res: EmailTaskModel | None = (
        await session.execute(
            select(EmailTaskModel).where(EmailTaskModel.id == email_task_id)
        )
    ).scalar_one_or_none()

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email task not found",
        )

    return {
        "id": res.id,
        "status": res.status.value,
    }
