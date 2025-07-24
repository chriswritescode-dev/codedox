"""Content hash checking utilities for avoiding redundant LLM extraction."""

from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Document, CodeSnippet


def check_content_hash(session: Session, url: str, content_hash: str) -> Tuple[bool, int]:
    """Check if content with the given hash already exists for URL.
    
    Args:
        session: Database session
        url: Document URL
        content_hash: MD5 hash of content
        
    Returns:
        Tuple of (content_unchanged, snippet_count)
        - content_unchanged: True if content hash matches existing document
        - snippet_count: Number of snippets in existing document (0 if not found)
    """
    # Find existing document by URL
    existing_doc = session.query(Document).filter_by(url=url).first()
    
    if not existing_doc:
        return False, 0
    
    # Check if content hash matches
    if existing_doc.content_hash != content_hash:
        return False, 0
    
    # Content unchanged - get snippet count
    snippet_count = session.query(func.count(CodeSnippet.id))\
        .filter(CodeSnippet.document_id == existing_doc.id)\
        .scalar() or 0
    
    return True, snippet_count


def get_existing_document_info(session: Session, url: str) -> Optional[Tuple[int, str, int]]:
    """Get existing document info by URL.
    
    Args:
        session: Database session
        url: Document URL
        
    Returns:
        Tuple of (document_id, content_hash, snippet_count) or None if not found
    """
    existing_doc = session.query(Document).filter_by(url=url).first()
    
    if not existing_doc:
        return None
    
    # Get snippet count
    snippet_count = session.query(func.count(CodeSnippet.id))\
        .filter(CodeSnippet.document_id == existing_doc.id)\
        .scalar() or 0
    
    return existing_doc.id, existing_doc.content_hash, snippet_count