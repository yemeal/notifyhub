import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, status

from src.app.schemas.topic import NotificationSendRequest, NotificationSendResponse
from src.app.tasks.topic import send_email_notification, send_sms_notification

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post(
    "/send",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=NotificationSendResponse,
)
async def send_notification(body: Annotated[NotificationSendRequest, Body(...)]):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    routing_key = f"notifications.{body.channel}.{body.priority}"
    notification_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    task = send_email_notification if body.channel == "email" else send_sms_notification

    task.apply_async(
        args=[notification_id, body.priority, body.recipient, body.message],
        task_id=task_id,
        exchange="notifications",
        routing_key=routing_key,
        headers={"X-Request-Id": str(request_id)},
    )

    return NotificationSendResponse(
        task_id=task_id,
        routing_key=routing_key,
    )
