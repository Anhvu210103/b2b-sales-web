"""API v1 router."""

from fastapi import APIRouter
from app.config import settings

from app.api.v1.leads import router as leads_router
from app.api.v1.outreach import router as outreach_router
from app.api.v1.deals import router as deals_router
from app.api.v1.users import router as users_router
from app.api.v1.auth import router as auth_router
from app.api.v1.scraping import router as scraping_router
from app.api.v1.analytics import router as analytics_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(leads_router, prefix="/leads", tags=["Leads"])
router.include_router(outreach_router, prefix="/outreach", tags=["Outreach"])
router.include_router(deals_router, prefix="/deals", tags=["Deals"])
if settings.ENABLE_SCRAPING:
    router.include_router(scraping_router, prefix="/scraping", tags=["Scraping"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
