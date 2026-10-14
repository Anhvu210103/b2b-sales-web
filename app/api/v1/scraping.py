"""Scraping API routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_active_user, require_role
from app.models.lead import Lead, LeadSource
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post("/yellowpages")
async def scrape_yellowpages(
    background_tasks: BackgroundTasks,
    keywords: List[str] = ["B2B", "software", "marketing", "logistics"],
    pages_per_keyword: int = 2,
    max_details: int = 12,
    location: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger YellowPages scraping."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    job_id = await scheduler.schedule_yellowpages_scraping(
        keywords=keywords,
        pages_per_keyword=pages_per_keyword,
        max_details=max_details,
        location=location,
    )
    
    return {
        "message": "YellowPages scraping scheduled",
        "job_id": job_id,
        "status": "scheduled",
    }


@router.post("/vietnamworks")
async def scrape_vietnamworks(
    background_tasks: BackgroundTasks,
    keywords: List[str] = ["B2B", "software", "marketing", "sales"],
    pages: int = 2,
    max_details: int = 12,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger VietnamWorks scraping."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    job_id = await scheduler.schedule_vietnamworks_scraping(
        keywords=keywords,
        pages=pages,
        max_details=max_details,
    )
    
    return {
        "message": "VietnamWorks scraping scheduled",
        "job_id": job_id,
        "status": "scheduled",
    }


@router.post("/apollo")
async def scrape_apollo(
    background_tasks: BackgroundTasks,
    location: str = "Hanoi",
    titles: List[str] = ["CEO", "CTO", "Founder", "Head of", "Director"],
    max_pages: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger Apollo.io scraping."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    job_id = await scheduler.schedule_apollo_scraping(
        location=location,
        titles=titles,
        max_pages=max_pages,
    )
    
    return {
        "message": "Apollo.io scraping scheduled",
        "job_id": job_id,
        "status": "scheduled",
    }


@router.post("/signals")
async def scrape_signals(
    background_tasks: BackgroundTasks,
    sources: List[str] = ["news", "associations", "portfolios"],
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger signals scraping (news, associations, portfolios)."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    job_id = await scheduler.schedule_signals_scraping(
        sources=sources,
        days=days,
    )
    
    return {
        "message": "Signals scraping scheduled",
        "job_id": job_id,
        "status": "scheduled",
    }


@router.get("/jobs")
async def list_scraping_jobs(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List scraping jobs."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    jobs = scheduler.get_jobs(status=status)
    
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_scraping_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get scraping job details."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    job = scheduler.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_scraping_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Cancel a scraping job."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    await scheduler.cancel_job(job_id)
    
    return {"message": "Job cancelled"}


@router.get("/stats")
async def get_scraping_stats(
    current_user: User = Depends(get_current_active_user),
):
    """Get scraping statistics."""
    from app.scrapers.scheduler import ScraperScheduler
    
    scheduler = ScraperScheduler()
    stats = await scheduler.get_stats()
    
    return stats


@router.post("/enrich/{lead_id}")
async def enrich_lead_manual(
    lead_id: str,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Manually enrich a lead."""
    from app.services.lead_service import LeadService
    
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    service = LeadService(db)
    enriched = await service.enrich_lead(lead, force_refresh=True)
    
    return {
        "message": "Lead enriched successfully",
        "enrichment_data": lead.enrichment_data,
    }