import time
import structlog
from src.app.tasks.celery_app import celery
from src.app.core.database import SyncSessionLocal
from src.app.models.analytics_event import AnalyticsEvent

logger = structlog.get_logger()


def check_routing_key_match(task_instance, expected_routing_key: str) -> bool:
    routing_key = task_instance.request.delivery_info.get("routing_key")
    return routing_key == expected_routing_key


@celery.task(bind=True, name="src.app.tasks.broadcast.send_welcome_email")
def send_welcome_email(self, user_id: str, email: str, name: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
        user_id=user_id,
        request_id=self.request.headers.get("X-Request-Id"),
    )

    if not check_routing_key_match(self, "user.email"):
        logger.info("routing_key_mismatch_skipping_task")
        return

    logger.info("send_welcome_email_started", email=email, name=name)
    time.sleep(1)
    logger.info("send_welcome_email_completed", email=email)


@celery.task(bind=True, name="src.app.tasks.broadcast.log_user_registration")
def log_user_registration(self, user_id: str, email: str, name: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
        user_id=user_id,
        request_id=self.request.headers.get("X-Request-Id"),
    )

    if not check_routing_key_match(self, "user.analytics"):
        logger.info("routing_key_mismatch_skipping_task")
        return

    logger.info("log_user_registration_started")
    with SyncSessionLocal() as session:
        analytics_event = AnalyticsEvent(
            event_type="user_registered",
            payload={"user_id": user_id, "email": email, "name": name},
        )
        session.add(analytics_event)
        session.commit()
        logger.info("log_user_registration_db_saved", event_id=str(analytics_event.id))
    logger.info("log_user_registration_completed")


@celery.task(bind=True, name="src.app.tasks.broadcast.notify_slack_team")
def notify_slack_team(self, user_id: str, email: str, name: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
        user_id=user_id,
        request_id=self.request.headers.get("X-Request-Id"),
    )

    if not check_routing_key_match(self, "user.slack"):
        logger.info("routing_key_mismatch_skipping_task")
        return

    logger.info("notify_slack_team_started")
    logger.error("notify_slack_team_failed_deliberately")
    raise ValueError("Deliberate error in Slack notification task")


@celery.task(bind=True, name="tasks.broadcast.send_bulk_promo")
def send_bulk_promo(self, recipients: list[str], subject: str, body: str) -> dict:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
        request_id=self.request.headers.get("X-Request-Id"),
    )

    logger.info("send_bulk_promo_started", recipient_count=len(recipients))

    sent_count = 0
    for recipient in recipients:
        # имитация отправки, в реальности тут будет SMTP/API вызов
        time.sleep(0.2)
        sent_count += 1
        logger.info("bulk_promo_sent_to", recipient=recipient, progress=f"{sent_count}/{len(recipients)}")

    logger.info("send_bulk_promo_completed", sent_count=sent_count)
    return {"sent_count": sent_count, "total": len(recipients)}

