"""Shared utilities for upload functionality."""

import hashlib
import logging
import os
from typing import Any, Dict, List

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.crawler.extraction_models import SimpleCodeBlock
from src.database.models import CodeSnippet, Document

logger = logging.getLogger(__name__)
settings = get_settings()


class FileValidationRules:
    """Centralized file validation configuration."""

    ALLOWED_EXTENSIONS = (".md", ".markdown", ".txt", ".mdx", ".html", ".htm")
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

    @staticmethod
    def extract_from_content(content: str, max_lines: int | None = None) -> str | None:
        """Extract title from markdown content (H1 heading).

        Args:
            content: Markdown content to search
            max_lines: Maximum number of lines to search (default from config)

        Returns:
            The H1 title if found, None otherwise
        """
        if max_lines is None:
            max_lines = getattr(settings.upload, "title_search_lines", 10)

        lines = content.split("\n")[:max_lines]
        for line in lines:
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
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
        """Resolve title with priority: explicit -> H1 -> URL.

        Args:
            explicit_title: Explicitly provided title (highest priority)
            content: Markdown content to search for H1
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


# Keep legacy functions for backward compatibility
def extract_title_from_markdown(content: str, max_lines: int | None = None) -> str | None:
    """Legacy function - use TitleExtractor.extract_from_content instead."""
    return TitleExtractor.extract_from_content(content, max_lines)


def resolve_document_title(explicit_title: str | None, content: str, fallback_name: str) -> str:
    """Legacy function - use TitleExtractor.resolve instead."""
    if explicit_title:
        return explicit_title
    content_title = TitleExtractor.extract_from_content(content)
    return content_title or fallback_name


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


class MarkdownCodeExtractor:
    @classmethod
    def extract_blocks(
        cls, content: str, source_url: str | None = None, include_context: bool = False
    ) -> list[SimpleCodeBlock]:
        """Extract code blocks from markdown and return as SimpleCodeBlock objects.
        
        Args:
            content: Markdown content
            source_url: Source URL for the blocks
            include_context: Whether to include surrounding context
            
        Returns:
            List of SimpleCodeBlock objects
        """
        extractor = cls()
        raw_blocks = extractor.extract_code_blocks(content)
        
        result = []
        for block in raw_blocks:
            metadata = {}
            
            # Add context if requested
            if include_context:
                # Find position of this block in content
                block_start = content.find(block['content'])
                if block_start > 0:
                    context = cls._extract_context(content, block_start, before=True, max_chars=300)
                    if context:
                        metadata['context_before'] = context
            
            # Add block type to metadata
            metadata['block_type'] = block.get('type', 'code')
            
            result.append(
                SimpleCodeBlock(
                    code=block['content'],
                    language=block.get('language'),
                    source_url=source_url,
                    container_type=block.get('type', 'code'),
                    metadata=metadata,
                )
            )
        
        return result
    
    def extract_code_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract both fenced and indented code blocks from markdown content."""
        blocks = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            # Check for fenced code block (``` or ~~~)
            if lines[i].startswith('```'): 
                fence = lines[i][:3]
                language = lines[i][3:].strip() or None
                code_lines = []
                i += 1
                
                # Collect lines until closing fence
                while i < len(lines) and not lines[i].startswith(fence):
                    code_lines.append(lines[i])
                    i += 1
                
                if code_lines:
                    # Filter out standalone --- separators (common in MongoDB docs)
                    filtered_lines = []
                    for line in code_lines:
                        # Skip lines that are just --- (with optional whitespace)
                        if line.strip() != '---':
                            filtered_lines.append(line)
                    
                    if filtered_lines:  # Only add if there's content after filtering
                        blocks.append({
                            'content': '\n'.join(filtered_lines),
                            'language': language,
                            'type': 'fenced'
                        })
                i += 1  # Skip closing fence
                continue
            
            # Check for indented code block (4 spaces or tab)
            if lines[i].startswith('    ') or lines[i].startswith('\t'):
                code_lines = []
                
                # Collect all consecutive indented lines
                while i < len(lines):
                    if lines[i].startswith('    '):
                        # Remove exactly 4 spaces
                        code_lines.append(lines[i][4:])
                    elif lines[i].startswith('\t'):
                        # Remove one tab
                        code_lines.append(lines[i][1:])
                    elif lines[i].strip() == '':
                        # Check if next line is also indented (blank line within code)
                        if i + 1 < len(lines) and (
                            lines[i + 1].startswith('    ') or 
                            lines[i + 1].startswith('\t')
                        ):
                            code_lines.append('')  # Keep blank line
                        else:
                            break  # End of indented block
                    else:
                        break  # Non-indented line ends the block
                    i += 1
                
                # Clean up and add block if non-empty
                if code_lines:
                    # Remove trailing empty lines
                    while code_lines and code_lines[-1] == '':
                        code_lines.pop()
                    
                    if code_lines:  # Check again after cleanup
                        blocks.append({
                            'content': '\n'.join(code_lines),
                            'language': None,  # Indented blocks don't have language
                            'type': 'indented'
                        })
                continue
            
            i += 1
        
        return blocks

    @classmethod
    def _extract_context(
        cls, content: str, position: int, before: bool = True, max_chars: int = 200
    ) -> str:
        """Extract context around a position."""
        if before:
            start = max(0, position - max_chars)
            context = content[start:position].strip()
        else:
            end = min(len(content), position + max_chars)
            context = content[position:end].strip()
        return context


# Keep legacy function for backward compatibility
def extract_code_blocks_from_markdown(content: str) -> list[SimpleCodeBlock]:
    """Legacy function - use MarkdownCodeExtractor.extract_blocks instead."""
    return MarkdownCodeExtractor.extract_blocks(content)


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
