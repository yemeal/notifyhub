from celery import Celery

from src.app.core.logging import setup_logging
from src.app.core.settings import get_settings

settings = get_settings()

# настраиваем логгинг и для воркера тоже
# потому что воркер и апи - это два разных процесса, у каждого своя память
# воркер не запускает main.py
setup_logging(json_logs=not settings.DEBUG, log_level="INFO")

celery = Celery(
    "src.app.tasks.celery_app",
    broker=settings.BROKER_URL,
    backend=settings.RESULT_BACKEND,
    broker_connection_retry_on_start=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    include=[
        "src.app.tasks.broadcast",
        "src.app.tasks.email",
        "src.app.tasks.reports",
    ],
)
