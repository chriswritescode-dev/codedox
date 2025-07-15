"""Source management routes."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database import get_db, CodeSearcher
from ...database.models import CrawlJob, Document, CodeSnippet
from ...mcp_server import MCPTools

logger = logging.getLogger(__name__)
router = APIRouter()
mcp_tools = MCPTools()


class UpdateSourceRequest(BaseModel):
    """Request model for updating source name."""
    name: str = Field(..., min_length=1, max_length=200, description="New source name")


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


@router.post("/sources/{source_id}/recrawl")
async def recrawl_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Recrawl an existing source (completed crawl job)."""
    # Get the original crawl job
    original_job = db.query(CrawlJob).filter_by(id=source_id).first()
    if not original_job:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if original_job.status != 'completed':
        raise HTTPException(status_code=400, detail="Can only recrawl completed sources")
    
    try:
        # Use the same init_crawl method that MCP and web UI use
        result = await mcp_tools.init_crawl(
            name=original_job.name,
            start_urls=original_job.start_urls,
            max_depth=original_job.max_depth,
            domain_filter=original_job.domain if original_job.domain else None,
            metadata={
                "is_recrawl": True,
                "original_source_id": source_id,
                "original_name": original_job.name,
                "recrawl_started_at": datetime.utcnow().isoformat()
            }
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # For recrawl, the job_id will be the same as source_id due to domain reuse
        # Add 'id' field for frontend compatibility
        result['id'] = source_id
        result['is_recrawl'] = True
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to recrawl source: {e}")
        raise HTTPException(status_code=400, detail=str(e))