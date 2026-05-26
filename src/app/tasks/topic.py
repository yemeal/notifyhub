import time
import re
import structlog

from src.app.tasks.celery_app import celery
from src.app.tasks.celery_app import bind_structlog_contextvars_for_task

logger = structlog.get_logger()


def amqp_match(pattern: str, routing_key: str) -> bool:
    # конвертация AMQP паттерна в регулярку
    regex_parts: list[str] = []
    for part in pattern.split("."):
        if part == "*":
            regex_parts.append(r"[^.]+")
        elif part == "#":
            regex_parts.append(r".*")
        else:
            regex_parts.append(re.escape(part))

    regex_str = "^" + r"\.".join(regex_parts) + "$"

    # если заканчивается на .# чтобы корректно отработать например sms.normal.# -> sms.normal
    if pattern.endswith(".#"):
        base_pattern = pattern[:-2]
        base_parts: list[str] = []
        for part in base_pattern.split("."):
            if part == "*":
                base_parts.append(r"[^.]+")
            elif part == "#":
                base_parts.append(r".*")
            else:
                base_parts.append(re.escape(part))
        regex_str = "^" + r"\.".join(base_parts) + r"(?:\..*)?$"

    return bool(re.match(regex_str, routing_key))


def resolve_queues_for_routing_key(exchange_name: str, routing_key: str) -> list[str]:
    matched_queues = []
    for queue in celery.conf.task_queues:
        if queue.exchange and queue.exchange.name == exchange_name:
            if amqp_match(queue.routing_key, routing_key):
                matched_queues.append(queue.name)
    return matched_queues


@celery.task(bind=True, name="tasks.send_email_notification")
def send_email_notification(
    self,
    notification_id: str,
    priority: str,
    recipient: str,
    message: str,
) -> None:
    bind_structlog_contextvars_for_task(self, notification_id=notification_id)

    routing_key = self.request.delivery_info.get("routing_key", "")
    queues = resolve_queues_for_routing_key("notifications", routing_key)

    logger.info(
        "send_email_notification_started",
        priority=priority,
        recipient=recipient,
        message=message,
        routing_key=routing_key,
        matched_queues=queues,
    )

    time.sleep(10) if priority == "critical" else time.sleep(100)
    logger.info("send_email_notification_completed", recipient=recipient)


@celery.task(bind=True, name="tasks.send_sms_notification")
def send_sms_notification(
    self,
    notification_id: str,
    priority: str,
    recipient: str,
    message: str,
) -> None:
    bind_structlog_contextvars_for_task(self, notification_id=notification_id)

    routing_key = self.request.delivery_info.get("routing_key", "")
    queues = resolve_queues_for_routing_key("notifications", routing_key)

    logger.info(
        "send_sms_notification_started",
        priority=priority,
        recipient=recipient,
        message=message,
        routing_key=routing_key,
        matched_queues=queues,
    )

    time.sleep(10) if priority == "critical" else time.sleep(100)
    logger.info("send_sms_notification_completed", recipient=recipient)
