"""Dashboard statistics routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database import get_db
from ...database.models import CodeSnippet, CrawlJob, Document, UploadJob

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/statistics")
async def get_statistics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get dashboard statistics."""
    # Count completed crawl jobs and upload jobs as sources
    crawl_sources = db.query(CrawlJob).filter_by(status='completed').count()
    upload_sources = db.query(UploadJob).filter_by(status='completed').count()
    total_sources = crawl_sources + upload_sources

    # Count documents from both crawl and upload jobs (excluding cancelled)
    crawl_documents = db.query(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled'
    ).count()
    
    upload_documents = db.query(Document).join(UploadJob).filter(
        UploadJob.status != 'cancelled'
    ).count()
    
    total_documents = crawl_documents + upload_documents

    # Count snippets from both crawl and upload jobs (excluding cancelled)
    crawl_snippets = db.query(CodeSnippet).join(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled'
    ).count()
    
    upload_snippets = db.query(CodeSnippet).join(Document).join(UploadJob).filter(
        UploadJob.status != 'cancelled'
    ).count()
    
    total_snippets = crawl_snippets + upload_snippets

    # Get language statistics from both crawl and upload jobs
    crawl_language_stats = db.query(
        CodeSnippet.language,
        func.count(CodeSnippet.id).label('count')
    ).join(Document).join(CrawlJob).filter(
        CrawlJob.status != 'cancelled',
        CodeSnippet.language.isnot(None)
    ).group_by(CodeSnippet.language).all()
    
    upload_language_stats = db.query(
        CodeSnippet.language,
        func.count(CodeSnippet.id).label('count')
    ).join(Document).join(UploadJob).filter(
        UploadJob.status != 'cancelled',
        CodeSnippet.language.isnot(None)
    ).group_by(CodeSnippet.language).all()
    
    # Combine language statistics
    language_dict = {}
    for stat in crawl_language_stats:
        language_dict[stat.language] = stat.count
    for stat in upload_language_stats:
        if stat.language in language_dict:
            language_dict[stat.language] += stat.count
        else:
            language_dict[stat.language] = stat.count

    languages = language_dict

    # Get recent crawls
    recent_crawls = db.query(CrawlJob).order_by(
        CrawlJob.created_at.desc()
    ).limit(5).all()
    
    # Get recent upload jobs
    recent_uploads = db.query(UploadJob).order_by(
        UploadJob.created_at.desc()
    ).limit(5).all()
    
    # Combine and sort all jobs by created_at
    all_jobs = []
    
    # Add crawl jobs with a job_type field
    for crawl in recent_crawls:
        job_dict = crawl.to_dict()
        job_dict['job_type'] = 'crawl'
        all_jobs.append(job_dict)
    
    # Add upload jobs with a job_type field
    for upload in recent_uploads:
        all_jobs.append({
            "id": str(upload.id),
            "name": upload.name,
            "status": upload.status,
            "job_type": "upload",
            "file_count": upload.file_count,
            "processed_files": upload.processed_files,
            "snippets_extracted": upload.snippets_extracted,
            "created_at": upload.created_at.isoformat(),
            "completed_at": upload.completed_at.isoformat() if upload.completed_at else None,
        })
    
    # Sort combined jobs by created_at and take the 5 most recent
    all_jobs.sort(key=lambda x: x["created_at"], reverse=True)
    recent_jobs = all_jobs[:5]

    return {
        "total_sources": total_sources,
        "total_documents": total_documents,
        "total_snippets": total_snippets,
        "languages": languages,
        "recent_jobs": recent_jobs
    }
