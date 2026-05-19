import time

import structlog

from src.app.tasks.celery_app import celery

logger = structlog.get_logger()


@celery.task(bind=True)  # bind=True даёт доступ к self.request
def send_email(self, user_ids: list[int]) -> None:

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=self.request.id,
        worker_name=self.request.hostname,
    )

    for user_id in user_ids:
        logger.info("sending_email", user_id=user_id)
        time.sleep(10)
        logger.info("email_sent", user_id=user_id)


def send_email_task(user_ids: list[int]) -> None:
    send_email.apply_async(args=[user_ids])
