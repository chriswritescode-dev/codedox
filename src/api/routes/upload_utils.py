"""Shared utilities for upload functionality."""

import hashlib
import logging
import os

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.constants import ALL_SUPPORTED_EXTENSIONS
from src.crawler.extractors.models import ExtractedCodeBlock
from src.database.models import CodeSnippet, Document

logger = logging.getLogger(__name__)
settings = get_settings()


class FileValidationRules:
    """Centralized file validation configuration."""

    ALLOWED_EXTENSIONS = ALL_SUPPORTED_EXTENSIONS
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB
    BINARY_CHECK_BYTES = 8192


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


class TitleExtractor:
    """Centralized title extraction utilities."""

    RST_MARKER_CHARS = "=-~`#*+^"

    @staticmethod
    def _is_rst_marker_line(line: str) -> tuple[bool, str | None]:
        """Check if line is an RST section marker.
        
        Args:
            line: Line to check
            
        Returns:
            Tuple of (is_marker, marker_char) where marker_char is the character used
        """
        stripped = line.strip()
        if not stripped:
            return False, None
        
        if all(c in TitleExtractor.RST_MARKER_CHARS for c in stripped):
            return True, stripped[0]
        return False, None

    @staticmethod
    def extract_from_content(content: str, max_lines: int | None = None) -> str | None:
        """Extract title from markdown or RST content.

        Args:
            content: Markdown or RST content to search
            max_lines: Maximum number of lines to search (default from config)

        Returns:
            The title if found, None otherwise
        """
        if max_lines is None:
            max_lines = getattr(settings.upload, "title_search_lines", 10)

        lines = content.split("\n")[:max_lines]
        
        # Check for Markdown H1 heading
        for line in lines:
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
        
        # Check for RST title (text with overline and underline using =, -, ~, etc.)
        for i in range(len(lines) - 2):
            line1 = lines[i].strip()
            line2 = lines[i + 1].strip()
            line3 = lines[i + 2].strip() if i + 2 < len(lines) else ""
            
            # Check for RST title with overline and underline
            is_marker1, char1 = TitleExtractor._is_rst_marker_line(line1)
            is_marker3, char3 = TitleExtractor._is_rst_marker_line(line3)
            
            if (is_marker1 and is_marker3 and
                char1 == char3 and
                len(line1) >= len(line2) and
                len(line3) >= len(line2) and
                line2):
                return line2.strip()
            
            # Check for RST title with just underline
            is_marker2, _ = TitleExtractor._is_rst_marker_line(line2)
            if (line1 and is_marker2 and
                not line1.startswith("#") and  # Not a markdown heading
                len(line2) >= len(line1)):
                return line1.strip()
        
        return None

    @staticmethod
    def extract_from_url(url: str) -> str:
        """Extract title from URL path.

        Args:
            url: URL to extract title from

        Returns:
            Extracted title or 'Untitled Document'
        """
        if url.startswith("file://"):
            return os.path.basename(url[7:])
        elif url.startswith("upload://"):
            parts = url[9:].split("/", 1)
            if len(parts) > 1:
                filename = parts[1]
                if "." in filename:
                    filename = filename.rsplit(".", 1)[0]
                return filename
            return parts[0] if parts else "Untitled Document"
        return "Untitled Document"

    @staticmethod
    def resolve(explicit_title: str | None, content: str, url: str) -> str:
        """Resolve title with priority: explicit -> content title -> URL.

        Args:
            explicit_title: Explicitly provided title (highest priority)
            content: Markdown or RST content to search for title
            url: URL to extract fallback title from

        Returns:
            The resolved title
        """
        if explicit_title:
            return explicit_title

        content_title = TitleExtractor.extract_from_content(content)
        if content_title:
            return content_title

        return TitleExtractor.extract_from_url(url)




