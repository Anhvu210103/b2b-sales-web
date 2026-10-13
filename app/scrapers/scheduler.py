"""Scraper scheduler - manages scraping jobs."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
import asyncio

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead, LeadSource
from app.scrapers.yellowpages import YellowPagesScraper
from app.scrapers.vietnamworks import VietnamWorksScraper
from app.scrapers.apollo import ApolloScraper
from app.scrapers.signals import SignalsScraper
from app.services.lead_service import LeadService


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScraperScheduler:
    """Manages scraping jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
        self._running = False
    
    # ==================== YellowPages ====================
    
    async def schedule_yellowpages_scraping(
        self,
        keywords: List[str] = None,
        pages_per_keyword: int = 2,
        max_details: int = 12,
        location: str = "all",
    ) -> str:
        """Schedule YellowPages scraping job."""
        if keywords is None:
            keywords = [
                "B2B", "software", "marketing", "logistics", "manufacturing",
                "construction", "wholesale", "retail", "technology", "consulting",
            ]
        
        job_id = str(uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "type": "yellowpages",
            "status": JobStatus.PENDING,
            "params": {
                "keywords": keywords,
                "pages_per_keyword": pages_per_keyword,
                "max_details": max_details,
                "location": location,
            },
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        
        # Run in background
        asyncio.create_task(self._run_yellowpages_job(job_id))
        
        return job_id
    
    async def _run_yellowpages_job(self, job_id: str):
        job = self.jobs[job_id]
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.utcnow()
        
        try:
            async with YellowPagesScraper() as scraper:
                companies = await scraper.search_companies(
                    keywords=job["params"]["keywords"],
                    max_pages=job["params"]["pages_per_keyword"],
                    max_details=job["params"]["max_details"],
                )
            
            job["status"] = JobStatus.COMPLETED
            job["result"] = {
                "companies_found": len(companies),
                "companies": [
                    {
                        "company_name": c.company_name,
                        "domain": c.domain,
                        "website": c.website,
                        "email": c.email,
                        "phone": c.phone,
                        "address": c.address,
                        "city": c.city,
                        "industry": c.industry,
                    }
                    for c in companies
                ],
            }
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error"] = str(e)
        finally:
            job["completed_at"] = datetime.utcnow()
    
    # ==================== VietnamWorks ====================
    
    async def schedule_vietnamworks_scraping(
        self,
        keywords: List[str] = None,
        pages: int = 2,
        max_details: int = 12,
    ) -> str:
        """Schedule VietnamWorks scraping job."""
        if keywords is None:
            keywords = [
                "Business Development", "Sales Manager", "Project Manager",
                "Operations Manager", "Marketing Manager", "HR Manager",
                "Technical Lead", "Engineering Manager", "Product Manager",
                "Account Manager", "Customer Success", "Business Analyst",
            ]
        
        job_id = str(uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "type": "vietnamworks",
            "status": JobStatus.PENDING,
            "params": {
                "keywords": keywords,
                "pages": pages,
                "max_details": max_details,
            },
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        
        asyncio.create_task(self._run_vietnamworks_job(job_id))
        return job_id
    
    async def _run_vietnamworks_job(self, job_id: str):
        job = self.jobs[job_id]
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.utcnow()
        
        try:
            async with VietnamWorksScraper() as scraper:
                companies = await scraper.search_companies_by_hiring(
                    keywords=job["params"]["keywords"],
                    max_pages=job["params"]["pages"],
                    min_open_roles=2,
                )
            
            job["status"] = JobStatus.COMPLETED
            job["result"] = {
                "companies_found": len(companies),
                "companies": companies,
            }
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error"] = str(e)
        finally:
            job["completed_at"] = datetime.utcnow()
    
    # ==================== Apollo ====================
    
    async def schedule_apollo_scraping(
        self,
        location: str = "Vietnam",
        titles: List[str] = None,
        max_pages: int = 3,
    ) -> str:
        """Schedule Apollo.io scraping job."""
        job_id = str(uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "type": "apollo",
            "status": JobStatus.PENDING,
            "params": {
                "location": location,
                "titles": titles,
                "max_pages": max_pages,
            },
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        
        asyncio.create_task(self._run_apollo_job(job_id))
        return job_id
    
    async def _run_apollo_job(self, job_id: str):
        job = self.jobs[job_id]
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.utcnow()
        
        try:
            async with ApolloScraper() as scraper:
                companies = await scraper.search_companies_by_hiring(
                    location=job["params"]["location"],
                    titles=job["params"]["titles"],
                    max_pages=job["params"]["max_pages"],
                )
            
            job["status"] = JobStatus.COMPLETED
            job["result"] = {
                "companies_found": len(companies),
                "companies": companies,
            }
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error"] = str(e)
        finally:
            job["completed_at"] = datetime.utcnow()
    
    # ==================== Signals ====================
    
    async def schedule_signals_scraping(
        self,
        sources: List[str] = None,
        days: int = 30,
    ) -> str:
        """Schedule signals scraping (news, associations, portfolios)."""
        if sources is None:
            sources = ["news", "associations", "portfolios"]
        
        job_id = str(uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "type": "signals",
            "status": JobStatus.PENDING,
            "params": {
                "sources": sources,
                "days": days,
            },
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        
        asyncio.create_task(self._run_signals_job(job_id))
        return job_id
    
    async def _run_signals_job(self, job_id: str):
        job = self.jobs[job_id]
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.utcnow()
        
        try:
            async with SignalsScraper() as scraper:
                all_results = []
                
                if "news" in job["params"]["sources"]:
                    news = await scraper.scrape_news_signals(days=job["params"]["days"])
                    all_results.extend(news)
                
                if "associations" in job["params"]["sources"]:
                    associations = await scraper.scrape_associations()
                    all_results.extend([{
                        "company_name": c.company_name,
                        "domain": c.domain,
                        "website": c.website,
                        "source": c.source,
                        "source_url": c.source_url,
                    } for c in associations])
                
                if "portfolios" in job["params"]["sources"]:
                    portfolios = await scraper.scrape_portfolios()
                    all_results.extend([{
                        "company_name": c.company_name,
                        "domain": c.domain,
                        "website": c.website,
                        "source": c.source,
                        "source_url": c.source_url,
                    } for c in portfolios])
            
            job["status"] = JobStatus.COMPLETED
            job["result"] = {
                "signals_found": len(all_results),
                "signals": all_results,
            }
        except Exception as e:
            job["status"] = JobStatus.FAILED
            job["error"] = str(e)
        finally:
            job["completed_at"] = datetime.utcnow()
    
    # ==================== Job Management ====================
    
    def get_jobs(self, status: Optional[str] = None) -> List[Dict]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return sorted(jobs, key=lambda x: x["created_at"], reverse=True)
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending/running job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job["status"] in (JobStatus.PENDING, JobStatus.RUNNING):
            job["status"] = JobStatus.CANCELLED
            job["completed_at"] = datetime.utcnow()
            return True
        return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total = len(self.jobs)
        by_status = {}
        by_type = {}
        
        for job in self.jobs.values():
            by_status[job["status"]] = by_status.get(job["status"], 0) + 1
            by_type[job["type"]] = by_type.get(job["type"], 0) + 1
        
        return {
            "total_jobs": total,
            "by_status": by_status,
            "by_type": by_type,
            "running": by_status.get(JobStatus.RUNNING, 0),
        }
    
    # ==================== Lead Integration ====================
    
    async def save_scraped_leads(
        self,
        db: AsyncSession,
        scraped_data: List[Dict],
        source: LeadSource,
        assigned_to: Optional[UUID] = None,
    ) -> Dict[str, int]:
        """Save scraped companies as leads."""
        service = LeadService(db)
        created = 0
        updated = 0
        skipped = 0
        
        for data in scraped_data:
            try:
                # Check if lead exists by domain or company name
                domain = data.get("domain") or data.get("domain")
                company_name = data.get("company_name")
                
                existing = None
                if domain:
                    result = await db.execute(
                        select(Lead).where(Lead.domain == domain)
                    )
                    existing = result.scalar_one_or_none()
                
                if not existing and company_name:
                    result = await db.execute(
                        select(Lead).where(Lead.company_name.ilike(company_name))
                    )
                    existing = result.scalar_one_or_none()
                
                lead_data = {
                    "company_name": data.get("company_name", ""),
                    "domain": data.get("domain"),
                    "website": data.get("website"),
                    "email": data.get("email"),
                    "phone": data.get("phone"),
                    "address": data.get("address"),
                    "city": data.get("city"),
                    "industry": data.get("industry"),
                    "source": LeadSource(source),
                    "source_url": data.get("source_url"),
                    "enrichment_data": {
                        "raw_scraped": data,
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                }
                
                if existing:
                    # Update
                    for key, value in {
                        "email": data.get("email"),
                        "phone": data.get("phone"),
                        "website": data.get("website"),
                        "address": data.get("address"),
                        "enrichment_data": {
                            "raw_scraped": data,
                            "scraped_at": datetime.utcnow().isoformat(),
                        },
                    }.items():
                        setattr(existing, key, value)
                    updated += 1
                else:
                    lead = Lead(**lead_data)
                    if assigned_to:
                        existing.assigned_to = assigned_to
                    db.add(lead)
                    created += 1
                    
            except Exception as e:
                skipped += 1
                print(f"Error saving lead: {e}")
        
        # Note: caller should commit
        return {"created": created, "updated": updated, "skipped": skipped}