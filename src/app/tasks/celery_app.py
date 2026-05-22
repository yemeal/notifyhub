from celery import Celery
from kombu import Exchange, Queue

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

# Создаем обменник user events типа фанаут
# Fanout как раз и позволяет всем очередям получать копию сообщдения
user_events_exchange = Exchange("user_events", type="fanout")

# создаем очереди с выше созданному обменнику и ключом маршрутизации
celery.conf.task_queues = (
    Queue(
        "user.email",
        exchange=user_events_exchange,
        routing_key="user.email",
    ),
    Queue(
        "user.analytics",
        exchange=user_events_exchange,
        routing_key="user.analytics",
    ),
    Queue(
        "user.slack",
        exchange=user_events_exchange,
        routing_key="user.slack",
    ),
)
