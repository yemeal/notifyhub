import structlog

from src.app.tasks.celery_app import celery, bind_structlog_contextvars_for_task
from src.app.core.database import SyncSessionLocal
from src.app.models.failed_task import FailedTask

logger = structlog.get_logger()


@celery.task(
    bind=True,
    name="tasks.process_dead_letter",
    queue="notifications.dlq",
)
def process_dead_letter(self, message_data: dict) -> dict:
    bind_structlog_contextvars_for_task(self)

    try:
        with SyncSessionLocal() as session:
            # проверяем, не обработано ли уже
            existing = (
                session.query(FailedTask)
                .filter_by(original_task_id=message_data.get("original_task_id"))
                .first()
            )

            # если обработано, увеличиваем счетчик
            if existing:
                existing.failure_count += 1
                existing.error_message = message_data.get("error_message")
                session.commit()
                logger.warning(
                    "dlq_duplicate_updated",
                    original_task_id=message_data.get("original_task_id"),
                    failure_count=existing.failure_count,
                )
                return {"status": "updated", "id": str(existing.id)}

            failed_task = FailedTask(
                original_task_id=message_data.get("original_task_id", "unknown"),
                task_name=message_data.get("task_name", "unknown"),
                args=message_data.get("args"),
                kwargs=message_data.get("kwargs"),
                error_message=message_data.get("error_message"),
                failure_count=message_data.get("failure_count", 1),
            )
            session.add(failed_task)
            session.commit()

            # алерт
            logger.error(
                "dead_letter_received",
                original_task_id=failed_task.original_task_id,
                task_name=failed_task.task_name,
                error_message=failed_task.error_message,
                failed_task_id=str(failed_task.id),
            )

            # мок слак уведа
            _notify_slack_mock(failed_task)

            return {"status": "saved", "id": str(failed_task.id)}

    except Exception as exc:
        # dlq-воркер НИКОГДА не должен падать
        logger.critical(
            "dlq_worker_error",
            error=str(exc),
            message_data=message_data,
        )
        return {"status": "error", "error": str(exc)}


def _notify_slack_mock(failed_task: FailedTask) -> None:
    logger.info(
        "slack_notification_sent_mock",
        channel="#alerts",
        message=f"Dead letter: {failed_task.task_name} "
        f"(task_id={failed_task.original_task_id}) — "
        f"{failed_task.error_message}",
    )
