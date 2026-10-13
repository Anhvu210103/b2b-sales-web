"""Scrapers package."""

from app.scrapers.base import BaseScraper, APIScraper, ScrapedCompany
from app.scrapers.yellowpages import YellowPagesScraper
from app.scrapers.vietnamworks import VietnamWorksScraper
from app.scrapers.apollo import ApolloScraper
from app.scrapers.signals import SignalsScraper
from app.scrapers.scheduler import ScraperScheduler, JobStatus

__all__ = [
    "BaseScraper",
    "APIScraper",
    "ScrapedCompany",
    "YellowPagesScraper",
    "VietnamWorksScraper",
    "ApolloScraper",
    "SignalsScraper",
    "ScraperScheduler",
    "JobStatus",
]