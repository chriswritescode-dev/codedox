"""API routes module."""

from fastapi import APIRouter

from .sources import router as sources_router
from .crawl_jobs import router as crawl_jobs_router
from .search import router as search_router
from .health import router as health_router
from .statistics import router as statistics_router

# Create main router
router = APIRouter(prefix="/api")

# Include all sub-routers
router.include_router(sources_router)
router.include_router(crawl_jobs_router)
router.include_router(search_router)
router.include_router(health_router)
router.include_router(statistics_router)

__all__ = ["router"]