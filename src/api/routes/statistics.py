"""Dashboard statistics routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database import get_db
from ...database.models import Document, CrawlJob, CodeSnippet

logger = logging.getLogger(__name__)
router = APIRouter()


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