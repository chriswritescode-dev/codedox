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


@router.get("/{snippet_id}")
async def get_snippet(snippet_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get details of a specific code snippet."""
    try:
        snippet = db.query(CodeSnippet).filter_by(id=snippet_id).first()
        
        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet not found")
        
        return snippet.to_dict()
        
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
        
        # Format the code
        original_code = snippet.code_content
        formatted_code = formatter.format(original_code, snippet.language)
        
        # Check if formatting changed the code
        changed = original_code != formatted_code
        
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
            saved=saved
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