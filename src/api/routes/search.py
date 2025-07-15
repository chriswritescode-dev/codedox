"""Search and snippet routes."""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db, CodeSearcher
from ...database.models import CodeSnippet

logger = logging.getLogger(__name__)
router = APIRouter()


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