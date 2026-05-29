from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select

from src.app.core.database import SyncSessionLocal
from src.app.models.email_task import EmailTask, EmailStatus
from src.app.tasks.celery_app import celery, bind_structlog_contextvars_for_task

logger = structlog.get_logger()


@celery.task(bind=True, name="tasks.reports.generate_monthly_report")
def generate_monthly_report(self, year: int = None, month: int = None) -> dict:
    bind_structlog_contextvars_for_task(self)

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    logger.info("monthly_report_started", year=year, month=month)

    with SyncSessionLocal() as session:
        # определяем границы месяца для фильтрации
        start_date = datetime(year, month, 1)
        end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        results = session.execute(
            select(
                EmailTask.status,
                func.count().label("count"),
            )
            .where(EmailTask.created_at >= start_date)
            .where(EmailTask.created_at < end_date)
            .group_by(EmailTask.status)
        ).all()

        report = {status.value: count for status, count in results}

    logger.info("monthly_report_completed", report=report)
    return report


@celery.task(bind=True, name="tasks.reports.hourly_stats_report")
def hourly_stats_report(self) -> dict:
    bind_structlog_contextvars_for_task(self)

    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)

    logger.info("hourly_stats_started", from_time=str(hour_ago), to_time=str(now))

    with SyncSessionLocal() as session:
        results = session.execute(
            select(
                EmailTask.status,
                func.count().label("count"),
            )
            .where(EmailTask.created_at >= hour_ago)
            .where(EmailTask.created_at < now)
            .group_by(EmailTask.status)
        ).all()

        stats = {status.value: count for status, count in results}
        total = sum(stats.values())

    logger.info(
        "hourly_stats_completed",
        total=total,
        breakdown=stats,
        period_start=str(hour_ago),
        period_end=str(now),
    )
    return {"total": total, "breakdown": stats}


@celery.task(bind=True, name="tasks.reports.nightly_cleanup")
def nightly_cleanup(self, days_old: int = 30) -> dict:
    bind_structlog_contextvars_for_task(self)

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    logger.info("nightly_cleanup_started", cutoff_date=str(cutoff_date))

    with SyncSessionLocal() as session:
        # удаляем только завершенные задачи (SENT/FAILED), чтобы не тронуть активные
        old_tasks = session.execute(
            select(EmailTask)
            .where(EmailTask.created_at < cutoff_date)
            .where(EmailTask.status.in_([EmailStatus.SENT, EmailStatus.FAILED]))
        ).scalars().all()

        deleted_count = len(old_tasks)
        for task in old_tasks:
            session.delete(task)
        session.commit()

    logger.info("nightly_cleanup_completed", deleted_count=deleted_count)
    return {"deleted_count": deleted_count, "cutoff_date": str(cutoff_date)}
