"""Celery workers used by the API and Docker Compose."""

import asyncio
from celery import Celery
from app.config import settings

celery_app = Celery(
    "b2b_sales",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="b2b_sales.run_scraping")
def run_scraping(job_id: str):
    """Execute a queued scraper and persist its final status in Redis."""
    from app.scrapers.scheduler import ScraperScheduler, JobStatus

    scheduler = ScraperScheduler()
    job = scheduler.get_job(job_id)
    if job is None or job["status"] == JobStatus.CANCELLED:
        return
    scheduler.jobs[job_id] = job
    runners = {
        "yellowpages": scheduler._run_yellowpages_job,
        "vietnamworks": scheduler._run_vietnamworks_job,
        "apollo": scheduler._run_apollo_job,
        "signals": scheduler._run_signals_job,
    }
    asyncio.run(runners[job["type"]](job_id))
    return scheduler.get_job(job_id)
