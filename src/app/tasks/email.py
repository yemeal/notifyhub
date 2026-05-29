import random

import structlog
from celery.exceptions import MaxRetriesExceededError

from src.app.core.database import SyncSessionLocal
from src.app.core.redis_client import get_redis_client
from src.app.models import EmailTask
from src.app.models.email_task import EmailStatus
from src.app.services.email_client import (
    UnreliableEmailClient,
    ServiceUnavailableError,
    ConnectionTimeoutError,
)
from src.app.tasks.celery_app import celery
from src.app.tasks.celery_app import bind_structlog_contextvars_for_task

logger = structlog.get_logger()
redis_client = get_redis_client()


# Redis гарантирует атомарность выполнения Lua-скрипта
LUA_RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def release_lock_safely(lock_key: str, lock_value: str) -> None:
    """Безопасно снимает блокировку в redis с помощью атомарного! Lua-скрипта"""

    try:
        redis_client.eval(LUA_RELEASE_LOCK, 1, lock_key, lock_value)
    except Exception as e:
        logger.error("redis_lock_release_failed", error=str(e))


# bind=True связывает экземпляр задачи с первым аргументом (self)
@celery.task(bind=True, name="tasks.send_email")
def send_email(self, email_task_id: str) -> dict | None:
    bind_structlog_contextvars_for_task(
        self,
        email_task_id=email_task_id,
    )

    # проверка ключа результата (для идемпотентности)
    result_key = f"email_task:{email_task_id}:result"
    if redis_client.exists(result_key):
        logger.info("task_already_completed_skipping")
        return {"skipped": True, "reason": "already_processed"}

    # ключ блокировки решает проблему параллельного выполнения, когда еще нет результата
    # SET NX (if not exists) гарантироует, что только один из воркеров успешно установит ключ (второй получит None)
    # TTL нужен, чтобы снимать блокировку с задачи (например при краше воркера он не сможет снять блокировку и она навсегда останется заблоченной)
    # обычно 10 минут хватает
    lock_key = f"email_task:{email_task_id}"
    # значением ключа является айди нашей залачи, чтобы при снятии блокировки мы удаляли именно свою блокировку
    lock_value = self.request.id

    is_locked = redis_client.set(lock_key, lock_value, nx=True, ex=600)

    if not is_locked:
        # блокировка уже захвачена другим воркером или предыдущей попыткой
        logger.warning("duplicate_task_execution_prevented", lock_key=lock_key)
        return {"skipped": True, "reason": "already_processed"}

    with SyncSessionLocal() as session:
        email_task = session.get(EmailTask, email_task_id)
        if not email_task:
            logger.error("email_task_not_found")
            release_lock_safely(lock_key, lock_value)
            return None

        # проверка статуса на уровне БД
        if email_task.status == EmailStatus.SENT:
            logger.info("email_already_sent_skipping")
            release_lock_safely(lock_key, lock_value)
            return {"skipped": True, "reason": "already_processed"}

        try:
            # pending / failed -> processing
            email_task.status = EmailStatus.PROCESSING
            session.commit()
            logger.info("status_updated", status="PROCESSING")

            # наш нестабильный почтовый клиент
            client = UnreliableEmailClient()
            client.send(
                recipient=email_task.recipient,
                subject=email_task.subject,
                body=email_task.body,
            )

            email_task.status = EmailStatus.SENT
            session.commit()
            logger.info("email_sent", recipient=email_task.recipient)

            # TTL 24 часа гарантирует, что вызов задачи с тем же email_task_id будет пропущен
            redis_client.set(result_key, "success", ex=86400)

            release_lock_safely(lock_key, lock_value)

        except ValueError as exc:
            # non-retriable, celery помечает как FAILED
            session.rollback()
            email_task.status = EmailStatus.FAILED
            session.commit()
            logger.error(
                "email_failed_permanently",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            release_lock_safely(lock_key, lock_value)
            raise

        except (ServiceUnavailableError, ConnectionTimeoutError) as exc:
            session.rollback()

            # формула задержки: countdown = base_delay * (2 ** attempt) + jitter
            # ретрай по экспоненте позволяет не забивать сервер одинаковым потоком запросов
            # и дает ему больше времени на восстановление
            # jitter позволяет отправлять запросы равномерно, а не все сразу в один момент, что распределяет нагрузку

            base_delay = 2
            attempt = self.request.retries
            jitter = random.uniform(0, 1)
            countdown = base_delay * (2**attempt) + jitter

            logger.warning(
                "email_failed_transiently_scheduling_retry",
                attempt_number=attempt + 1,
                error_type=type(exc).__name__,
                wait_seconds=round(countdown, 2),
            )

            # мы обязаны снять лок до ретрая потому что self.retry() выбрасывает
            # специальное исключение celery.exceptions.Retry, после которого код ниже НЕ ВЫПОЛНИТСЯ
            # когда задача запустится снова, она попытается сделать лок в редисе,
            # но наткнется на собственный неистекший ключ и решит, что является дубликатом и выйдет.
            release_lock_safely(lock_key, lock_value)

            # max_retries=5 - 6 попыток всего.
            # обязательно передаем ошибку вышу через raise
            # Celery при вызове self.retry(exc=exc) перевыбрасывает ИСХОДНОЕ исключение,
            # мы сами проверяем лимит перед ретраем.
            max_retries_limit = 5
            if attempt >= max_retries_limit:
                email_task.status = EmailStatus.FAILED
                session.commit()
                logger.error(
                    "email_failed_max_retries_exceeded", total_attempts=attempt + 1
                )

                # отправляем в dead letter queue
                from src.app.tasks.dlq import process_dead_letter

                process_dead_letter.apply_async(
                    args=[
                        {
                            "original_task_id": self.request.id,
                            "task_name": "tasks.send_email",
                            "args": [email_task_id],
                            "kwargs": {},
                            "error_message": str(exc),
                            "failure_count": attempt + 1,
                        }
                    ],
                    queue="notifications.dlq",
                )

                raise exc

            raise self.retry(
                exc=exc, countdown=countdown, max_retries=max_retries_limit
            )


@celery.task(bind=True, name="tasks.email.send_otp")
def send_otp(self, user_id: str, otp_code: str) -> dict:
    bind_structlog_contextvars_for_task(self, user_id=user_id)

    logger.info("send_otp_started", user_id=user_id)

    # в реальности тут отправка через SMS/Email провайдер
    import time
    time.sleep(0.5)

    logger.info("send_otp_completed", user_id=user_id, otp_code=otp_code)
    return {"user_id": user_id, "otp_code": otp_code, "status": "sent"}

