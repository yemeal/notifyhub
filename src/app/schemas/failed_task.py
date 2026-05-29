import uuid
from datetime import datetime
from pydantic import BaseModel


class FailedTaskResponse(BaseModel):
    id: uuid.UUID
    original_task_id: str
    task_name: str
    args: dict | list | None = None
    kwargs: dict | None = None
    error_message: str | None = None
    failure_count: int
    created_at: datetime
    last_retry_at: datetime | None = None

    model_config = {"from_attributes": True}


class FailedTaskListResponse(BaseModel):
    items: list[FailedTaskResponse]
    total: int
    limit: int
    offset: int


class RetryResponse(BaseModel):
    status: str
    new_task_id: str
    original_task_id: str
