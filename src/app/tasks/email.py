import time

import structlog

from src.app.core.database import SyncSessionLocal
from src.app.models import EmailTask
from src.app.models.email_task import EmailStatus
from src.app.tasks.celery_app import celery

logger = structlog.get_logger()


@celery.task(bind=True, name="tasks.send_email")  # bind=True даёт доступ к self.request
def send_email(self, email_task_id: str) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
        email_task_id=email_task_id,
        request_id=self.request.headers.get("X-Request-Id"),
    )

    with SyncSessionLocal() as session:
        email_task = session.get(EmailTask, email_task_id)
        if not email_task:
            logger.error("email_task_not_found")
            return

        try:
            # pending -> processing
            email_task.status = EmailStatus.PROCESSING
            session.commit()
            logger.info("status_updated", status="PROCESSING")

            logger.info("sending_email", recipient=email_task.recipient)
            time.sleep(5)

            # processing -> sent
            email_task.status = EmailStatus.SENT
            session.commit()
            logger.info("email_sent", recipient=email_task.recipient)

        except Exception as exc:
            session.rollback()
            email_task.status = EmailStatus.FAILED
            session.commit()
            logger.error("email_failed", error=str(exc))
            raise
