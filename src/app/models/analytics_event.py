from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base, UuidMixin, TimestampMixin


class AnalyticsEvent(Base, UuidMixin, TimestampMixin):
    event_type: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB)
