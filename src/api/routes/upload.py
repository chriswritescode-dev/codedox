"""Upload routes for processing markdown files."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...config import get_settings
from ...crawler.extractors.models import ExtractedCodeBlock
from ...crawler.github_processor import GitHubProcessor, GitHubRepoConfig
from ...crawler.llm_retry import LLMDescriptionGenerator
from ...database import get_db
from ...database.models import CodeSnippet, CrawlJob, Document
from .upload_utils import (
    TitleExtractor,
    is_binary_content,
    validate_and_read_file,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/upload", tags=["upload"])


@router.get("/config")
async def get_upload_config() -> dict[str, int]:
    """Get upload configuration limits."""
    settings = get_settings()
    return {
        "max_file_size": settings.upload.max_file_size,
        "max_total_size": settings.upload.max_total_size,
        "batch_size": 500,  # Recommended batch size for file uploads
    }


class UploadMarkdownRequest(BaseModel):
    """Request model for uploading markdown content."""

    content: str = Field(..., description="Markdown content to process")
    name: str = Field(..., description="Name for this upload batch")
    title: str | None = Field(None, description="Optional title")


def extract_code_blocks_with_context(content: str, url: str) -> list[ExtractedCodeBlock]:
    """Extract code blocks from markdown content with surrounding context."""
    from ...crawler.extractors.markdown import MarkdownCodeExtractor
    
    extractor = MarkdownCodeExtractor()
    blocks = extractor.extract_blocks(content)
    
    # Set source_url for each block
    for block in blocks:
        block.source_url = url
    
    return blocks


@router.post("/markdown")
async def upload_markdown(
    request: UploadMarkdownRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Upload and process markdown content."""
    try:
        # Create a crawl job for this upload
        job = CrawlJob(
            id=uuid4(),
            name=request.name,
            start_urls=[f"upload://{request.name}"],
            status="completed",
            max_depth=0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)

        # Create document
        content_hash = hashlib.md5(request.content.encode()).hexdigest()

        final_title = TitleExtractor.resolve(request.title, request.content, request.name)

        doc_url = f"upload://{request.name}/{final_title}"
        doc = Document(
            url=doc_url,
            title=final_title,
            content_type="markdown",
            content_hash=content_hash,
            markdown_content=request.content,
            crawl_job_id=job.id,
        )
        db.add(doc)
        db.flush()

        # Extract code blocks with context
        code_blocks = extract_code_blocks_with_context(request.content, doc_url)
        snippets_count = 0

        if code_blocks:
            # Initialize LLM generator
            llm_generator = LLMDescriptionGenerator()

            # Generate titles and descriptions using LLM
            if llm_generator.client:
                logger.info(f"Processing {len(code_blocks)} code blocks with LLM")
                enhanced_blocks = await llm_generator.generate_titles_and_descriptions_batch(
                    code_blocks, doc_url
                )
            else:
                logger.warning("LLM not available, using basic extraction")
                enhanced_blocks = code_blocks
                # Add fallback titles/descriptions
                for i, block in enumerate(enhanced_blocks):
                    if not block.title:
                        block.title = f"Code Block {i + 1}"
                    if not block.description:
                        block.description = (
                            f"{block.language or 'Code'} snippet from {request.name}"
                        )

            # Save enhanced code snippets
            for block in enhanced_blocks:
                # Calculate code hash
                code_hash = hashlib.md5(block.code_content.encode()).hexdigest()

                # Check if snippet already exists in the same source
                from ...database.content_check import find_duplicate_snippet_in_source
                existing_snippet = find_duplicate_snippet_in_source(db, code_hash, doc)

                if existing_snippet:
                    logger.info(f"Skipping duplicate code snippet with hash {code_hash}")
                    continue

                snippet = CodeSnippet(
                    document_id=doc.id,
                    title=block.title or "",
                    description=block.description or "",
                    language=block.language or "unknown",
                    code_content=block.code_content,
                    code_hash=code_hash,
                    snippet_type="code",
                    source_url=doc_url,
                    functions=[],
                    imports=[],
                    keywords=[],
                )
                db.add(snippet)
                snippets_count += 1

        # Update job stats
        job.snippets_extracted = snippets_count
        job.processed_pages = 1
        job.total_pages = 1

        db.commit()

        return {
            "status": "success",
            "document_id": str(doc.id),
            "snippets_count": snippets_count,
            "message": f"Successfully processed {request.name}",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    title: str | None = Form(None),
    max_concurrent: int | None = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload a markdown or HTML file for processing."""
    try:
        content_str, filename_without_ext = await validate_and_read_file(file)

        # Determine content type based on file extension
        from src.constants import get_content_type_for_extension
        
        content_type = get_content_type_for_extension(file.filename) if file.filename else "text"
        if not content_type:
            content_type = "text"  # Default fallback

        # For HTML files, use the UploadProcessor
        if content_type == "html":
            from ...crawler.upload_processor import UploadConfig, UploadProcessor

            processor = UploadProcessor()
            config = UploadConfig(
                name=name or title or filename_without_ext,
                files=[
                    {
                        "path": file.filename or "upload.html",
                        "content": content_str,
                        "source_url": f"upload://{file.filename or 'upload.html'}",
                        "content_type": "html",
                    }
                ],
                use_llm=settings.code_extraction.enable_llm_extraction,
                max_concurrent_files=max_concurrent or settings.crawling.max_concurrent_crawls,
            )

            job_id = await processor.process_upload(config)

            # Wait for completion or return job ID
            return {
                "status": "processing",
                "job_id": job_id,
                "message": f"HTML file upload started for {name or filename_without_ext}",
            }

        # Process markdown files as before
        final_name = name or title or filename_without_ext
        request = UploadMarkdownRequest(
            content=content_str,
            name=final_name,
            title=title,
        )

        return await upload_markdown(request, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files")
async def upload_files(
    files: list[UploadFile] = File(...),
    name: str | None = Form(None),
    title: str | None = Form(None),
    version: str | None = Form(None),
    max_concurrent: int | None = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload multiple markdown files and process them using the unified UploadProcessor.

    Note: Files should be sent in batches of 500 or less to avoid server limits.
    The frontend handles automatic batching for larger file sets.
    """
    try:
        settings = get_settings()

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Check total size and individual file sizes
        total_size = 0
        for file in files:
            if file.size and file.size > settings.upload.max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' exceeds {settings.upload.max_file_size / (1024 * 1024):.1f}MB limit",
                )
            if file.size:
                total_size += file.size

        if total_size > settings.upload.max_total_size:
            raise HTTPException(
                status_code=400,
                detail=f"Total file size ({total_size / (1024 * 1024):.1f}MB) exceeds {settings.upload.max_total_size / (1024 * 1024):.1f}MB limit",
            )

        # Prepare files data for UploadProcessor
        source_name = name or title or f"Upload {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        files_data = []

        # Read and validate all files first
        for file in files:
            try:
                # Validate file type
                if not file.filename:
                    continue

                from .upload_utils import FileValidationRules

                if not file.filename.endswith(FileValidationRules.ALLOWED_EXTENSIONS):
                    logger.warning(f"Skipping unsupported file: {file.filename}")
                    continue

                # Read file content
                try:
                    content = await file.read()
                    # Check if file is likely binary
                    if is_binary_content(content):
                        logger.warning(f"Skipping binary file: {file.filename}")
                        continue
                    content_str = content.decode("utf-8")
                except UnicodeDecodeError:
                    logger.warning(f"Skipping file with invalid encoding: {file.filename}")
                    continue

                # Determine content type based on file extension
                from src.constants import get_content_type_for_extension
                
                content_type = get_content_type_for_extension(file.filename) if file.filename else "text"
                if not content_type:
                    content_type = "text"  # Default fallback

                # Create URL for this file
                file_url = f"upload://{source_name}/{file.filename}"

                files_data.append(
                    {
                        "path": file.filename,
                        "content": content_str,
                        "source_url": file_url,
                        "content_type": content_type,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to read file {file.filename}: {e}")
                continue

        if not files_data:
            raise HTTPException(status_code=400, detail="No valid markdown files found in upload")

        # Use UploadProcessor for consistent processing (same as GitHub)
        from ...crawler.upload_processor import UploadConfig, UploadProcessor

        processor = UploadProcessor()
        upload_config = UploadConfig(
            name=source_name,
            files=files_data,
            version=version,
            metadata={
                "source": "file_upload",
                "upload_type": "batch",
            },
            extract_code_only=True,
            use_llm=settings.code_extraction.enable_llm_extraction,
            max_concurrent_files=max_concurrent or settings.crawling.max_concurrent_crawls,
        )

        # Process upload asynchronously (returns job_id immediately)
        job_id = await processor.process_upload(upload_config)

        return {
            "status": "processing",
            "job_id": job_id,
            "file_count": len(files_data),
            "message": f"Processing {len(files_data)} files",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload files: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class UploadGitHubRepoRequest(BaseModel):
    """Request model for uploading GitHub repository."""

    repo_url: str = Field(..., description="GitHub repository URL")
    name: str | None = Field(None, description="Name for this documentation source")
    version: str | None = Field(None, description="Version identifier for this upload")
    path: str | None = Field(None, description="Specific path within the repository to process")
    branch: str = Field("main", description="Git branch to clone")
    token: str | None = Field(None, description="GitHub personal access token for private repos")
    include_patterns: list[str] | None = Field(None, description="Include file patterns")
    exclude_patterns: list[str] | None = Field(None, description="Exclude file patterns")
    max_concurrent: int | None = Field(
        None, description="Maximum number of files to process concurrently"
    )


@router.post("/github")
async def upload_github_repo(
    request: UploadGitHubRepoRequest,
) -> dict[str, Any]:
    """Upload markdown documentation from a GitHub repository."""
    try:
        # Auto-generate name from repo URL if not provided
        if not request.name:
            import re

            match = re.search(r"/([^/]+?)(?:\.git)?$", request.repo_url)
            request.name = match.group(1) if match else "Repository Documentation"

        config = GitHubRepoConfig(
            repo_url=request.repo_url,
            name=request.name,
            version=request.version,
            path=request.path,
            branch=request.branch,
            token=request.token,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
            cleanup=True,
            max_concurrent=request.max_concurrent,
        )

        processor = GitHubProcessor()

        # Process repository asynchronously
        job_id = await processor.process_repository(config)

        return {
            "status": "processing",
            "job_id": job_id,
            "repository": request.repo_url,
            "name": request.name,
            "path": request.path,
            "branch": request.branch,
            "message": f"Processing repository {request.repo_url}",
        }

    except Exception as e:
        logger.error(f"Failed to process GitHub repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_upload_status(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get the status of any upload job (files or GitHub)."""
    from ...database import UploadJob

    job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": str(job.id),
        "name": job.name,
        "status": job.status,
        "file_count": job.file_count,
        "processed_files": job.processed_files,
        "snippets_extracted": job.snippets_extracted,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


@router.get("/github/status/{job_id}")
async def get_github_upload_status(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get the status of a GitHub repository upload job (legacy endpoint, redirects to unified)."""
    return await get_upload_status(job_id, db)