async def validate_and_read_file(
    file: UploadFile,
    max_file_size: int | None = None,
    allowed_extensions: tuple | None = None,
) -> tuple[str, str]:
    """Validate file and return content and filename without extension.

    Args:
        file: The uploaded file
        max_file_size: Maximum file size in bytes (default from config)
        allowed_extensions: Tuple of allowed file extensions (default from constants)

    Returns:
        Tuple of (content, filename_without_ext)

    Raises:
        HTTPException: If file validation fails
    """
    if max_file_size is None:
        max_file_size = settings.upload.max_file_size

    if allowed_extensions is None:
        allowed_extensions = ALL_SUPPORTED_EXTENSIONS

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


async def extract_code_blocks_by_type(
    content: str, content_type: str, source_url: str | None = None, batch_size: int = 5
) -> list[ExtractedCodeBlock]:
    """Extract code blocks based on content type using the factory pattern.
    
    Args:
        content: The content to extract from
        content_type: The type of content (markdown, restructuredtext, etc.)
        source_url: Optional source URL for the blocks
        batch_size: Number of blocks to process before yielding control
        
    Returns:
        List of ExtractedCodeBlock objects
    """
    from src.crawler.extractors.factory import create_extractor
    
    # Map content types to extractor types
    extractor_type = content_type
    if content_type == 'text':
        extractor_type = 'markdown'  # Default text to markdown
    
    extractor = create_extractor(content_type=extractor_type)
    if not extractor:
        # Fall back to markdown if type is unknown
        extractor = create_extractor(content_type='markdown')
    
    # Extract blocks
    blocks = await extractor.extract_blocks(content, batch_size=batch_size)
    
    # Set source_url for each block
    if source_url:
        for block in blocks:
            block.source_url = source_url
    
    return blocks


class GitHubURLParser:
    """Centralized GitHub URL parsing utilities."""

    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str]:
        """Extract owner and repo from GitHub URL.

        Args:
            url: GitHub repository URL

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If URL is invalid
        """
        url = url.rstrip(".git")
        if url.startswith("git@"):
            url = url.replace("git@github.com:", "https://github.com/")

        # Handle various GitHub URL formats
        if "github.com" in url:
            parts = url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return parts[0], parts[1].rstrip("/")

        raise ValueError(f"Invalid GitHub URL: {url}")

    @staticmethod
    def generate_blob_url(repo_url: str, branch: str, path: str) -> str:
        """Generate GitHub blob URL for a file.

        Args:
            repo_url: Repository URL
            branch: Branch name
            path: File path in repository

        Returns:
            GitHub blob URL
        """
        owner, repo = GitHubURLParser.parse_repo_url(repo_url)
        # Ensure path doesn't start with /
        path = path.lstrip("/")
        return f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"

    @staticmethod
    def generate_raw_url(repo_url: str, branch: str, path: str) -> str:
        """Generate GitHub raw content URL.

        Args:
            repo_url: Repository URL
            branch: Branch name
            path: File path in repository

        Returns:
            GitHub raw content URL
        """
        owner, repo = GitHubURLParser.parse_repo_url(repo_url)
        path = path.lstrip("/")
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


def process_code_snippets(
    code_blocks: list[ExtractedCodeBlock],
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
        code_hash = hashlib.md5(block.code_content.encode()).hexdigest()

        # Check if snippet already exists in batch
        if code_hash in batch_snippets:
            logger.info(f"Skipping duplicate within batch: {code_hash}")
            continue

        # Check if snippet already exists in the same source
        from ...database.content_check import find_duplicate_snippet_in_source
        existing_snippet = find_duplicate_snippet_in_source(db, code_hash, document)

        if existing_snippet:
            logger.info(f"Skipping existing code snippet with hash {code_hash}")
            continue

        # Create snippet
        snippet = CodeSnippet(
            document_id=document.id,
            title=block.title or file_context or "Code Block",
            description=block.description or "",
            language=block.language or "text",
            code_content=block.code_content,
            code_hash=code_hash,
            snippet_type="code",
            source_url=source_url,
        )

        db.add(snippet)
        batch_snippets[code_hash] = snippet
        snippets_created += 1

    return snippets_created
