"""Source management routes."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...config import get_settings
from ...database import CodeSearcher, get_db
from ...database.models import CodeSnippet, CrawlJob, Document, UploadJob
from ...mcp_server import MCPTools

logger = logging.getLogger(__name__)
router = APIRouter()
mcp_tools = MCPTools()


class UpdateSourceRequest(BaseModel):
    """Request model for updating source name."""
    name: str = Field(..., min_length=1, max_length=200, description="New source name")


def _get_snippet_counts_for_crawl_jobs(db: Session, job_ids: list[str]) -> dict[str, int]:
    """Get snippet counts for multiple crawl jobs in a single query."""
    if not job_ids:
        return {}

    counts = db.query(
        Document.crawl_job_id,
        func.count(CodeSnippet.id).label('count')
    ).join(
        CodeSnippet, Document.id == CodeSnippet.document_id
    ).filter(
        Document.crawl_job_id.in_(job_ids)
    ).group_by(
        Document.crawl_job_id
    ).all()

    return {str(row.crawl_job_id): getattr(row, 'count') for row in counts}


def _get_snippet_counts_for_upload_jobs(db: Session, job_ids: list[str]) -> dict[str, int]:
    """Get snippet counts for multiple upload jobs in a single query."""
    if not job_ids:
        return {}

    counts = db.query(
        Document.upload_job_id,
        func.count(CodeSnippet.id).label('count')
    ).join(
        CodeSnippet, Document.id == CodeSnippet.document_id
    ).filter(
        Document.upload_job_id.in_(job_ids)
    ).group_by(
        Document.upload_job_id
    ).all()

    return {str(row.upload_job_id): getattr(row, 'count') for row in counts}


def _batch_get_crawl_jobs(db: Session, job_ids: list[str]) -> dict[str, CrawlJob]:
    """Batch fetch multiple crawl jobs in a single query."""
    if not job_ids:
        return {}
    
    jobs = db.query(CrawlJob).filter(CrawlJob.id.in_(job_ids)).all()
    return {str(job.id): job for job in jobs}


def _batch_get_upload_jobs(db: Session, job_ids: list[str]) -> dict[str, UploadJob]:
    """Batch fetch multiple upload jobs in a single query."""
    if not job_ids:
        return {}
    
    jobs = db.query(UploadJob).filter(UploadJob.id.in_(job_ids)).all()
    return {str(job.id): job for job in jobs}


def _build_crawl_source_dict(source: CrawlJob, snippet_count: int) -> dict[str, Any]:
    """Build a standardized dictionary for a crawl source."""
    return {
        "id": str(source.id),
        "name": source.name,
        "source_type": "crawl",
        "domain": source.domain,
        "base_url": source.start_urls[0] if source.start_urls else "",
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
        "documents_count": len(source.documents),
        "snippets_count": snippet_count,
    }


def _build_upload_source_dict(source: UploadJob, snippet_count: int) -> dict[str, Any]:
    """Build a standardized dictionary for an upload source."""
    return {
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
    }


@router.get("/sources")
async def get_sources(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get paginated sources (completed crawl jobs and upload jobs)."""
    result = []

    # Get completed crawl jobs with pagination
    crawl_sources = db.query(CrawlJob).filter_by(status='completed').offset(offset).limit(limit).all()
    crawl_ids = [str(source.id) for source in crawl_sources]
    crawl_snippet_counts = _get_snippet_counts_for_crawl_jobs(db, crawl_ids)

    for source in crawl_sources:
        snippet_count = crawl_snippet_counts.get(str(source.id), 0)
        result.append(_build_crawl_source_dict(source, snippet_count))

    # Get completed upload jobs with pagination
    upload_sources = db.query(UploadJob).filter_by(status='completed').offset(offset).limit(limit).all()
    upload_ids = [str(source.id) for source in upload_sources]
    upload_snippet_counts = _get_snippet_counts_for_upload_jobs(db, upload_ids)

    for source in upload_sources:
        snippet_count = upload_snippet_counts.get(str(source.id), 0)
        result.append(_build_upload_source_dict(source, snippet_count))

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
    query: str | None = Query(None, description="Search query for fuzzy matching"),
    min_snippets: int | None = Query(None, ge=0, description="Minimum snippet count"),
    max_snippets: int | None = Query(None, ge=0, description="Maximum snippet count"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Search sources with fuzzy matching and snippet count filtering."""

    # Treat empty string as None
    if query == '' or query is None:
        # If no query, get all sources with snippet filtering
        result = []

        # Get all completed crawl jobs
        crawl_sources = db.query(CrawlJob).filter_by(status='completed').all()
        crawl_ids = [str(source.id) for source in crawl_sources]
        crawl_snippet_counts = _get_snippet_counts_for_crawl_jobs(db, crawl_ids)

        for source in crawl_sources:
            snippet_count = crawl_snippet_counts.get(str(source.id), 0)

            # Apply snippet filter
            if min_snippets is not None and snippet_count < min_snippets:
                continue
            if max_snippets is not None and snippet_count > max_snippets:
                continue

            source_dict = _build_crawl_source_dict(source, snippet_count)
            source_dict['match_score'] = None
            result.append(source_dict)

        # Get all completed upload jobs
        upload_sources = db.query(UploadJob).filter_by(status='completed').all()
        upload_ids = [str(source.id) for source in upload_sources]
        upload_snippet_counts = _get_snippet_counts_for_upload_jobs(db, upload_ids)

        for source in upload_sources:
            snippet_count = upload_snippet_counts.get(str(source.id), 0)

            # Apply snippet filter
            if min_snippets is not None and snippet_count < min_snippets:
                continue
            if max_snippets is not None and snippet_count > max_snippets:
                continue

            source_dict = _build_upload_source_dict(source, snippet_count)
            source_dict['match_score'] = None
            result.append(source_dict)

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
    
    # Collect IDs by type for batch fetching
    crawl_ids = []
    upload_ids = []
    filtered_libraries = []
    
    for lib in libraries:
        # Apply snippet count filter
        if min_snippets is not None and lib['snippet_count'] < min_snippets:
            continue
        if max_snippets is not None and lib['snippet_count'] > max_snippets:
            continue
        
        # Collect IDs for batch fetching
        if lib['source_type'] == 'crawl':
            crawl_ids.append(lib['library_id'])
        else:
            upload_ids.append(lib['library_id'])
        
        filtered_libraries.append(lib)
    
    # Batch fetch all needed sources (2 queries instead of N)
    crawl_jobs = _batch_get_crawl_jobs(db, crawl_ids) if crawl_ids else {}
    upload_jobs = _batch_get_upload_jobs(db, upload_ids) if upload_ids else {}
    
    # Build sources using pre-fetched data
    for lib in filtered_libraries:
        if lib['source_type'] == 'crawl':
            crawl_source = crawl_jobs.get(lib['library_id'])
            if crawl_source:
                source_dict = _build_crawl_source_dict(crawl_source, lib['snippet_count'])
                source_dict['match_score'] = lib.get('similarity_score', 0.0)
                sources.append(source_dict)
        else:
            upload_source = upload_jobs.get(lib['library_id'])
            if upload_source:
                source_dict = _build_upload_source_dict(upload_source, lib['snippet_count'])
                source_dict['match_score'] = lib.get('similarity_score', 0.0)
                sources.append(source_dict)

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
async def get_source(source_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get a specific source (crawl job or upload job)."""
    # Try crawl job first
    crawl_source = db.query(CrawlJob).filter_by(id=source_id).first()
    if crawl_source:
        # Get snippet count efficiently
        snippet_counts = _get_snippet_counts_for_crawl_jobs(db, [source_id])
        snippet_count = snippet_counts.get(source_id, 0)
        return _build_crawl_source_dict(crawl_source, snippet_count)

    # Try upload job
    upload_source = db.query(UploadJob).filter_by(id=source_id).first()
    if upload_source:
        # Get snippet count efficiently
        snippet_counts = _get_snippet_counts_for_upload_jobs(db, [source_id])
        snippet_count = snippet_counts.get(source_id, 0)
        return _build_upload_source_dict(upload_source, snippet_count)

    raise HTTPException(status_code=404, detail="Source not found")


@router.get("/sources/{source_id}/documents")
async def get_source_documents(
    source_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
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
    query: str | None = Query(None),
    language: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
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
            source=source.name if hasattr(source, 'name') else None,
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
async def get_source_languages(source_id: str, db: Session = Depends(get_db)) -> dict[str, list[dict[str, Any]]]:
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


@router.get("/documents/{document_id}/snippets")
async def get_document_snippets(
    document_id: int,
    query: str | None = Query(None),
    language: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get paginated code snippets for a specific document with optional search."""
    # Get the document
    document = db.query(Document).filter_by(id=document_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # If query is provided, use the search functionality
    if query:
        searcher = CodeSearcher(db)
        # Search within this document's snippets
        snippet_query = db.query(CodeSnippet).filter(CodeSnippet.document_id == document_id)

        if language:
            snippet_query = snippet_query.filter(CodeSnippet.language == language)

        # Apply text search
        search_filter = or_(
            CodeSnippet.title.ilike(f"%{query}%"),
            CodeSnippet.description.ilike(f"%{query}%"),
            CodeSnippet.code_content.ilike(f"%{query}%")
        )
        snippet_query = snippet_query.filter(search_filter)

        total = snippet_query.count()
        snippets = snippet_query.order_by(CodeSnippet.created_at.desc()).offset(offset).limit(limit).all()
    else:
        # Build query for snippets
        snippet_query = db.query(CodeSnippet).filter(CodeSnippet.document_id == document_id)

        if language:
            snippet_query = snippet_query.filter(CodeSnippet.language == language)

        total = snippet_query.count()
        snippets = snippet_query.order_by(CodeSnippet.created_at.desc()).offset(offset).limit(limit).all()

    # Get source info
    source_info = None
    if document.crawl_job_id:
        source = db.query(CrawlJob).filter_by(id=document.crawl_job_id).first()
        if source:
            source_info = {
                "id": str(source.id),
                "name": source.name,
                "type": "crawl"
            }
    elif document.upload_job_id:
        source = db.query(UploadJob).filter_by(id=document.upload_job_id).first()
        if source:
            source_info = {
                "id": str(source.id),
                "name": source.name,
                "type": "upload"
            }

    return {
        "document": {
            "id": document.id,
            "url": document.url,
            "title": document.title or "Untitled",
            "crawl_depth": document.crawl_depth,
            "created_at": document.created_at.isoformat(),
        },
        "source": source_info,
        "snippets": [
            {
                "id": str(snippet.id),
                "title": snippet.title,
                "code": snippet.code_content,
                "language": snippet.language,
                "description": snippet.description,
                "source_url": snippet.source_url or document.url,
                "document_title": document.title,
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


@router.delete("/sources/bulk")
async def delete_sources_bulk(source_ids: list[str], db: Session = Depends(get_db)) -> dict[str, Any]:
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


class DeleteFilteredRequest(BaseModel):
    """Request model for deleting filtered sources."""
    min_snippets: int | None = Field(None, ge=0, description="Minimum snippet count")
    max_snippets: int | None = Field(None, ge=0, description="Maximum snippet count")
    query: str | None = Field(None, description="Search query for name/URL matching")


@router.post("/sources/bulk/delete-filtered")
async def delete_filtered_sources(
    request: DeleteFilteredRequest,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Delete all sources matching the filter criteria."""
    sources_to_delete = []
    
    # Get all completed crawl jobs
    crawl_sources = db.query(CrawlJob).filter_by(status='completed').all()
    crawl_ids = [str(source.id) for source in crawl_sources]
    crawl_snippet_counts = _get_snippet_counts_for_crawl_jobs(db, crawl_ids)
    
    for source in crawl_sources:
        snippet_count = crawl_snippet_counts.get(str(source.id), 0)
        
        # Apply snippet filter
        if request.min_snippets is not None and snippet_count < request.min_snippets:
            continue
        if request.max_snippets is not None and snippet_count > request.max_snippets:
            continue
            
        # Apply query filter if provided
        if request.query:
            query_lower = request.query.lower()
            if not (query_lower in source.name.lower() or 
                    any(query_lower in url.lower() for url in (source.start_urls or []))):
                continue
        
        sources_to_delete.append(source)
    
    # Get all completed upload jobs
    upload_sources = db.query(UploadJob).filter_by(status='completed').all()
    upload_ids = [str(source.id) for source in upload_sources]
    upload_snippet_counts = _get_snippet_counts_for_upload_jobs(db, upload_ids)
    
    for source in upload_sources:
        snippet_count = upload_snippet_counts.get(str(source.id), 0)
        
        # Apply snippet filter
        if request.min_snippets is not None and snippet_count < request.min_snippets:
            continue
        if request.max_snippets is not None and snippet_count > request.max_snippets:
            continue
            
        # Apply query filter if provided
        if request.query:
            query_lower = request.query.lower()
            if not query_lower in source.name.lower():
                continue
        
        sources_to_delete.append(source)
    
    deleted_count = len(sources_to_delete)
    
    if deleted_count == 0:
        return {
            "message": "No sources found matching the filter criteria",
            "deleted_count": 0
        }
    
    # Delete all matching sources (cascade will handle documents and snippets)
    for source in sources_to_delete:
        db.delete(source)
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {deleted_count} source(s) matching filter criteria",
        "deleted_count": deleted_count
    }


@router.post("/sources/bulk/count-filtered")
async def count_filtered_sources(
    request: DeleteFilteredRequest,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Count all sources matching the filter criteria (useful for confirmation dialogs)."""
    matching_count = 0
    
    # Get all completed crawl jobs
    crawl_sources = db.query(CrawlJob).filter_by(status='completed').all()
    crawl_ids = [str(source.id) for source in crawl_sources]
    crawl_snippet_counts = _get_snippet_counts_for_crawl_jobs(db, crawl_ids)
    
    for source in crawl_sources:
        snippet_count = crawl_snippet_counts.get(str(source.id), 0)
        
        # Apply snippet filter
        if request.min_snippets is not None and snippet_count < request.min_snippets:
            continue
        if request.max_snippets is not None and snippet_count > request.max_snippets:
            continue
            
        # Apply query filter if provided
        if request.query:
            query_lower = request.query.lower()
            if not (query_lower in source.name.lower() or 
                    any(query_lower in url.lower() for url in (source.start_urls or []))):
                continue
        
        matching_count += 1
    
    # Get all completed upload jobs
    upload_sources = db.query(UploadJob).filter_by(status='completed').all()
    upload_ids = [str(source.id) for source in upload_sources]
    upload_snippet_counts = _get_snippet_counts_for_upload_jobs(db, upload_ids)
    
    for source in upload_sources:
        snippet_count = upload_snippet_counts.get(str(source.id), 0)
        
        # Apply snippet filter
        if request.min_snippets is not None and snippet_count < request.min_snippets:
            continue
        if request.max_snippets is not None and snippet_count > request.max_snippets:
            continue
            
        # Apply query filter if provided
        if request.query:
            query_lower = request.query.lower()
            if not query_lower in source.name.lower():
                continue
        
        matching_count += 1
    
    return {
        "count": matching_count,
        "filters": {
            "min_snippets": request.min_snippets,
            "max_snippets": request.max_snippets,
            "query": request.query
        }
    }


@router.patch("/sources/{source_id}")
async def update_source_name(
    source_id: str,
    request: UpdateSourceRequest,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
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
    source.name = request.name  # type: ignore[assignment]
    source.updated_at = datetime.utcnow()  # type: ignore[assignment]
    db.commit()

    # Return updated source info using helper functions
    if is_upload_job:
        snippet_counts = _get_snippet_counts_for_upload_jobs(db, [source_id])
        snippet_count = snippet_counts.get(source_id, 0)
        return _build_upload_source_dict(source, snippet_count)
    else:
        snippet_counts = _get_snippet_counts_for_crawl_jobs(db, [source_id])
        snippet_count = snippet_counts.get(source_id, 0)
        return _build_crawl_source_dict(source, snippet_count)


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
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
) -> dict[str, Any]:
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
            name=original_job.name,  # type: ignore[arg-type]
            start_urls=original_job.start_urls,  # type: ignore[arg-type]
            max_depth=original_job.max_depth,  # type: ignore[arg-type]
            domain_filter=original_job.domain if original_job.domain else None,  # type: ignore[arg-type]
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
