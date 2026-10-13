"""Apollo.io scraper for B2B contacts."""

from typing import Optional, List, Dict, Any
import asyncio
import random

from app.scrapers.base import APIScraper


class ApolloScraper(APIScraper):
    """Scraper for Apollo.io API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        from app.config import settings
        super().__init__(
            base_url="https://api.apollo.io/v1",
            api_key=api_key or settings.APOLLO_API_KEY,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
            **kwargs,
        )
    
    async def search_people(
        self,
        person_titles: Optional[List[str]] = None,
        organization_locations: Optional[List[str]] = None,
        organization_num_employees_ranges: Optional[List[str]] = None,
        organization_industry_tag_ids: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """Search for people (contacts)."""
        payload = {
            "page": page,
            "per_page": per_page,
        }
        
        if person_titles:
            payload["person_titles"] = person_titles
        if organization_locations:
            payload["organization_locations"] = organization_locations
        if organization_num_employees_ranges:
            payload["organization_num_employees_ranges"] = organization_num_employees_ranges
        if organization_industry_tag_ids:
            payload["organization_industry_tag_ids"] = organization_industry_tag_ids
        
        return await self._request("POST", "/mixed_people/search", json=payload)
    
    async def search_organizations(
        self,
        organization_locations: Optional[List[str]] = None,
        organization_num_employees_ranges: Optional[List[str]] = None,
        organization_industry_tag_ids: Optional[List[str]] = None,
        q_organization_name: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """Search for organizations (companies)."""
        payload = {
            "page": page,
            "per_page": per_page,
        }
        
        if organization_locations:
            payload["organization_locations"] = organization_locations
        if organization_num_employees_ranges:
            payload["organization_num_employees_ranges"] = organization_num_employees_ranges
        if organization_industry_tag_ids:
            payload["organization_industry_tag_ids"] = organization_industry_tag_ids
        if q_organization_name:
            payload["q_organization_name"] = q_organization_name
        
        return await self._request("POST", "/mixed_companies/search", json=payload)
    
    async def enrich_person(self, email: str) -> Optional[Dict]:
        """Enrich person by email."""
        return await self._request("POST", "/people/match", json={"email": email})
    
    async def enrich_company(self, domain: str) -> Optional[Dict]:
        """Enrich company by domain."""
        return await self._request("POST", "/organizations/enrich", json={"domain": domain})
    
    async def search_companies_by_hiring(
        self,
        location: str = "Vietnam",
        titles: List[str] = None,
        max_pages: int = 3,
    ) -> List[Dict]:
        """Search companies that are hiring for specific titles."""
        if titles is None:
            titles = [
                "CEO", "CTO", "CFO", "COO", "Founder", "Co-founder",
                "VP Engineering", "VP Sales", "VP Marketing", "VP Operations",
                "Head of Engineering", "Head of Sales", "Head of Marketing",
                "Director", "Engineering Manager", "Sales Manager",
            ]
        
        all_results = []
        
        for page in range(1, max_pages + 1):
            try:
                result = await self.search_people(
                    person_titles=titles,
                    organization_locations=[location],
                    organization_num_employees_ranges=[
                        "11-50", "51-200", "201-500"
                    ],
                    page=page,
                    per_page=50,
                )
                
                people = result.get("people", [])
                if not people:
                    break
                
                for person in people:
                    org = person.get("organization", {})
                    if not org:
                        continue
                    
                    all_results.append({
                        "company_name": org.get("name", ""),
                        "domain": org.get("primary_domain", ""),
                        "website": org.get("website_url", ""),
                        "industry": org.get("industry", ""),
                        "employee_count": org.get("estimated_num_employees", 0),
                        "location": org.get("raw_address", ""),
                        "contact_name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                        "contact_title": person.get("title", ""),
                        "contact_email": person.get("email", ""),
                        "contact_linkedin": person.get("linkedin_url", ""),
                        "contact_phone": person.get("phone_numbers", [None])[0],
                        "source": "apollo",
                    })
                
                # Check if there are more pages
                pagination = result.get("pagination", {})
                if page >= pagination.get("total_pages", 1):
                    break
                    
            except Exception as e:
                print(f"Apollo search error page {page}: {e}")
                break
            
            await asyncio.sleep(random.uniform(2, 4))
        
        # Deduplicate by company
        seen = set()
        unique = []
        for r in all_results:
            key = r["domain"] or r["company_name"]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return unique
    
    async def get_company_details(self, domain: str) -> Optional[Dict]:
        """Get company details by domain."""
        result = await self.enrich_company(domain)
        if not result or "organization" not in result:
            return None
        
        org = result["organization"]
        return {
            "company_name": org.get("name", ""),
            "domain": org.get("primary_domain", ""),
            "website": org.get("website_url", ""),
            "industry": org.get("industry", ""),
            "employee_count": org.get("estimated_num_employees", 0),
            "location": org.get("raw_address", ""),
            "technologies": org.get("technologies", []),
            "funding": org.get("funding", {}),
            "source": "apollo",
        }
    
    async def search_companies_by_hiring(
        self,
        location: str = "Vietnam",
        titles: List[str] = None,
        max_pages: int = 3,
        min_employees: int = 10,
        max_employees: int = 500,
    ) -> List[Dict]:
        """Search companies with hiring signals."""
        if titles is None:
            titles = [
                "CEO", "CTO", "Founder", "Head of", "Director",
                "VP Engineering", "VP Sales", "VP Marketing",
                "Engineering Manager", "Sales Manager",
            ]
        
        employee_ranges = []
        if min_employees <= 50:
            employee_ranges.append("11-50")
        if min_employees <= 200 and max_employees >= 51:
            employee_ranges.append("51-200")
        if max_employees >= 201:
            employee_ranges.append("201-500")
        
        return await self.search_companies_by_hiring(
            location=location,
            titles=titles,
            max_pages=max_pages,
        )