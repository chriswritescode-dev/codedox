"""API routes for FastAPI."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db, CodeSearcher
from ..database.models import Document, CrawlJob, CodeSnippet
from ..mcp_server import MCPTools
from ..crawler import CrawlManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
mcp_tools = MCPTools()


class UpdateSourceRequest(BaseModel):
    """Request model for updating source name."""
    name: str = Field(..., min_length=1, max_length=200, description="New source name")


@router.get("/statistics")
async def get_statistics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get dashboard statistics."""
    total_sources = db.query(CrawlJob).filter_by(status='completed').count()
    
    # Only count documents and snippets from non-cancelled jobs
    total_documents = db.query(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled'
    ).count()
    
    total_snippets = db.query(CodeSnippet).join(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled'
    ).count()
    
    # Get language statistics (only from non-cancelled jobs)
    language_stats = db.query(
        CodeSnippet.language,
        func.count(CodeSnippet.id).label('count')
    ).join(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled',
        CodeSnippet.language.isnot(None)
    ).group_by(CodeSnippet.language).all()
    
    languages = {stat.language: stat.count for stat in language_stats}
    
    # Get recent crawls
    recent_crawls = db.query(CrawlJob).order_by(
        CrawlJob.created_at.desc()
    ).limit(5).all()
    
    return {
        "total_sources": total_sources,
        "total_documents": total_documents,
        "total_snippets": total_snippets,
        "languages": languages,
        "recent_crawls": [
            {
                "id": str(crawl.id),
                "name": crawl.name,
                "status": crawl.status,
                "base_url": crawl.start_urls[0] if crawl.start_urls else "",
                "max_depth": crawl.max_depth,
                "urls_crawled": crawl.processed_pages,
                "snippets_extracted": crawl.snippets_extracted,
                "created_at": crawl.created_at.isoformat(),
                "completed_at": crawl.completed_at.isoformat() if crawl.completed_at else None,
            }
            for crawl in recent_crawls
        ]
    }


@router.get("/sources")
async def get_sources(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all sources (completed crawl jobs)."""
    # Use completed crawl jobs as sources
    sources = db.query(CrawlJob).filter_by(status='completed').all()
    
    result = []
    for source in sources:
        # Count snippets through documents
        snippets_count = 0
        for doc in source.documents:
            snippets_count += len(doc.code_snippets)
        
        result.append({
            "id": str(source.id),
            "name": source.name,
            "domain": source.domain,
            "base_url": source.start_urls[0] if source.start_urls else "",
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "documents_count": len(source.documents),
            "snippets_count": snippets_count,
        })
    
    return result


@router.get("/sources/{source_id}")
async def get_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific source (crawl job)."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Count snippets through documents
    snippets_count = 0
    for doc in source.documents:
        snippets_count += len(doc.code_snippets)
    
    return {
        "id": str(source.id),
        "name": source.name,
        "base_url": source.start_urls[0] if source.start_urls else "",
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
        "documents_count": len(source.documents),
        "snippets_count": snippets_count,
    }


@router.get("/sources/{source_id}/documents")
async def get_source_documents(
    source_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get paginated documents for a specific source."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Get total count
    total = db.query(Document).filter_by(crawl_job_id=source_id).count()
    
    # Get paginated documents
    documents = db.query(Document).filter_by(crawl_job_id=source_id)\
        .order_by(Document.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "url": doc.url,
                "title": doc.title or "Untitled",
                "crawl_depth": doc.crawl_depth,
                "snippets_count": len(doc.code_snippets),
                "created_at": doc.created_at.isoformat(),
                "enrichment_status": doc.enrichment_status,
            }
            for doc in documents
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sources/{source_id}/snippets")
async def get_source_snippets(
    source_id: str,
    query: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get paginated code snippets for a specific source with optional search."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # If query is provided, use the search functionality
    if query:
        searcher = CodeSearcher(db)
        snippets, total = searcher.search(
            query=query,
            source=str(source.name),
            language=language,
            limit=limit,
            offset=offset
        )
    else:
        # Build query for snippets
        snippet_query = db.query(CodeSnippet)\
            .join(Document)\
            .filter(Document.crawl_job_id == source_id)
        
        if language:
            snippet_query = snippet_query.filter(CodeSnippet.language == language)
        
        # Get total count
        total = snippet_query.count()
        
        # Get paginated snippets
        snippets = snippet_query\
            .order_by(CodeSnippet.created_at.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()
    
    return {
        "snippets": [
            {
                "id": str(snippet.id),
                "title": snippet.title,
                "code": snippet.code_content,
                "language": snippet.language,
                "description": snippet.description,
                "source_url": snippet.source_url or snippet.document.url,
                "document_title": snippet.document.title,
                "file_path": snippet.source_url,
                "start_line": snippet.line_start,
                "end_line": snippet.line_end,
                "created_at": snippet.created_at.isoformat(),
            }
            for snippet in snippets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sources/{source_id}/languages")
async def get_source_languages(source_id: str, db: Session = Depends(get_db)) -> Dict[str, List[Dict[str, Any]]]:
    """Get unique languages used in a source's code snippets."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Get unique languages with counts
    language_stats = db.query(
        CodeSnippet.language,
        func.count(CodeSnippet.id).label('count')
    ).join(Document).filter(
        Document.crawl_job_id == source_id,
        CodeSnippet.language.isnot(None)
    ).group_by(CodeSnippet.language).all()
    
    return {
        "languages": [
            {"name": stat.language, "count": stat.count}
            for stat in language_stats
        ]
    }


@router.delete("/sources/bulk")
async def delete_sources_bulk(source_ids: List[str], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete multiple sources (crawl jobs) and all their associated data."""
    if not source_ids:
        raise HTTPException(status_code=400, detail="No source IDs provided")
    
    # Validate UUIDs
    valid_ids = []
    for source_id in source_ids:
        try:
            # Try to parse as UUID
            from uuid import UUID
            UUID(source_id)
            valid_ids.append(source_id)
        except ValueError:
            # Skip invalid UUIDs
            pass
    
    if not valid_ids:
        raise HTTPException(status_code=404, detail="No sources found with provided IDs")
    
    # Find all sources to delete
    sources = db.query(CrawlJob).filter(CrawlJob.id.in_(valid_ids)).all()
    
    if not sources:
        raise HTTPException(status_code=404, detail="No sources found with provided IDs")
    
    # Delete all sources (cascade will handle documents and snippets)
    deleted_count = len(sources)
    for source in sources:
        db.delete(source)
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {deleted_count} source(s)",
        "deleted_count": deleted_count
    }


@router.patch("/sources/{source_id}")
async def update_source_name(
    source_id: str,
    request: UpdateSourceRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update source name."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Update the name
    source.name = request.name  # type: ignore[assignment]
    source.updated_at = datetime.utcnow()  # type: ignore[assignment]
    db.commit()
    
    # Return updated source info
    snippets_count = 0
    for doc in source.documents:
        snippets_count += len(doc.code_snippets)
    
    return {
        "id": str(source.id),
        "name": source.name,
        "domain": source.domain,
        "base_url": source.start_urls[0] if source.start_urls else "",
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
        "documents_count": len(source.documents),
        "snippets_count": snippets_count,
    }


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete a source (crawl job) and all its associated data."""
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # The cascade delete will handle documents and code snippets
    db.delete(source)
    db.commit()
    
    return {"message": "Source deleted successfully"}


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
            "enrichment_progress": min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0)) if job.documents_enriched is not None else 0,
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
    from ..database.models import FailedPage
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
        "documents_enriched": job.documents_enriched,
        "retry_count": job.retry_count,
        # Calculate progress percentages
        "crawl_progress": min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0)),
        "enrichment_progress": min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0)),
    }


