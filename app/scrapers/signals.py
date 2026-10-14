"""Signals scraper - news, associations, portfolio companies."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import feedparser
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from app.scrapers.base import BaseScraper, ScrapedCompany
from app.config import settings


class SignalsScraper(BaseScraper):
    """Scraper for buying signals from multiple sources."""
    
    def __init__(self, **kwargs):
        super().__init__(headless=kwargs.pop("headless", settings.PLAYWRIGHT_HEADLESS), **kwargs)
        
        # News sources
        self.news_feeds = {
            "vietstock": "https://vietstock.vn/820/doanh-nghiep.rss",
            "vneconomy": "https://vneconomy.vn/rss/doanh-nghiep.rss",
            "cafef": "https://cafef.vn/rss/doanh-nghiep.rss",
            "nhipsongkinhte": "https://nhipsongkinhte.vn/rss/doanh-nghiep.rss",
            "google_news_goi_von": "https://news.google.com/rss/search?q=goi+von&hl=vi&gl=VN&ceid=VN:vi",
            "google_news_huy_dong": "https://news.google.com/rss/search?q=huy+dong+von&hl=vi&gl=VN&ceid=VN:vi",
            "google_news_nhan_dau_tu": "https://news.google.com/rss/search?q=nhan+dau+tu&hl=vi&gl=VN&ceid=VN:vi",
            "google_news_khai_truong": "https://news.google.com/rss/search?q=khai+truong&hl=vi&gl=VN&ceid=VN:vi",
            "google_news_mo_rong": "https://news.google.com/rss/search?q=mo+rong&hl=vi&gl=VN&ceid=VN:vi",
        }
        
        # Association targets
        self.association_targets = [
            ("HANOISME", "https://hanoisme.vn/"),
            ("VINASA", "https://vinasa.org.vn/"),
            ("VCCI", "https://vcci.com.vn/"),
            ("VLA", "https://vla.com.vn/"),
            ("VNREA", "https://vnrea.vn/"),
        ]
        
        # Portfolio/Incubator targets
        self.portfolio_targets = [
            ("BSSC", "https://bssc.vn/"),
            ("VSV Capital", "https://vsvcapital.com/"),
            ("ThinkZone", "https://thinkzone.vn/"),
            ("Toong", "https://toong.com/"),
        ]
        
        # Funding keywords
        self.funding_keywords = [
            "goi von", "huy dong von", "rot von", "dau tu", "nhan dau tu",
            "vong goi von", "series a", "series b", "seed round", "pre-seed",
            "funding", "raised", "khai truong", "mo chi nhanh", "mo rong",
            "m&a", "sap nhap", "hop nhat", "mua lai", "tieng chuc",
        ]
    
    # ==================== News Signals ====================
    
    async def scrape_news_signals(
        self,
        days: int = 30,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape news for funding/expansion signals."""
        if sources is None:
            sources = list(self.news_feeds.keys())
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        signals = []
        
        for source in sources:
            if source not in self.news_feeds:
                continue
            
            try:
                feed = feedparser.parse(self.news_feeds[source])
                
                for entry in feed.entries:
                    # Parse date
                    published = self._parse_date(entry)
                    if published and published < cutoff:
                        continue
                    
                    # Check for funding keywords
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    text = f"{title} {summary}".lower()
                    
                    matched_keywords = []
                    for kw in self.funding_keywords:
                        if kw in text:
                            matched_keywords.append(kw)
                    
                    if not matched_keywords:
                        continue
                    
                    # Extract company name
                    company_name = self._extract_company_from_title(title)
                    
                    signals.append({
                        "company_name": company_name,
                        "signal_type": "funding_news",
                        "title": title,
                        "url": entry.get("link", ""),
                        "source": source,
                        "published_at": published.isoformat() if published else None,
                        "matched_keywords": matched_keywords,
                        "summary": summary[:500],
                        "signal_strength": "high" if any(k in ["goi von", "huy dong von", "series", "funding", "raised"] for k in matched_keywords) else "medium",
                    })
                    
            except Exception as e:
                print(f"Error scraping {source}: {e}")
        
        return signals
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse date from feed entry."""
        for field in ["published_parsed", "updated_parsed"]:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    return datetime(*getattr(entry, field)[:6])
                except:
                    pass
        
        for field in ["published", "updated"]:
            if field in entry:
                try:
                    # Try parsing common formats
                    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]:
                        try:
                            return datetime.strptime(entry[field][:25], fmt[:25])
                        except:
                            pass
                except:
                    pass
        return None
    
    def _extract_company_from_title(self, title: str) -> str:
        """Extract company name from news title."""
        # Patterns for company names in Vietnamese news
        patterns = [
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:goi|huy dong|nhan|rot|khai truong|mo rong)",
            r"(?:cong ty|cty|company)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:vua|moi|vua moi)\s+(?:goi|huy dong|nhan dau tu)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: first capitalized words
        words = title.split()
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 2:
                # Take this and next few capitalized words
                company = [word]
                for w in words[i+1:i+4]:
                    if w[0].isupper() and w not in ["Va", "Voi", "Cua", "Cho", "Tai", "Trong", "Tren", "Duoi"]:
                        company.append(w)
                    else:
                        break
                return " ".join(company)
        
        return "Unknown"
    
    # ==================== Association Members ====================
    
    async def scrape_associations(
        self,
        targets: Optional[List[tuple]] = None,
    ) -> List[ScrapedCompany]:
        """Scrape member companies from association websites."""
        if targets is None:
            targets = self.association_targets
        
        companies = []
        
        for name, url in targets:
            try:
                companies.extend(await self._scrape_association_page(name, url))
            except Exception as e:
                print(f"Error scraping association {name}: {e}")
        
        return companies
    
    async def _scrape_association_page(
        self,
        association_name: str,
        url: str,
    ) -> List[ScrapedCompany]:
        """Scrape a single association member page."""
        companies = []
        
        page = await self.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await self.random_delay()
            
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            
            # Find all external links
            links = soup.find_all("a", href=True)
            
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                
                # Skip internal links and noise
                if not href.startswith("http"):
                    continue
                if any(skip in href for skip in ["facebook.com", "youtube.com", "linkedin.com", "twitter.com", "instagram.com", "zalo.me"]):
                    continue
                if any(skip in text.lower() for skip in ["trang chủ", "liên hệ", "giới thiệu", "đăng nhập", "đăng ký", "tuyển dụng", "home", "about", "contact", "login"]):
                    continue
                if len(text) < 3 or len(text) > 80:
                    continue
                
                # Extract domain
                domain = self._extract_domain(href)
                if not domain or domain in ["facebook.com", "youtube.com", "linkedin.com"]:
                    continue
                
                company = ScrapedCompany(
                    company_name=text,
                    domain=domain,
                    website=href,
                    source="association",
                    source_url=url,
                    industry=f"Association: {association_name}",
                )
                companies.append(company)
                
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        finally:
            await page.close()
        
        return companies
    
    # ==================== Portfolio Companies ====================
    
    async def scrape_portfolios(
        self,
        targets: Optional[List[tuple]] = None,
    ) -> List[ScrapedCompany]:
        """Scrape portfolio companies from incubators/VCs."""
        if targets is None:
            targets = self.portfolio_targets
        
        companies = []
        
        for name, url in targets:
            try:
                companies.extend(await self._scrape_portfolio_page(name, url))
            except Exception as e:
                print(f"Error scraping portfolio {name}: {e}")
        
        return companies
    
    async def _scrape_portfolio_page(
        self,
        portfolio_name: str,
        url: str,
    ) -> List[ScrapedCompany]:
        """Scrape a single portfolio page."""
        companies = []
        
        page = await self.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await self.random_delay()
            
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            
            links = soup.find_all("a", href=True)
            
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                
                # Skip noise
                if not href.startswith("http"):
                    continue
                if any(skip in href for skip in ["facebook.com", "youtube.com", "linkedin.com", "twitter.com", "instagram.com"]):
                    continue
                if any(skip in text.lower() for skip in ["trang chủ", "liên hệ", "giới thiệu", "đăng nhập", "đăng ký", "home", "about", "contact", "login", "sign up"]):
                    continue
                if len(text) < 3 or len(text) > 80:
                    continue
                
                domain = self._extract_domain(href)
                if not domain:
                    continue
                
                # Skip known noise domains
                noise_domains = ["wordpress.com", "wix.com", "shopify.com", "sapo.vn", "haravan.com", "google.com", "bit.ly"]
                if any(n in domain for n in noise_domains):
                    continue
                
                company = ScrapedCompany(
                    company_name=text,
                    domain=domain,
                    website=href,
                    source="portfolio",
                    source_url=url,
                    industry=f"Portfolio: {portfolio_name}",
                )
                companies.append(company)
                
        except Exception as e:
            print(f"Error scraping portfolio {url}: {e}")
        finally:
            await page.close()
        
        return companies
    
    # ==================== crt.sh SSL Certificates ====================
    
    async def scrape_crtsh(
        self,
        query: str = "%.vn",
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Scrape crt.sh for new SSL certificates."""
        import aiohttp
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        results = []
        
        url = f"https://crt.sh/?q={query}&output=json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=120) as resp:
                    if resp.status != 200:
                        return []
                    
                    data = await resp.json()
                    
                    for entry in data:
                        not_before = entry.get("not_before")
                        if not_before:
                            try:
                                cert_date = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
                                if cert_date < cutoff:
                                    continue
                            except:
                                continue
                        
                        # Extract domain
                        name_value = entry.get("name_value", "")
                        common_name = entry.get("common_name", "")
                        
                        for domain_str in [name_value, common_name]:
                            for line in domain_str.split("\n"):
                                domain = self._registrable_domain(line.strip())
                                if domain and domain.endswith(".vn"):
                                    results.append({
                                        "domain": domain,
                                        "cert_date": cert_date.isoformat() if cert_date else None,
                                        "issuer": entry.get("issuer_name", ""),
                                        "source": "crt.sh",
                                    })
        except Exception as e:
            print(f"crt.sh error: {e}")
        
        return results
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract registrable domain from URL."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            return self._registrable_domain(host)
        except:
            return None
    
    def _registrable_domain(self, host: str) -> Optional[str]:
        """Get registrable domain (e.g., company.com.vn)."""
        host = host.lower().strip(".")
        if not host or "." not in host:
            return None
        
        labels = host.split(".")
        if len(labels) >= 3 and labels[-2] in ["com", "net", "org", "edu", "gov", "co", "net"]:
            return ".".join(labels[-3:])
        return ".".join(labels[-2:])
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search across all signal sources."""
        results = []
        
        # News signals
        news = await self.scrape_news_signals(days=30)
        for n in news:
            n["source_type"] = "news"
            results.append(n)
        
        # Associations
        associations = await self.scrape_associations()
        for a in associations:
            results.append({
                "company_name": a.company_name,
                "domain": a.domain,
                "website": a.website,
                "source": a.source,
                "source_url": a.source_url,
                "industry": a.industry,
            })
        
        # Portfolios
        portfolios = await self.scrape_portfolios()
        for p in portfolios:
            results.append({
                "company_name": p.company_name,
                "domain": p.domain,
                "website": p.website,
                "source": p.source,
                "source_url": p.source_url,
                "industry": p.industry,
            })
        
        return results
    
    async def get_company_details(self, url: str) -> Optional[Any]:
        """Not used for signals scraper."""
        return None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search across all signal sources."""
        return await self.scrape_news_signals()