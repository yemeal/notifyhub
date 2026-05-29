import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.app.models.base import Base, UuidMixin, TimestampMixin


class FailedTask(Base, UuidMixin, TimestampMixin):

    original_task_id: Mapped[str] = mapped_column(String(255))
    task_name: Mapped[str] = mapped_column(String(255))
    args: Mapped[dict | None] = mapped_column(JSONB, default=None)
    kwargs: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    failure_count: Mapped[int] = mapped_column(Integer, default=1)
    last_retry_at: Mapped[datetime | None] = mapped_column(server_default=func.now())