class CreateCrawlJobRequest(BaseModel):
    name: Optional[str] = None
    base_url: str
    max_depth: int = 2
    domain_filter: Optional[str] = None


@router.post("/crawl-jobs")
async def create_crawl_job(
    request: CreateCrawlJobRequest
) -> Dict[str, Any]:
    """Create a new crawl job."""
    result = await mcp_tools.init_crawl(
        name=request.name,
        start_urls=[request.base_url],
        max_depth=request.max_depth,
        domain_filter=request.domain_filter
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
            from uuid import UUID
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
    success = await crawl_manager.resume_job(job_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job not found or cannot be resumed")
    
    return {"message": "Crawl job resumed successfully", "job_id": job_id}


@router.post("/crawl-jobs/{job_id}/restart-enrichment")
async def restart_enrichment(job_id: str) -> Dict[str, str]:
    """Restart only the enrichment process for a crawl job."""
    crawl_manager = CrawlManager()
    success = await crawl_manager.restart_enrichment(job_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job not found or enrichment cannot be restarted")
    
    return {"message": "Enrichment restarted successfully", "job_id": job_id}


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


@router.get("/search")
async def search_snippets(
    source_name: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Search code snippets."""
    searcher = CodeSearcher(db)
    snippets, total = searcher.search(
        query=query,
        source=source_name,
        language=language,
        limit=limit,
        offset=offset
    )
    
    # Return list directly for backward compatibility with tests
    return [
        {
            "snippet": {
                "id": str(snippet.id),
                "code": snippet.code_content,
                "language": snippet.language,
                "description": snippet.description,
                "source_url": snippet.source_url or snippet.document.url,
                "document_title": snippet.document.title,
                "file_path": snippet.source_url,
                "start_line": snippet.line_start,
                "end_line": snippet.line_end,
                "created_at": snippet.created_at.isoformat(),
            },
            "score": 1.0,  # Placeholder score
        }
        for snippet in snippets
    ]


@router.get("/snippets/{snippet_id}")
async def get_snippet(snippet_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific code snippet."""
    snippet = db.query(CodeSnippet).filter(CodeSnippet.id == int(snippet_id)).first()
    
    if not snippet:
        raise HTTPException(status_code=404, detail="Snippet not found")
    
    return {
        "id": str(snippet.id),
        "title": snippet.title,
        "code": snippet.code_content,
        "language": snippet.language,
        "description": snippet.description,
        "source_url": snippet.source_url or snippet.document.url,
        "document_title": snippet.document.title,
        "file_path": snippet.source_url,
        "start_line": snippet.line_start,
        "end_line": snippet.line_end,
        "created_at": snippet.created_at.isoformat(),
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/health/database")
async def health_database(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Check database health."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "message": "Database is connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/health/llm")
async def health_llm() -> Dict[str, Any]:
    """Check LLM service health."""
    from ..llm.client import LLMClient
    
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
    from ..crawler.health_monitor import get_health_monitor
    
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
    from ..crawler.health_monitor import get_health_monitor
    
    health_monitor = get_health_monitor()
    health_status = health_monitor.check_job_health(job_id)
    
    if health_status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    
    return health_status