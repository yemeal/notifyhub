from typing import Annotated

import structlog
from fastapi import APIRouter, Body, status
from pydantic import BaseModel

from src.app.tasks.email import send_otp

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class OtpRequest(BaseModel):
    user_id: str
    otp_code: str


@router.post("/otp", status_code=status.HTTP_202_ACCEPTED)
async def send_otp_notification(body: Annotated[OtpRequest, Body(...)]):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    # priority=9 значит "почти максимальный" (max=10 в нашей очереди)
    # queue не указываем - task_routes в celery_app.py подхватит автоматически
    result = send_otp.apply_async(
        args=[body.user_id, body.otp_code],
        priority=9,
        headers={"X-Request-Id": str(request_id)},
    )

    return {"task_id": result.id, "queue": "notifications.critical", "priority": 9}
