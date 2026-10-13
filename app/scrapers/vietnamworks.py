"""VietnamWorks scraper for job postings (company signals)."""

from typing import Optional, List, Dict, Any
from playwright.async_api import Page
import re
import json
from urllib.parse import quote

from app.scrapers.base import BaseScraper, ScrapedCompany


class VietnamWorksScraper(BaseScraper):
    """Scraper for VietnamWorks.com - job postings as hiring signals."""
    
    BASE_URL = "https://www.vietnamworks.com"
    API_URL = "https://ms.vietnamworks.com/job-search/v1.0/search"
    
    async def search(
        self,
        query: str,
        max_pages: int = 2,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search for job postings (companies hiring)."""
        results = []
        
        for page in range(1, max_pages + 1):
            # Use API
            payload = {
                "query": query,
                "page": page,
                "size": 20,
                "sortBy": "relevance",
            }
            
            try:
                async with self.session.post(self.API_URL, json=payload) as resp:
                    if resp.status != 200:
                        break
                    data = await resp.json()
            except Exception as e:
                print(f"API error: {e}")
                break
            
            jobs = data.get("data", [])
            if not jobs:
                break
            
            for job in jobs:
                company = job.get("companyName", "")
                if not company:
                    continue
                
                results.append({
                    "company_name": company,
                    "job_title": job.get("jobTitle", ""),
                    "company_id": job.get("companyId", ""),
                    "job_url": f"{self.BASE_URL}/vieclam/{job.get('jobId', '')}",
                    "source": "vietnamworks",
                    "job_description": job.get("description", "")[:500],
                    "salary": job.get("salary", ""),
                    "location": job.get("workingLocations", [{}])[0].get("cityNameVI", ""),
                    "posted_date": job.get("onlineOn", ""),
                })
            
            # Small delay between pages
            import asyncio
            await asyncio.sleep(random.uniform(1, 2))
        
        return results
    
    async def search_companies_by_hiring(
        self,
        keywords: List[str] = None,
        max_pages: int = 2,
        min_open_roles: int = 2,
    ) -> List[Dict[str, Any]]:
        """Search companies by hiring signals."""
        if keywords is None:
            keywords = [
                "Business Development", "Sales Manager", "Project Manager",
                "Operations Manager", "Marketing Manager", "HR Manager",
                "Technical Lead", "Engineering Manager", "Product Manager",
                "Account Manager", "Customer Success", "Business Analyst",
            ]
        
        all_companies = {}
        
        for keyword in keywords:
            results = await self.search(keyword, max_pages=max_pages)
            
            for job in results:
                company_name = job["company_name"]
                if company_name not in all_companies:
                    all_companies[company_name] = {
                        "company_name": company_name,
                        "open_roles": [],
                        "job_urls": [],
                        "source": "vietnamworks",
                        "hiring_signals": True,
                    }
                
                all_companies[company_name]["open_roles"].append(job["job_title"])
                all_companies[company_name]["job_urls"].append(job["job_url"])
        
        # Filter by minimum open roles
        filtered = [
            c for c in all_companies.values()
            if len(c["open_roles"]) >= min_open_roles
        ]
        
        # Sort by number of open roles
        filtered.sort(key=lambda x: len(x["open_roles"]), reverse=True)
        
        return filtered
    
    async def get_company_details(self, url: str) -> Optional[Any]:
        """Get company details from VietnamWorks company page."""
        # Company page format: https://www.vietnamworks.com/company/{company-id}
        # This would need company ID, not just URL
        return None