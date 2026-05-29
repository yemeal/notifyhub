from typing import Annotated

import structlog
from fastapi import APIRouter, Query, status

from src.app.tasks.reports import generate_monthly_report

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/monthly", status_code=status.HTTP_202_ACCEPTED)
async def trigger_monthly_report(
    year: Annotated[int | None, Query()] = None,
    month: Annotated[int | None, Query()] = None,
):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    # queue не указываем - task_routes направит в reports.heavy
    result = generate_monthly_report.apply_async(
        args=[year, month],
        headers={"X-Request-Id": str(request_id)},
    )

    return {"task_id": result.id, "queue": "reports.heavy"}
