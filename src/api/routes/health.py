"""Health check routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...database import get_db
from ...llm.client import LLMClient
from ...crawler.health_monitor import get_health_monitor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/health/database")
async def health_database(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Check database health."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "message": "Database is connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/health/llm")
async def health_llm() -> Dict[str, Any]:
    """Check LLM service health."""
    async with LLMClient(debug=True) as client:
        connection_status = await client.test_connection()
        
        if connection_status.get("status") == "connected":
            return {
                "status": "healthy",
                "message": f"Connected to {connection_status['provider']} at {connection_status['endpoint']}",
                "details": {
                    "provider": connection_status['provider'],
                    "endpoint": connection_status['endpoint'],
                    "model": client.model,
                    "has_api_key": bool(client.api_key),
                    "available_models": connection_status.get('models', [])
                }
            }
        elif connection_status.get("status") == "connection_error":
            return {
                "status": "error",
                "message": f"Cannot connect to LLM: {connection_status.get('error', 'Unknown error')}",
                "details": connection_status
            }
        else:
            return {
                "status": "unhealthy",
                "message": connection_status.get('error', 'LLM service is not responding correctly'),
                "details": connection_status
            }


@router.get("/health/crawl-jobs")
async def health_crawl_jobs() -> Dict[str, Any]:
    """Check health of crawl jobs."""
    health_monitor = get_health_monitor()
    stalled_jobs = health_monitor.get_stalled_jobs()
    
    return {
        "status": "healthy" if not stalled_jobs else "warning",
        "stalled_jobs": stalled_jobs,
        "stalled_count": len(stalled_jobs),
        "message": f"{len(stalled_jobs)} stalled jobs detected" if stalled_jobs else "All jobs healthy"
    }


@router.get("/health/crawl-jobs/{job_id}")
async def health_crawl_job(job_id: str) -> Dict[str, Any]:
    """Check health of a specific crawl job."""
    health_monitor = get_health_monitor()
    health_status = health_monitor.check_job_health(job_id)
    
    if health_status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    
    return health_status