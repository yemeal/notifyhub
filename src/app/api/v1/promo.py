from typing import Annotated

import structlog
from fastapi import APIRouter, Body, status
from pydantic import BaseModel

from src.app.tasks.broadcast import send_bulk_promo

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class BulkPromoRequest(BaseModel):
    recipients: list[str]
    subject: str
    body: str


@router.post("/bulk-promo", status_code=status.HTTP_202_ACCEPTED)
async def send_promo(body: Annotated[BulkPromoRequest, Body(...)]):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    # queue не указываем - task_routes подхватит и направит в notifications.bulk
    result = send_bulk_promo.apply_async(
        args=[body.recipients, body.subject, body.body],
        headers={"X-Request-Id": str(request_id)},
    )

    return {"task_id": result.id, "queue": "notifications.bulk"}
