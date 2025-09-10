"""Content hash checking utilities for avoiding redundant LLM extraction."""



from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import CodeSnippet, Document


def check_content_hash(session: Session, url: str, content_hash: str) -> tuple[bool, int]:
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


def get_existing_document_info(session: Session, url: str) -> tuple[int, str, int] | None:
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

    return int(existing_doc.id), str(existing_doc.content_hash or ""), int(snippet_count)  # type: ignore


def find_duplicate_snippet_in_source(
    session: Session,
    code_hash: str,
    document: Document
) -> CodeSnippet | None:
    """Find duplicate snippet within the same source (crawl or upload job).
    
    This ensures that duplicate detection is scoped to each source, allowing
    the same code to exist in different sources (e.g., different versions of
    documentation or different libraries).
    
    Args:
        session: Database session
        code_hash: Hash of the code content
        document: Document that contains or will contain the snippet
        
    Returns:
        Existing CodeSnippet if duplicate found in same source, None otherwise
    """
    # Build query to find snippets with same hash
    query = (
        session.query(CodeSnippet)
        .join(Document)
        .filter(CodeSnippet.code_hash == code_hash)
    )
    
    # Add source-specific filtering
    if document.crawl_job_id:
        # Check within same crawl job
        query = query.filter(Document.crawl_job_id == document.crawl_job_id)
    elif document.upload_job_id:
        # Check within same upload job
        query = query.filter(Document.upload_job_id == document.upload_job_id)
    else:
        # Orphan document - check against other orphans
        # This shouldn't normally happen but we handle it for completeness
        query = query.filter(
            Document.crawl_job_id.is_(None),
            Document.upload_job_id.is_(None)
        )
    
    return query.first()
