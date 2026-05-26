from celery import Celery
from kombu import Exchange, Queue
import structlog

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
        "src.app.tasks.topic",
    ],
)

# Создаем обменник user events типа фанаут
# Fanout как раз и позволяет всем очередям получать копию сообщдения
# pub/sub для всех подписчиков без исключения и без фильтрации (игнорим routing_key)
user_events_exchange = Exchange("user_events", type="fanout")

# создаем обменник типа топик, для того, чтобы реализовать
# pub/sub, где подписчики выбирают какие подкатегории получать (гибкая фильтрация на стороне брокера)
# (через маски `* - only one` и `# - zero or more`)
notifications_exchange = Exchange("notifications", type="topic")

# создаем очереди с выше созданными обменниками и ключом маршрутизации
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
    # все critical, где ключ состоит из трех слов
    Queue(
        "queue_all_critical",
        exchange=notifications_exchange,
        routing_key="*.*.critical",
    ),
    # все email, вне зависимости от приоритета
    Queue(
        "queue_email_all",
        exchange=notifications_exchange,
        routing_key="notifications.email.#",
    ),
    # смс только с нормал приорити
    Queue(
        "queue_sms_normal",
        exchange=notifications_exchange,
        routing_key="notifications.sms.normal",
    ),
    # ВАЖНО: если мы задаем кастомные очереди, селери перстает слушать деволтную очередь "celery",
    # в которую попадают задачи без кастомного exchange (если ее не добавить, воркер не увидит эти задачи)
    Queue("celery"),
)


def bind_structlog_contextvars_for_task(
    task_instance: Celery,
    **kwargs,
) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=task_instance.request.id,
        worker_name=task_instance.request.hostname,
        request_id=task_instance.request.headers.get("X-Request-Id"),
        **kwargs,
    )
