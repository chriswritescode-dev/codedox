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
from ...database.models import CrawlJob, UploadJob, Document, CodeSnippet
from ...mcp_server import MCPTools
from ...config import get_settings
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)
router = APIRouter()
mcp_tools = MCPTools()


class UpdateSourceRequest(BaseModel):
    """Request model for updating source name."""
    name: str = Field(..., min_length=1, max_length=200, description="New source name")


@router.get("/sources")
async def get_sources(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get paginated sources (completed crawl jobs and upload jobs)."""
    result = []
    
    # Get completed crawl jobs with pagination
    crawl_sources = db.query(CrawlJob).filter_by(status='completed').offset(offset).limit(limit).all()
    for source in crawl_sources:
        # Count actual snippets in database
        snippet_count = db.query(CodeSnippet).join(Document).filter(
            Document.crawl_job_id == source.id
        ).count()
        
        result.append({
            "id": str(source.id),
            "name": source.name,
            "source_type": "crawl",
            "domain": source.domain,
            "base_url": source.start_urls[0] if source.start_urls else "",
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "documents_count": len(source.documents),
            "snippets_count": snippet_count,
        })
    
    # Get completed upload jobs with pagination
    upload_sources = db.query(UploadJob).filter_by(status='completed').offset(offset).limit(limit).all()
    for source in upload_sources:
        # Count actual snippets in database
        snippet_count = db.query(CodeSnippet).join(Document).filter(
            Document.upload_job_id == source.id
        ).count()
        
        result.append({
            "id": str(source.id),
            "name": source.name,
            "source_type": "upload",
            "domain": "upload",
            "base_url": f"Uploaded: {source.created_at.strftime('%Y-%m-%d')}",
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "documents_count": len(source.documents),
            "snippets_count": snippet_count,
            "file_count": source.file_count,
        })
    
    # Sort by updated_at descending
    result.sort(key=lambda x: x['updated_at'], reverse=True)
    
    # Get total count for pagination
    total_crawl = db.query(CrawlJob).filter_by(status='completed').count()
    total_upload = db.query(UploadJob).filter_by(status='completed').count()
    total = total_crawl + total_upload
    
    return {
        "sources": result,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + limit < total,
        "has_previous": offset > 0,
    }


@router.get("/sources/search")
async def search_sources(
    query: Optional[str] = Query(None, description="Search query for fuzzy matching"),
    min_snippets: Optional[int] = Query(None, ge=0, description="Minimum snippet count"),
    max_snippets: Optional[int] = Query(None, ge=0, description="Maximum snippet count"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Search sources with fuzzy matching and snippet count filtering."""
    
    # Treat empty string as None
    if query == '' or query is None:
        # If no query, just use regular get_sources with filtering
        result = []
        
        # Get all completed crawl jobs
        crawl_query = db.query(CrawlJob).filter_by(status='completed')
        crawl_sources = crawl_query.all()
        
        for source in crawl_sources:
            snippet_count = db.query(CodeSnippet).join(Document).filter(
                Document.crawl_job_id == source.id
            ).count()
            
            # Apply snippet filter
            if min_snippets is not None and snippet_count < min_snippets:
                continue
            if max_snippets is not None and snippet_count > max_snippets:
                continue
                
            result.append({
                "id": str(source.id),
                "name": source.name,
                "source_type": "crawl",
                "domain": source.domain,
                "base_url": source.start_urls[0] if source.start_urls else "",
                "created_at": source.created_at.isoformat(),
                "updated_at": source.updated_at.isoformat(),
                "documents_count": len(source.documents),
                "snippets_count": snippet_count,
                "match_score": None
            })
        
        # Get all completed upload jobs
        upload_query = db.query(UploadJob).filter_by(status='completed')
        upload_sources = upload_query.all()
        
        for source in upload_sources:
            snippet_count = db.query(CodeSnippet).join(Document).filter(
                Document.upload_job_id == source.id
            ).count()
            
            # Apply snippet filter
            if min_snippets is not None and snippet_count < min_snippets:
                continue
            if max_snippets is not None and snippet_count > max_snippets:
                continue
                
            result.append({
                "id": str(source.id),
                "name": source.name,
                "source_type": "upload",
                "domain": "upload",
                "base_url": f"Uploaded: {source.created_at.strftime('%Y-%m-%d')}",
                "created_at": source.created_at.isoformat(),
                "updated_at": source.updated_at.isoformat(),
                "documents_count": len(source.documents),
                "snippets_count": snippet_count,
                "file_count": source.file_count,
                "match_score": None
            })
        
        # Sort by snippets_count descending, then updated_at
        result.sort(key=lambda x: (-x['snippets_count'], x['updated_at']), reverse=True)
        
        # Apply pagination
        total = len(result)
        result = result[offset:offset + limit]
        
        return {
            "sources": result,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
            "has_previous": offset > 0,
            "query": None,
            "filters": {
                "min_snippets": min_snippets,
                "max_snippets": max_snippets
            }
        }
    
    # We have a query - use CodeSearcher for fuzzy search
    searcher = CodeSearcher(db)
    
    # Get all matching libraries
    libraries, total_count = searcher.search_libraries(
        query=query,
        limit=1000,  # Get all to filter by snippets
        offset=0
    )
    
    # Convert to sources format and filter
    sources = []
    for lib in libraries:
        # Apply snippet count filter
        if min_snippets is not None and lib['snippet_count'] < min_snippets:
            continue
        if max_snippets is not None and lib['snippet_count'] > max_snippets:
            continue
        
        # Get the actual source to get more details
        if lib['source_type'] == 'crawl':
            source = db.query(CrawlJob).filter_by(id=lib['library_id']).first()
            if source:
                sources.append({
                    "id": lib['library_id'],
                    "name": lib['name'],
                    "source_type": "crawl",
                    "domain": source.domain,
                    "base_url": source.start_urls[0] if source.start_urls else "",
                    "created_at": source.created_at.isoformat(),
                    "updated_at": source.updated_at.isoformat(),
                    "documents_count": len(source.documents),
                    "snippets_count": lib['snippet_count'],
                    "match_score": lib.get('similarity_score', 0.0)
                })
        else:
            source = db.query(UploadJob).filter_by(id=lib['library_id']).first()
            if source:
                sources.append({
                    "id": lib['library_id'],
                    "name": lib['name'],
                    "source_type": "upload",
                    "domain": "upload",
                    "base_url": f"Uploaded: {source.created_at.strftime('%Y-%m-%d')}",
                    "created_at": source.created_at.isoformat(),
                    "updated_at": source.updated_at.isoformat(),
                    "documents_count": len(source.documents),
                    "snippets_count": lib['snippet_count'],
                    "file_count": source.file_count,
                    "match_score": lib.get('similarity_score', 0.0)
                })
    
    # Sort by match score
    sources.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    
    # Apply pagination
    total = len(sources)
    paginated_sources = sources[offset:offset + limit]
    
    return {
        "sources": paginated_sources,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + limit < total,
        "has_previous": offset > 0,
        "query": query,
        "filters": {
            "min_snippets": min_snippets,
            "max_snippets": max_snippets
        }
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific source (crawl job or upload job)."""
    # Try crawl job first
    crawl_source = db.query(CrawlJob).filter_by(id=source_id).first()
    if crawl_source:
        # Count actual snippets in database
        snippet_count = db.query(CodeSnippet).join(Document).filter(
            Document.crawl_job_id == crawl_source.id
        ).count()
        
        return {
            "id": str(crawl_source.id),
            "name": crawl_source.name,
            "source_type": "crawl",
            "domain": crawl_source.domain,
            "base_url": crawl_source.start_urls[0] if crawl_source.start_urls else "",
            "created_at": crawl_source.created_at.isoformat(),
            "updated_at": crawl_source.updated_at.isoformat(),
            "documents_count": len(crawl_source.documents),
            "snippets_count": snippet_count,
        }
    
    # Try upload job
    upload_source = db.query(UploadJob).filter_by(id=source_id).first()
    if upload_source:
        # Count actual snippets in database
        snippet_count = db.query(CodeSnippet).join(Document).filter(
            Document.upload_job_id == upload_source.id
        ).count()
        
        return {
            "id": str(upload_source.id),
            "name": upload_source.name,
            "source_type": "upload",
            "domain": "upload",
            "base_url": f"Uploaded: {upload_source.created_at.strftime('%Y-%m-%d')}",
            "created_at": upload_source.created_at.isoformat(),
            "updated_at": upload_source.updated_at.isoformat(),
            "documents_count": len(upload_source.documents),
            "snippets_count": snippet_count,
            "file_count": upload_source.file_count,
        }
    
    raise HTTPException(status_code=404, detail="Source not found")


@router.get("/sources/{source_id}/documents")
async def get_source_documents(
    source_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get paginated documents for a specific source."""
    # Check if it's a crawl job or upload job
    crawl_source = db.query(CrawlJob).filter_by(id=source_id).first()
    upload_source = db.query(UploadJob).filter_by(id=source_id).first()
    
    if not crawl_source and not upload_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Build query based on source type
    if crawl_source:
        query = db.query(Document).filter_by(crawl_job_id=source_id)
    else:
        query = db.query(Document).filter_by(upload_job_id=source_id)
    
    # Get total count
    total = query.count()
    
    # Get paginated documents
    documents = query\
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
                "crawl_depth": doc.crawl_depth if crawl_source else 0,
                "snippets_count": len(doc.code_snippets),
                "created_at": doc.created_at.isoformat(),
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
    # Check if it's a crawl job or upload job
    crawl_source = db.query(CrawlJob).filter_by(id=source_id).first()
    upload_source = db.query(UploadJob).filter_by(id=source_id).first()
    
    if not crawl_source and not upload_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source = crawl_source or upload_source
    
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
        # Build query for snippets based on source type
        snippet_query = db.query(CodeSnippet).join(Document)
        
        if crawl_source:
            snippet_query = snippet_query.filter(Document.crawl_job_id == source_id)
        else:
            snippet_query = snippet_query.filter(Document.upload_job_id == source_id)
        
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
    # Find the source (either crawl job or upload job)
    crawl_source = db.query(CrawlJob).filter_by(id=source_id).first()
    upload_source = db.query(UploadJob).filter_by(id=source_id).first()
    
    if not crawl_source and not upload_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source_type = "crawl" if crawl_source else "upload"
    
    # Get unique languages with counts
    language_stats = db.query(
        CodeSnippet.language,
        func.count(CodeSnippet.id).label('count')
    ).join(Document).filter(
        (Document.crawl_job_id == source_id) if source_type == "crawl" else (Document.upload_job_id == source_id),
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
    """Delete multiple sources (crawl jobs or upload jobs) and all their associated data."""
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
    
    # Find all crawl job sources to delete
    sources = db.query(CrawlJob).filter(CrawlJob.id.in_(valid_ids)).all()
    deleted_count = len(sources)
    
    # If we don't find enough sources, check for upload jobs
    if deleted_count < len(valid_ids):
        remaining_ids = [id for id in valid_ids if not any(s.id == id for s in sources)]
        upload_sources = db.query(UploadJob).filter(UploadJob.id.in_(remaining_ids)).all()
        sources.extend(upload_sources)
        deleted_count = len(sources)
    
    if not sources:
        raise HTTPException(status_code=404, detail="No sources found with provided IDs")
    
    # Delete all sources (cascade will handle documents and snippets)
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
    """Update source name for both crawl jobs and upload jobs."""
    # Try crawl job first
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    is_upload_job = False
    
    if not source:
        source = db.query(UploadJob).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        is_upload_job = True
    
    # Update the name
    source.name = request.name
    source.updated_at = datetime.utcnow()
    db.commit()
    
    # Return updated source info
    if is_upload_job:
        upload_source = source  # type: ignore
        return {
            "id": str(upload_source.id),
            "name": upload_source.name,
            "source_type": "upload",
            "domain": "upload",
            "base_url": f"Uploaded: {upload_source.created_at.strftime('%Y-%m-%d')}",
            "created_at": upload_source.created_at.isoformat(),
            "updated_at": upload_source.updated_at.isoformat(),
            "documents_count": len(upload_source.documents),
            "snippets_count": len([doc for doc in upload_source.documents for doc in doc.code_snippets]),
            "file_count": upload_source.file_count,
        }
    else:
        crawl_source = source  # type: ignore
        return {
            "id": str(crawl_source.id),
            "name": crawl_source.name,
            "source_type": "crawl",
            "domain": crawl_source.domain,
            "base_url": crawl_source.start_urls[0] if crawl_source.start_urls else "",
            "created_at": crawl_source.created_at.isoformat(),
            "updated_at": crawl_source.updated_at.isoformat(),
            "documents_count": len(crawl_source.documents),
            "snippets_count": crawl_source.snippets_extracted,
        }


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete a source (crawl job or upload job) and all its associated data."""
    # Try crawl job first
    source = db.query(CrawlJob).filter_by(id=source_id).first()
    
    # If not found, try upload job
    if not source:
        source = db.query(UploadJob).filter_by(id=source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # The cascade delete will handle documents and code snippets
        db.delete(source)
        db.commit()
        return {"message": "Source deleted successfully"}
    
    # The cascade delete will handle documents and code snippets
    db.delete(source)
    db.commit()
    
    return {"message": "Source deleted successfully"}


class RecrawlRequest(BaseModel):
    """Request model for recrawling a source."""
    ignore_hash: bool = Field(default=False, description="Ignore content hash and regenerate all content")


@router.post("/sources/{source_id}/recrawl")
async def recrawl_source(
    source_id: str, 
    request: RecrawlRequest = RecrawlRequest(),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Recrawl an existing source (completed crawl job only)."""
    # Check if it's an upload job first
    upload_job = db.query(UploadJob).filter_by(id=source_id).first()
    if upload_job:
        raise HTTPException(status_code=400, detail="Recrawl is not available for uploaded sources")
    
    # Get the original crawl job
    original_job = db.query(CrawlJob).filter_by(id=source_id).first()
    if not original_job:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if original_job.status != 'completed':
        raise HTTPException(status_code=400, detail="Can only recrawl completed sources")
    
    try:
        # Use the same init_crawl method that MCP and web UI use
        # Get configuration from original job config if available
        max_concurrent = get_settings().crawling.max_concurrent_crawls  # default
        url_patterns = None  # default
        
        if original_job.config and isinstance(original_job.config, dict):
            max_concurrent = original_job.config.get('max_concurrent_crawls', get_settings().crawling.max_concurrent_crawls)
            # Preserve URL patterns from original crawl
            url_patterns = original_job.config.get('url_patterns', original_job.config.get('include_patterns'))
        
        result = await mcp_tools.init_crawl(
            name=original_job.name,
            start_urls=original_job.start_urls,
            max_depth=original_job.max_depth,
            domain_filter=original_job.domain if original_job.domain else None,
            url_patterns=url_patterns,
            metadata={
                "is_recrawl": True,
                "original_source_id": source_id,
                "original_name": original_job.name,
                "recrawl_started_at": datetime.utcnow().isoformat(),
                "ignore_hash": request.ignore_hash
            },
            max_concurrent_crawls=max_concurrent
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