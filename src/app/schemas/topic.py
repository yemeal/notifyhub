from typing import Literal, Annotated

from pydantic import BaseModel, Field


class NotificationSendRequest(BaseModel):
    channel: Literal["email", "sms"]
    priority: Literal["critical", "normal"]
    recipient: Annotated[str, Field(..., min_length=1, max_length=100)]
    message: Annotated[str, Field(..., min_length=1, max_length=1000)]


class NotificationSendResponse(BaseModel):
    task_id: str
    routing_key: str
