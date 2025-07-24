"""Crawl job management routes."""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...database.models import CrawlJob, FailedPage
from ...mcp_server import MCPTools
from ...crawler import CrawlManager

logger = logging.getLogger(__name__)
router = APIRouter()
mcp_tools = MCPTools()


class CreateCrawlJobRequest(BaseModel):
    name: Optional[str] = None
    base_url: str
    max_depth: int = 2
    domain_filter: Optional[str] = None
    url_patterns: Optional[List[str]] = None
    max_concurrent_crawls: int = 20


@router.get("/crawl-jobs")
async def get_crawl_jobs(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all crawl jobs."""
    jobs = db.query(CrawlJob).order_by(CrawlJob.created_at.desc()).all()
    
    return [
        {
            "id": str(job.id),
            "name": job.name,
            "domain": job.domain,
            "status": job.status,
            "base_url": job.start_urls[0] if job.start_urls else "",
            "max_depth": job.max_depth,
            "urls_crawled": job.processed_pages,
            "total_pages": job.total_pages,
            "snippets_extracted": job.snippets_extracted,
            "crawl_phase": job.crawl_phase,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            # Calculate progress percentages
            "crawl_progress": min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0)),
        }
        for job in jobs
    ]


@router.get("/crawl-jobs/{job_id}")
async def get_crawl_job(job_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific crawl job."""
    job = db.query(CrawlJob).filter_by(id=job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    
    # Count failed pages
    failed_pages_count = db.query(FailedPage).filter_by(crawl_job_id=job_id).count()
    
    return {
        "id": str(job.id),
        "name": job.name,
        "domain": job.domain,
        "status": job.status,
        "base_url": job.start_urls[0] if job.start_urls else "",
        "max_depth": job.max_depth,
        "urls_crawled": job.processed_pages,
        "total_pages": job.total_pages,
        "snippets_extracted": job.snippets_extracted,
        "failed_pages_count": failed_pages_count,
        "created_at": job.created_at.isoformat() + "Z",
        "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
        "completed_at": job.completed_at.isoformat() + "Z" if job.completed_at else None,
        "error_message": job.error_message,
        "crawl_phase": job.crawl_phase,
        "last_heartbeat": job.last_heartbeat.isoformat() + "Z" if job.last_heartbeat else None,
        "documents_crawled": job.documents_crawled,
        "retry_count": job.retry_count,
        # Calculate progress percentages
        "crawl_progress": min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0)),
    }


@router.post("/crawl-jobs")
async def create_crawl_job(
    request: CreateCrawlJobRequest
) -> Dict[str, Any]:
    """Create a new crawl job."""
    result = await mcp_tools.init_crawl(
        name=request.name,
        start_urls=[request.base_url],
        max_depth=request.max_depth,
        domain_filter=request.domain_filter,
        url_patterns=request.url_patterns,
        max_concurrent_crawls=request.max_concurrent_crawls
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Add 'id' field for frontend compatibility
    result['id'] = result.get('job_id')
    
    return result


@router.delete("/crawl-jobs/bulk")
async def delete_crawl_jobs_bulk(job_ids: List[str], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete multiple crawl jobs and all their associated data."""
    if not job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided")
    
    # Validate UUIDs
    valid_ids = []
    for job_id in job_ids:
        try:
            # Try to parse as UUID
            UUID(job_id)
            valid_ids.append(job_id)
        except ValueError:
            # Skip invalid UUIDs
            pass
    
    if not valid_ids:
        raise HTTPException(status_code=404, detail="No deletable jobs found with provided IDs")
    
    # Find all jobs to delete - only allow deletion of completed, failed, or cancelled jobs
    jobs = db.query(CrawlJob).filter(
        CrawlJob.id.in_(valid_ids),
        CrawlJob.status.in_(['completed', 'failed', 'cancelled'])
    ).all()
    
    if not jobs:
        raise HTTPException(status_code=404, detail="No deletable jobs found with provided IDs")
    
    # Check for active crawler tasks
    crawl_manager = CrawlManager()
    active_jobs = []
    for job in jobs:
        job_id = str(job.id)
        if hasattr(crawl_manager, '_active_crawl_tasks') and job_id in crawl_manager._active_crawl_tasks:
            task = crawl_manager._active_crawl_tasks[job_id]
            if not task.done():
                active_jobs.append(job_id)
    
    if active_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete jobs with active crawler tasks: {', '.join(active_jobs)}. Please cancel these jobs first."
        )
    
    # Delete all jobs (cascade will handle documents and snippets)
    deleted_count = len(jobs)
    for job in jobs:
        db.delete(job)
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {deleted_count} job(s)",
        "deleted_count": deleted_count
    }


@router.delete("/crawl-jobs/{job_id}")
async def delete_crawl_job(job_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete a crawl job and all its associated data."""
    job = db.query(CrawlJob).filter_by(id=job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    
    # Only allow deletion of completed, failed, or cancelled jobs
    if job.status not in ['completed', 'failed', 'cancelled']:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete job with status '{job.status}'. Only completed, failed, or cancelled jobs can be deleted."
        )
    
    # Check if there's an active crawler task for this job
    crawl_manager = CrawlManager()
    if hasattr(crawl_manager, '_active_crawl_tasks') and job_id in crawl_manager._active_crawl_tasks:
        task = crawl_manager._active_crawl_tasks[job_id]
        if not task.done():
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete job with active crawler task. Please cancel the job first."
            )
    
    # The cascade delete will handle documents and code snippets
    db.delete(job)
    db.commit()
    
    return {"message": "Crawl job deleted successfully"}


@router.post("/crawl-jobs/{job_id}/cancel")
async def cancel_crawl_job(job_id: str) -> Dict[str, str]:
    """Cancel a running crawl job."""
    crawl_manager = CrawlManager()
    success = await crawl_manager.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job not found or not cancellable")
    
    return {"message": "Crawl job cancelled successfully"}


@router.post("/crawl-jobs/{job_id}/resume")
async def resume_crawl_job(job_id: str) -> Dict[str, str]:
    """Resume a failed or stalled crawl job."""
    crawl_manager = CrawlManager()
    
    # Check if there are failed pages
    from ...database import FailedPage, get_db_manager
    db_manager = get_db_manager()
    with db_manager.session_scope() as session:
        failed_count = session.query(FailedPage).filter_by(crawl_job_id=job_id).count()
    
    if failed_count > 0:
        # Use retry_failed_pages which returns the new job ID
        new_job_id = await crawl_manager.retry_failed_pages(job_id)
        if new_job_id:
            return {"message": f"Created new job to retry {failed_count} failed pages", "id": new_job_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to create retry job")
    else:
        # Resume the existing job
        success = await crawl_manager.resume_job(job_id)
        if not success:
            raise HTTPException(status_code=400, detail="Job not found or cannot be resumed")
        
        return {"message": "Crawl job resumed successfully", "id": job_id}



@router.post("/crawl-jobs/{job_id}/retry-failed")
async def retry_failed_pages(job_id: str) -> Dict[str, str]:
    """Create a new crawl job to retry failed pages from a previous job."""
    crawl_manager = CrawlManager()
    new_job_id = await crawl_manager.retry_failed_pages(job_id)
    
    if not new_job_id:
        raise HTTPException(status_code=400, detail="No failed pages found or job not found")
    
    return {
        "message": "Retry job created successfully",
        "job_id": job_id,
        "new_job_id": new_job_id
    }