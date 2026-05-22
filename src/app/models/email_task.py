import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base, UuidMixin, TimestampMixin


class EmailStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class EmailTask(Base, UuidMixin, TimestampMixin):
    recipient: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str]
    status: Mapped[EmailStatus] = mapped_column(SAEnum(EmailStatus))
    task_id: Mapped[str | None] = mapped_column(default=None)
