"""YellowPages Vietnam scraper."""

from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote

from app.scrapers.base import BaseScraper, ScrapedCompany


class YellowPagesScraper(BaseScraper):
    """Scraper for yellowpages.com.vn"""
    
    BASE_URL = "https://www.yellowpages.com.vn"
    
    async def search(
        self,
        query: str,
        max_pages: int = 2,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search for companies by keyword."""
        results = []
        
        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/tim-kiem/{quote(query)}/trang-{page}.html"
            
            page_obj = await self.new_page()
            try:
                await page_obj.goto(url, wait_until="domcontentloaded")
                await self.random_delay()
                
                # Wait for results
                try:
                    await page_obj.wait_for_selector(".company-item, .search-result-item", timeout=10000)
                except:
                    break
                
                html = await page_obj.content()
                soup = BeautifulSoup(html, "lxml")
                
                # Parse results
                items = soup.select(".company-item, .search-result-item, .item-company")
                if not items:
                    break
                
                for item in items:
                    try:
                        # Company name
                        name_elem = item.select_one("h3 a, .company-name a, .title a")
                        if not name_elem:
                            continue
                        
                        name = name_elem.get_text(strip=True)
                        link = name_elem.get("href", "")
                        
                        if not link.startswith("http"):
                            link = urljoin(self.BASE_URL, link)
                        
                        # Phone
                        phone_elem = item.select_one(".phone, .tel, .contact-phone")
                        phone = phone_elem.get_text(strip=True) if phone_elem else None
                        
                        # Address
                        addr_elem = item.select_one(".address, .dia-chi, .location")
                        address = addr_elem.get_text(strip=True) if addr_elem else None
                        
                        # Category
                        cat_elem = item.select_one(".category, .nganh-nghe")
                        category = cat_elem.get_text(strip=True) if cat_elem else None
                        
                        results.append({
                            "company_name": name,
                            "url": link,
                            "phone": phone,
                            "address": address,
                            "category": category,
                            "source": "yellowpages",
                        })
                    except Exception as e:
                        print(f"Error parsing item: {e}")
                
            finally:
                await page_obj.close()
            
            # Check if no more results
            if not results:
                break
        
        return results
    
    async def get_company_details(self, url: str) -> Optional[ScrapedCompany]:
        """Get detailed company info from profile page."""
        page = await self.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await self.random_delay()
            
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            
            # Company name
            name_elem = soup.select_one("h1.company-name, h1.title, .company-header h1")
            name = name_elem.get_text(strip=True) if name_elem else ""
            
            if not name:
                return None
            
            # Website
            website = None
            web_elem = soup.select_one("a.website, .website a, .company-website a")
            if web_elem:
                website = web_elem.get("href", "").strip()
            
            # Email
            email = None
            email_elem = soup.select_one("a.email, .email a, .contact-email")
            if email_elem:
                email = email_elem.get("href", "").replace("mailto:", "").strip()
            
            # Phone
            phone = None
            phone_elem = soup.select_one(".phone, .tel, .contact-phone, .phone-number")
            if phone_elem:
                phone = phone_elem.get_text(strip=True)
            
            # Address
            address = None
            addr_elem = soup.select_one(".address, .dia-chi, .company-address")
            if addr_elem:
                address = addr_elem.get_text(strip=True)
            
            # City
            city = None
            city_elem = soup.select_one(".city, .thanh-pho, .province")
            if city_elem:
                city = city_elem.get_text(strip=True)
            
            # Industry
            industry = None
            ind_elem = soup.select_one(".industry, .nganh-nghe, .category")
            if ind_elem:
                industry = ind_elem.get_text(strip=True)
            
            # Contacts
            contacts = []
            contact_items = soup.select(".contact-item, .contact-person, .nguoi-lien-he")
            for item in contact_items:
                name_elem = item.select_one(".name, .ten")
                title_elem = item.select_one(".title, .chuc-vu")
                email_elem = item.select_one(".email")
                phone_elem = item.select_one(".phone")
                
                contact = {}
                if name_elem:
                    contact["name"] = name_elem.get_text(strip=True)
                if title_elem:
                    contact["title"] = title_elem.get_text(strip=True)
                if email_elem:
                    contact["email"] = email_elem.get_text(strip=True).replace("mailto:", "")
                if phone_elem:
                    contact["phone"] = phone_elem.get_text(strip=True)
                
                if contact:
                    contacts.append(contact)
            
            return ScrapedCompany(
                company_name=name,
                domain=self._extract_domain(website) if website else None,
                website=website,
                email=self._find_email(soup),
                phone=self._clean_phone(phone) if phone else None,
                address=address,
                city=city,
                industry=industry,
                contacts=contacts if contacts else None,
                source="yellowpages",
                source_url=url,
            )
            
        except Exception as e:
            print(f"Error getting details from {url}: {e}")
            return None
        finally:
            await page.close()
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return None
    
    def _find_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Find email in page."""
        # Look for mailto links
        email_links = soup.select('a[href^="mailto:"]')
        for link in email_links:
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if "@" in email:
                return email
        
        # Look for email in text
        text = soup.get_text()
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        if matches:
            return matches[0]
        
        return None
    
    def _clean_phone(self, phone: str) -> str:
        """Clean phone number."""
        if not phone:
            return ""
        # Remove non-digits except + and spaces
        digits = re.sub(r'[^\d+]', '', phone)
        return digits