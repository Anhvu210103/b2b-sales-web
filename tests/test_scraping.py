"""Exercise shared job state and execution without contacting external sites."""

import asyncio
from uuid import uuid4

from app.core.celery_app import run_scraping
from app.scrapers.scheduler import ScraperScheduler, JobStatus


def test_jobs_survive_scheduler_instances(monkeypatch):
    queued = []
    monkeypatch.setattr(run_scraping, "apply_async", lambda **kwargs: queued.append(kwargs))
    scheduler = ScraperScheduler()
    job_id = asyncio.run(scheduler.schedule_signals_scraping(sources=["news"]))
    try:
        assert queued == [{"args": [job_id], "task_id": job_id}]
        other = ScraperScheduler()
        assert other.get_job(job_id)["status"] == JobStatus.PENDING
        assert any(job["id"] == job_id for job in other.get_jobs("pending"))
        monkeypatch.setattr("app.core.celery_app.celery_app.control.revoke", lambda *a, **k: None)
        assert asyncio.run(other.cancel_job(job_id))
        assert scheduler.get_job(job_id)["status"] == JobStatus.CANCELLED
        assert run_scraping.run(job_id) is None
    finally:
        scheduler.store.delete("b2b:scraping:job:" + job_id)
        scheduler.store.srem("b2b:scraping:jobs", job_id)


def test_worker_persists_results(monkeypatch):
    class Scraper:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def scrape_news_signals(self, days):
            return [{"company_name": "Worker Company", "days": days}]

    monkeypatch.setattr("app.scrapers.scheduler.SignalsScraper", Scraper)
    scheduler = ScraperScheduler()
    job_id = str(uuid4())
    scheduler._persist({
        "id": job_id, "type": "signals", "status": "pending",
        "params": {"sources": ["news"], "days": 7}, "created_at": "2026-01-01",
    })
    try:
        result = run_scraping.run(job_id)
        assert result["status"] == JobStatus.COMPLETED
        assert result["result"]["signals"] == [{"company_name": "Worker Company", "days": 7}]
        assert ScraperScheduler().get_job(job_id)["result"]["signals_found"] == 1
    finally:
        scheduler.store.delete("b2b:scraping:job:" + job_id)
        scheduler.store.srem("b2b:scraping:jobs", job_id)
