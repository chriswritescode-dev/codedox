"""Shared utilities for upload functionality."""

import hashlib
import logging
import re

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.crawler.extraction_models import SimpleCodeBlock
from src.database.models import CodeSnippet, Document

logger = logging.getLogger(__name__)
settings = get_settings()


def is_binary_content(content: bytes, sample_size: int | None = None) -> bool:
    """Check if content appears to be binary.

    Args:
        content: The content bytes to check
        sample_size: Number of bytes to check (default from config)

    Returns:
        True if content appears to be binary, False otherwise
    """
    if sample_size is None:
        sample_size = settings.upload.binary_check_bytes

    return b"\x00" in content[:sample_size]


def extract_title_from_markdown(content: str, max_lines: int | None = None) -> str | None:
    """Extract the first H1 title from markdown content.

    Args:
        content: Markdown content to search
        max_lines: Maximum number of lines to search (default from config)

    Returns:
        The H1 title if found, None otherwise
    """
    if max_lines is None:
        max_lines = settings.upload.title_search_lines

    lines = content.split("\n")[:max_lines]

    for line in lines:
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()

    return None


def resolve_document_title(explicit_title: str | None, content: str, fallback_name: str) -> str:
    """Resolve document title with priority: explicit -> H1 from markdown -> fallback name.

    Args:
        explicit_title: Explicitly provided title (highest priority)
        content: Markdown content to search for H1
        fallback_name: Fallback name if no title found

    Returns:
        The resolved title
    """
    if explicit_title:
        return explicit_title

    extracted_title = extract_title_from_markdown(content)
    return extracted_title or fallback_name


async def validate_and_read_file(
    file: UploadFile,
    max_file_size: int | None = None,
    allowed_extensions: tuple | None = None,
) -> tuple[str, str]:
    """Validate file and return content and filename without extension.

    Args:
        file: The uploaded file
        max_file_size: Maximum file size in bytes (default from config)
        allowed_extensions: Tuple of allowed file extensions (default: .md, .markdown, .txt)

    Returns:
        Tuple of (content, filename_without_ext)

    Raises:
        HTTPException: If file validation fails
    """
    if max_file_size is None:
        max_file_size = settings.upload.max_file_size

    if allowed_extensions is None:
        allowed_extensions = (".md", ".markdown", ".txt")

    # Check file extension
    if not file.filename or not file.filename.endswith(allowed_extensions):
        raise HTTPException(
            status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are allowed"
        )

    # Check file size
    content_bytes = await file.read()
    if len(content_bytes) > max_file_size:
        raise HTTPException(
            status_code=400, detail=f"File size exceeds {max_file_size / (1024 * 1024):.1f}MB limit"
        )

    # Check for binary content
    if is_binary_content(content_bytes):
        raise HTTPException(status_code=400, detail="File appears to be binary, not a text file")

    # Decode content
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

    # Get filename without extension
    filename_without_ext = file.filename.rsplit(".", 1)[0]

    return content, filename_without_ext


def extract_code_blocks_from_markdown(content: str) -> list[SimpleCodeBlock]:
    """Extract code blocks from markdown content.

    Args:
        content: Markdown content

    Returns:
        List of CodeBlock objects
    """
    code_blocks = []

    # Regex to match code blocks with optional language
    pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    for language, code in matches:
        if code.strip():
            code_blocks.append(
                SimpleCodeBlock(
                    code=code.strip(),
                    language=language or "text",
                    title=None,
                    description=None,
                )
            )

    return code_blocks


def process_code_snippets(
    code_blocks: list[SimpleCodeBlock],
    document: Document,
    source_url: str,
    db: Session,
    batch_snippets: dict | None = None,
    file_context: str | None = None,
) -> int:
    """Process and store code snippets, avoiding duplicates.

    Args:
        code_blocks: List of code blocks to process
        document: Parent document
        source_url: Source URL for the snippets
        db: Database session
        batch_snippets: Optional dict to track snippets in batch
        file_context: Optional context about the file (for titles)

    Returns:
        Number of snippets created
    """
    snippets_created = 0

    if batch_snippets is None:
        batch_snippets = {}

    for block in code_blocks:
        # Calculate code hash
        code_hash = hashlib.md5(block.code.encode()).hexdigest()

        # Check if snippet already exists in batch
        if code_hash in batch_snippets:
            logger.info(f"Skipping duplicate within batch: {code_hash}")
            continue

        # Check if snippet already exists in database
        existing_snippet = db.query(CodeSnippet).filter(CodeSnippet.code_hash == code_hash).first()

        if existing_snippet:
            logger.info(f"Skipping existing code snippet with hash {code_hash}")
            continue

        # Create snippet
        snippet = CodeSnippet(
            document_id=document.id,
            title=block.title or file_context or "Code Block",
            description=block.description or "",
            language=block.language or "text",
            code_content=block.code,
            code_hash=code_hash,
            snippet_type="code",
            source_url=source_url,
        )

        db.add(snippet)
        batch_snippets[code_hash] = snippet
        snippets_created += 1

    return snippets_created
