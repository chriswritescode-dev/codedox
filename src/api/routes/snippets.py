"""API routes for snippet operations including formatting."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...database.models import CodeSnippet, CrawlJob, Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snippets", tags=["snippets"])


@router.get("/{snippet_id}")
async def get_snippet(snippet_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get details of a specific code snippet."""
    try:
        snippet = db.query(CodeSnippet)\
            .options(
                joinedload(CodeSnippet.document).joinedload(Document.crawl_job),
                joinedload(CodeSnippet.document).joinedload(Document.upload_job)
            )\
            .filter_by(id=snippet_id)\
            .first()

        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet not found")

        result = snippet.to_dict()

        if snippet.document:
            if snippet.document.crawl_job:
                result['source_id'] = str(snippet.document.crawl_job.id)
                result['source_name'] = snippet.document.crawl_job.name
            elif snippet.document.upload_job:
                result['source_id'] = str(snippet.document.upload_job.id)
                result['source_name'] = snippet.document.upload_job.name

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get snippet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeleteMatchesRequest(BaseModel):
    """Request model for deleting matching snippets."""
    source_id: str = Field(..., description="Source ID to delete from")
    query: str | None = Field(None, description="Search query to match snippets")
    language: str | None = Field(None, description="Language filter")


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


