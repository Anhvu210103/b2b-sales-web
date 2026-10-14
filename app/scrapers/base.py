"""Base scraper class."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import random

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import aiohttp
from app.config import settings


@dataclass
class ScrapedCompany:
    """Scraped company data."""
    company_name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    contacts: List[Dict[str, Any]] = None
    source: str = ""
    source_url: str = ""
    scraped_at: datetime = None
    
    def __post_init__(self):
        if self.contacts is None:
            self.contacts = []
        if self.scraped_at is None:
            self.scraped_at = datetime.utcnow()


class BaseScraper(ABC):
    """Base class for all scrapers."""
    
    def __init__(
        self,
        headless: bool = True,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        timeout: int = 30000,
        max_retries: int = 3,
    ):
        self.headless = headless
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.timeout = timeout
        self.max_retries = max_retries
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
    
    async def start(self):
        """Initialize browser and session."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless, executable_path=settings.PLAYWRIGHT_EXECUTABLE_PATH
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        self.session = aiohttp.ClientSession()
    
    async def stop(self):
        """Close browser and session."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        if self.session:
            await self.session.close()
    
    async def random_delay(self):
        """Random delay between requests."""
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)
    
    async def new_page(self) -> Page:
        """Create new page."""
        page = await self.context.new_page()
        page.set_default_timeout(self.timeout)
        return page
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for companies."""
        pass
    
    @abstractmethod
    async def get_company_details(self, url: str) -> Optional[ScrapedCompany]:
        """Get detailed company info from URL."""
        pass
    
    async def search_companies(
        self,
        keywords: List[str],
        max_pages: int = 2,
        max_details: int = 12,
        **kwargs,
    ) -> List[ScrapedCompany]:
        """Search for companies with multiple keywords."""
        all_companies = []
        
        for keyword in keywords:
            try:
                results = await self.search(keyword, max_pages=max_pages, **kwargs)
                
                # Get details for first max_details results
                for i, result in enumerate(results[:max_details]):
                    if "url" in result:
                        company = await self.get_company_details(result["url"])
                        if company:
                            all_companies.append(company)
                        await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"Error searching '{keyword}': {e}")
        
        return all_companies


class APIScraper(BaseScraper):
    """Base class for API-based scrapers."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(headless=False, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_headers = headers or {}
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Any:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        headers = {**self.default_headers}
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.request(
                    method, url, params=params, json=json, headers=headers
                ) as response:
                    if response.status == 429:
                        # Rate limited
                        wait = 2 ** attempt + random.uniform(1, 3)
                        await asyncio.sleep(wait)
                        continue
                    
                    response.raise_for_status()
                    return await response.json()
                    
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        return None
