import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, status
from pydantic import BaseModel

from src.app.tasks.broadcast import (
    send_welcome_email,
    log_user_registration,
    notify_slack_team,
)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class UserRegisteredEvent(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str


@router.post("/user-registered", status_code=status.HTTP_202_ACCEPTED)
async def user_registered(
    body: Annotated[UserRegisteredEvent, Body(...)],
):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id")

    task_id1 = str(uuid.uuid4())
    task_id2 = str(uuid.uuid4())
    task_id3 = str(uuid.uuid4())

    send_welcome_email.apply_async(
        args=[str(body.user_id), body.email, body.name],
        task_id=task_id1,
        exchange="user_events",
        routing_key="user.email",
        headers={"X-Request-Id": str(request_id)},
    )

    log_user_registration.apply_async(
        args=[str(body.user_id), body.email, body.name],
        task_id=task_id2,
        exchange="user_events",
        routing_key="user.analytics",
        headers={"X-Request-Id": str(request_id)},
    )

    notify_slack_team.apply_async(
        args=[str(body.user_id), body.email, body.name],
        task_id=task_id3,
        exchange="user_events",
        routing_key="user.slack",
        headers={"X-Request-Id": str(request_id)},
    )

    return {
        "published": True,
        "tasks": [task_id1, task_id2, task_id3],
    }
