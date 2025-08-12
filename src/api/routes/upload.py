"""Upload routes for processing markdown files."""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...crawler.extraction_models import SimpleCodeBlock
from ...crawler.llm_retry import LLMDescriptionGenerator
from ...database import get_db
from ...database.models import CodeSnippet, CrawlJob, Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadMarkdownRequest(BaseModel):
    """Request model for uploading markdown content."""

    content: str = Field(..., description="Markdown content to process")
    name: str = Field(..., description="Name for this upload batch")
    title: str | None = Field(None, description="Optional title")


def extract_code_blocks_with_context(content: str, url: str) -> list[SimpleCodeBlock]:
    """Extract code blocks from markdown content with surrounding context."""
    code_blocks = []
    lines = content.split("\n")

    # Match code blocks with optional language
    pattern = r"```(\w*)\n(.*?)\n```"
    matches = list(re.finditer(pattern, content, re.DOTALL))

    for i, match in enumerate(matches):
        language = match.group(1) or None
        code = match.group(2).strip()

        if code:  # Only add non-empty code blocks
            # Get line numbers
            start_line = content[: match.start()].count("\n")
            end_line = content[: match.end()].count("\n")

            # Extract context before (up to 5 lines)
            context_before = []
            for j in range(max(0, start_line - 5), start_line):
                if j < len(lines) and lines[j].strip():
                    context_before.append(lines[j].strip())

            # Extract context after (up to 3 lines)
            context_after = []
            for j in range(end_line + 1, min(len(lines), end_line + 4)):
                if j < len(lines) and lines[j].strip():
                    context_after.append(lines[j].strip())

            # Create SimpleCodeBlock for LLM processing
            block = SimpleCodeBlock(
                code=code,
                language=language,
                source_url=url,
                context_before=context_before,
                context_after=context_after,
            )
            code_blocks.append(block)

    return code_blocks


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
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(job)

        # Create document
        content_hash = hashlib.md5(request.content.encode()).hexdigest()
        doc_url = f"upload://{request.name}/{request.title or 'content'}"
        doc = Document(
            url=doc_url,
            title=request.title or request.name,
            content_type="markdown",
            content_hash=content_hash,
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
                code_hash = hashlib.md5(block.code.encode()).hexdigest()

                # Check if snippet already exists
                existing_snippet = (
                    db.query(CodeSnippet).filter(CodeSnippet.code_hash == code_hash).first()
                )

                if existing_snippet:
                    logger.info(f"Skipping duplicate code snippet with hash {code_hash}")
                    continue

                snippet = CodeSnippet(
                    document_id=doc.id,
                    title=block.title or "",
                    description=block.description or "",
                    language=block.language or "unknown",
                    code_content=block.code,
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
    name: str | None = Form(None, description="Name for this upload batch"),
    title: str | None = Form(None, description="Optional title"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload a markdown file for processing."""
    try:
        # Check file type
        if not file.filename.endswith((".md", ".markdown", ".txt")):
            raise HTTPException(
                status_code=400,
                detail="Only markdown (.md, .markdown) or text (.txt) files are supported",
            )

        # Read file content
        content = await file.read()
        content_str = content.decode("utf-8")

        # Process using markdown upload endpoint
        request = UploadMarkdownRequest(
            content=content_str,
            name=name or title or file.filename.rsplit(".", 1)[0],
            title=title or file.filename,
        )

        return await upload_markdown(request, db)

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
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
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload multiple markdown files and process them."""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Create a source for all files
        source_name = name or title or f"Upload {datetime.utcnow().strftime('%Y-%m-%d')}"
        url = f"upload://{source_name}/batch"

        # Check if source already exists
        existing_job = db.query(CrawlJob).filter(CrawlJob.name == source_name).first()

        if existing_job:
            crawl_job = existing_job
            logger.info(f"Using existing source: {source_name}")
        else:
            # Create crawl job for this upload batch
            crawl_job = CrawlJob(
                id=uuid4(),
                name=source_name,
                start_urls=[url],
                max_depth=0,
                status="completed",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(crawl_job)
            db.flush()

        # Initialize LLM generator if available
        llm_generator = None
        try:
            llm_generator = LLMDescriptionGenerator()
            logger.info("LLM generator initialized for batch upload")
        except Exception as e:
            logger.warning(f"LLM generator not available: {e}")

        total_snippets = 0
        processed_files = 0

        for file in files:
            try:
                # Validate file type
                if not file.filename:
                    continue

                if not (
                    file.filename.endswith(".md")
                    or file.filename.endswith(".markdown")
                    or file.filename.endswith(".txt")
                ):
                    logger.warning(f"Skipping non-markdown file: {file.filename}")
                    continue

                # Read file content
                content = await file.read()
                content_str = content.decode("utf-8")

                # Create URL for this file
                file_url = f"upload://{source_name}/{file.filename}"

                # Create document
                content_hash = hashlib.md5(content_str.encode()).hexdigest()

                # Check if document already exists
                existing_doc = (
                    db.query(Document)
                    .filter(Document.url == file_url, Document.content_hash == content_hash)
                    .first()
                )

                if existing_doc:
                    logger.info(f"Skipping duplicate file: {file.filename}")
                    continue

                document = Document(
                    url=file_url,
                    title=title or file.filename,
                    content_type="markdown",
                    content_hash=content_hash,
                    crawl_job_id=crawl_job.id,
                    crawl_depth=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(document)
                db.flush()

                # Extract code blocks with context
                code_blocks = extract_code_blocks_with_context(content_str, file_url)

                # Process code blocks with LLM if available
                if llm_generator and code_blocks:
                    try:
                        # Pass context to LLM for better understanding
                        enhanced_blocks = (
                            await llm_generator.generate_titles_and_descriptions_batch(
                                code_blocks, file_url
                            )
                        )
                        code_blocks = enhanced_blocks
                    except Exception as e:
                        logger.warning(f"LLM processing failed for {file.filename}: {e}")

                # Create code snippets
                for block in code_blocks:
                    # Calculate code hash
                    code_hash = hashlib.md5(block.code.encode()).hexdigest()

                    # Check if snippet already exists
                    existing_snippet = (
                        db.query(CodeSnippet).filter(CodeSnippet.code_hash == code_hash).first()
                    )

                    if existing_snippet:
                        logger.info(f"Skipping duplicate code snippet with hash {code_hash}")
                        continue

                    snippet = CodeSnippet(
                        document_id=document.id,
                        title=block.title or f"Code Block from {file.filename}",
                        description=block.description,
                        language=block.language or "text",
                        code_content=block.code,
                        code_hash=code_hash,
                        source_url=file_url,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(snippet)
                    total_snippets += 1

                processed_files += 1

            except Exception as e:
                logger.error(f"Failed to process file {file.filename}: {e}")
                continue

        # Update crawl job stats
        crawl_job.total_pages = processed_files
        crawl_job.processed_pages = processed_files
        crawl_job.snippets_extracted = total_snippets
        crawl_job.updated_at = datetime.utcnow()

        db.commit()

        return {
            "status": "success",
            "job_id": str(crawl_job.id),
            "file_count": processed_files,
            "message": f"Successfully processed {processed_files} files with {total_snippets} code snippets extracted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload files: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
