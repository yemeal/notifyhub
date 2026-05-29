from celery import Celery
from celery.schedules import crontab
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
        "src.app.tasks.dlq",
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

notifications_dead_letter_exchange = Exchange("notifications.dlx", type="topic")

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
        exchange=notifications_exchange,  # основной exchange
        routing_key="notifications.email.#",
        queue_arguments={
            "x-dead-letter-exchange": "notifications.dlx",  # куда отправляем мертвые
            "x-dead-letter-routing-key": "notifications.dlq.emails",  # с каким ключом роутинга
            "x-message-ttl": 86400000,  # сколько будет жить мервтое сообщение
        },
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
    Queue(
        "notifications.dlq",
        exchange=notifications_dead_letter_exchange,
        routing_key="notifications.dlq.#",
    ),
    # Task Routing: отдельные очереди под разные типы задач
    # x-max-priority включает приоритетную обработку внутри очереди
    # без этого аргумента rabbitmq обрабатывает строго FIFO
    # 10 уровней более чем достаточно, больше - лишний расход памяти в rabbitmq
    Queue(
        "notifications.critical",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue("notifications.bulk"),
    Queue("reports.heavy"),
)

# task_routes определяет в какую очередь попадет задача по ее имени
# это работает автоматически - не нужно указывать queue= при вызове .delay() или .apply_async()
# приоритет: apply_async(queue=...) > task_routes > task_default_queue ("celery")
celery.conf.task_routes = {
    "tasks.email.send_otp": {"queue": "notifications.critical"},
    "tasks.broadcast.send_bulk_promo": {"queue": "notifications.bulk"},
    "tasks.reports.generate_monthly_report": {"queue": "reports.heavy"},
    "tasks.reports.hourly_stats_report": {"queue": "reports.heavy"},
    "tasks.reports.nightly_cleanup": {"queue": "reports.heavy"},
}

# beat - отдельный процесс-планировщик, он только ставит задачи в очередь по расписанию
# выполняет их воркер, не beat
# ВАЖНО: beat должен быть запущен в одном экземпляре, иначе задачи будут дублироваться
celery.conf.beat_schedule = {
    # каждый час ровно в :00 - агрегирует статистику за последний час
    "hourly-stats-report": {
        "task": "tasks.reports.hourly_stats_report",
        "schedule": crontab(minute=0),
    },
    # каждую ночь в 03:00 - удаляет старые записи из email_tasks
    "nightly-cleanup": {
        "task": "tasks.reports.nightly_cleanup",
        "schedule": crontab(hour=3, minute=0),
    },
}

# без этого воркер "захватывает" несколько сообщений вперед (prefetch)
# и задача с высоким приоритетом будет ждать, пока воркер не обработает захваченные
# prefetch_multiplier=1 значит "бери по одной задаче за раз"
celery.conf.worker_prefetch_multiplier = 1


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
