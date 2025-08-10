"""API routes for snippet operations including formatting."""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...database.models import CodeSnippet, CrawlJob, Document
from ...crawler.code_formatter import CodeFormatter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snippets", tags=["snippets"])


class FormatSnippetRequest(BaseModel):
    """Request model for formatting a snippet."""
    save: bool = Field(default=False, description="Whether to save the formatted code")


class FormatSnippetResponse(BaseModel):
    """Response model for formatting a snippet."""
    original: str = Field(..., description="Original code")
    formatted: str = Field(..., description="Formatted code")
    language: str = Field(..., description="Detected language")
    changed: bool = Field(..., description="Whether formatting changed the code")
    saved: bool = Field(default=False, description="Whether the changes were saved")
    detected_language: Optional[str] = Field(None, description="Language detected from code patterns")
    formatter_used: Optional[str] = Field(None, description="Which formatter was used")


@router.get("/{snippet_id}")
async def get_snippet(snippet_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get details of a specific code snippet."""
    try:
        # Get snippet with document and source relationships
        snippet = db.query(CodeSnippet).filter_by(id=snippet_id).first()
        
        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet not found")
        
        result = snippet.to_dict()
        
        # Get source information through document relationship
        if snippet.document_id:
            document = db.query(Document).filter_by(id=snippet.document_id).first()
            if document:
                if document.crawl_job_id:
                    crawl_job = db.query(CrawlJob).filter_by(id=document.crawl_job_id).first()
                    if crawl_job:
                        result['source_id'] = str(crawl_job.id)
                        result['source_name'] = crawl_job.name
                elif document.upload_job_id:
                    from ...database.models import UploadJob
                    upload_job = db.query(UploadJob).filter_by(id=document.upload_job_id).first()
                    if upload_job:
                        result['source_id'] = str(upload_job.id)
                        result['source_name'] = upload_job.name
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get snippet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{snippet_id}/format", response_model=FormatSnippetResponse)
async def format_snippet(
    snippet_id: int,
    request: FormatSnippetRequest,
    db: Session = Depends(get_db)
) -> FormatSnippetResponse:
    """Format a single code snippet."""
    try:
        # Get the snippet
        snippet = db.query(CodeSnippet).filter_by(id=snippet_id).first()
        
        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet not found")
        
        # Initialize formatter
        formatter = CodeFormatter()
        
        # Format the code with detailed info
        original_code = snippet.code_content
        format_info = formatter.format_with_info(original_code, snippet.language)
        formatted_code = format_info['formatted']
        changed = format_info['changed']
        
        # Save if requested and changed
        saved = False
        if request.save and changed:
            snippet.code_content = formatted_code
            db.commit()
            saved = True
            logger.info(f"Saved formatted code for snippet {snippet_id}")
        
        return FormatSnippetResponse(
            original=original_code,
            formatted=formatted_code,
            language=snippet.language,
            changed=changed,
            saved=saved,
            detected_language=format_info['detected_language'],
            formatter_used=format_info['formatter_used']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to format snippet {snippet_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FormatSourceRequest(BaseModel):
    """Request model for formatting all snippets in a source."""
    save: bool = Field(default=False, description="Whether to save the formatted code")
    dry_run: bool = Field(default=True, description="Preview changes without saving")


class FormatSourceResponse(BaseModel):
    """Response model for formatting source snippets."""
    source_id: str = Field(..., description="Source ID")
    source_name: str = Field(..., description="Source name")
    total_snippets: int = Field(..., description="Total number of snippets")
    changed_snippets: int = Field(..., description="Number of snippets that would change")
    saved_snippets: int = Field(default=0, description="Number of snippets saved")
    preview: list[Dict[str, Any]] = Field(default_factory=list, description="Preview of changes (first 5)")


class DeleteMatchesRequest(BaseModel):
    """Request model for deleting matching snippets."""
    source_id: str = Field(..., description="Source ID to delete from")
    query: Optional[str] = Field(None, description="Search query to match snippets")
    language: Optional[str] = Field(None, description="Language filter")


class DeleteMatchesResponse(BaseModel):
    """Response model for delete matches operation."""
    deleted_count: int = Field(..., description="Number of snippets deleted")
    source_id: str = Field(..., description="Source ID")
    source_name: str = Field(..., description="Source name")


@router.post("/sources/{source_id}/delete-matches", response_model=DeleteMatchesResponse)
async def delete_matching_snippets(
    source_id: str,
    request: DeleteMatchesRequest,
    db: Session = Depends(get_db)
) -> DeleteMatchesResponse:
    """Delete snippets matching search criteria from a source."""
    try:
        # Get the source (crawl job)
        source = db.query(CrawlJob).filter_by(id=source_id).first()
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Build query to find snippet IDs to delete
        snippet_ids_query = db.query(CodeSnippet.id)\
            .join(Document)\
            .filter(Document.crawl_job_id == source_id)
        
        # Apply language filter if provided
        if request.language:
            snippet_ids_query = snippet_ids_query.filter(CodeSnippet.language == request.language)
        
        # Apply text search filter if provided
        if request.query:
            # Use PostgreSQL full-text search
            from sqlalchemy import func
            snippet_ids_query = snippet_ids_query.filter(
                func.to_tsvector('english', CodeSnippet.code_content).match(request.query) |
                func.to_tsvector('english', CodeSnippet.title).match(request.query) |
                func.to_tsvector('english', CodeSnippet.description).match(request.query)
            )
        
        # Get the IDs of snippets to delete
        snippet_ids_to_delete = [row[0] for row in snippet_ids_query.all()]
        deleted_count = len(snippet_ids_to_delete)
        
        logger.info(f"Found {deleted_count} snippets to delete from source {source_id}")
        
        # Delete only the specific snippets by ID to avoid cascade issues
        if snippet_ids_to_delete:
            db.query(CodeSnippet).filter(
                CodeSnippet.id.in_(snippet_ids_to_delete)
            ).delete(synchronize_session='fetch')
            db.commit()
            logger.info(f"Successfully deleted {deleted_count} snippets from source {source_id}")
        
        return DeleteMatchesResponse(
            deleted_count=deleted_count,
            source_id=source_id,
            source_name=source.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete matching snippets: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/{source_id}/format", response_model=FormatSourceResponse)
async def format_source_snippets(
    source_id: str,
    request: FormatSourceRequest,
    db: Session = Depends(get_db)
) -> FormatSourceResponse:
    """Format all snippets in a source."""
    try:
        # Get the source (crawl job)
        source = db.query(CrawlJob).filter_by(id=source_id).first()
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Get all snippets for the source (through Document relationship)
        snippets = db.query(CodeSnippet)\
            .join(Document)\
            .filter(Document.crawl_job_id == source_id)\
            .all()
        
        # Initialize formatter
        formatter = CodeFormatter()
        
        # Process snippets
        changed_count = 0
        saved_count = 0
        preview = []
        
        for snippet in snippets:
            original_code = snippet.code_content
            formatted_code = formatter.format(original_code, snippet.language)
            
            if original_code != formatted_code:
                changed_count += 1
                
                # Add to preview (first 5)
                if len(preview) < 5:
                    preview.append({
                        "snippet_id": snippet.id,
                        "title": snippet.title,
                        "language": snippet.language,
                        "original_preview": original_code[:200] + "..." if len(original_code) > 200 else original_code,
                        "formatted_preview": formatted_code[:200] + "..." if len(formatted_code) > 200 else formatted_code
                    })
                
                # Save if requested and not dry run
                if request.save and not request.dry_run:
                    snippet.code_content = formatted_code
                    saved_count += 1
        
        # Commit changes if any were saved
        if saved_count > 0:
            db.commit()
            logger.info(f"Saved formatted code for {saved_count} snippets in source {source_id}")
        
        return FormatSourceResponse(
            source_id=source_id,
            source_name=source.name,
            total_snippets=len(snippets),
            changed_snippets=changed_count,
            saved_snippets=saved_count,
            preview=preview
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to format source {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))