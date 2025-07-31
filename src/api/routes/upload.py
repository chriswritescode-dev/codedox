"""Upload routes for processing markdown files."""

import hashlib
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...database import get_db
from ...database.models import CrawlJob, Document, CodeSnippet
from ...crawler.llm_retry import LLMDescriptionGenerator
from ...crawler.extraction_models import SimpleCodeBlock

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadMarkdownRequest(BaseModel):
    """Request model for uploading markdown content."""
    content: str = Field(..., description="Markdown content to process")
    name: str = Field(..., description="Name for this upload batch")
    title: Optional[str] = Field(None, description="Optional title")


def extract_code_blocks_with_context(content: str, url: str) -> List[SimpleCodeBlock]:
    """Extract code blocks from markdown content with surrounding context."""
    code_blocks = []
    lines = content.split('\n')
    
    # Match code blocks with optional language
    pattern = r'```(\w*)\n(.*?)\n```'
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    for i, match in enumerate(matches):
        language = match.group(1) or None
        code = match.group(2).strip()
        
        if code:  # Only add non-empty code blocks
            # Get line numbers
            start_line = content[:match.start()].count('\n')
            end_line = content[:match.end()].count('\n')
            
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
                context_after=context_after
            )
            code_blocks.append(block)
    
    return code_blocks


@router.post("/markdown")
async def upload_markdown(request: UploadMarkdownRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
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
            completed_at=datetime.utcnow()
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
            crawl_job_id=job.id
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
                        block.description = f"{block.language or 'Code'} snippet from {request.name}"
            
            # Save enhanced code snippets
            for block in enhanced_blocks:
                snippet = CodeSnippet(
                    document_id=doc.id,
                    title=block.title or '',
                    description=block.description or '',
                    language=block.language or 'unknown',
                    code_content=block.code,
                    snippet_type='code',
                    source_url=doc_url,
                    functions=[],
                    imports=[],
                    keywords=[]
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
            "message": f"Successfully processed {request.name}"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(..., description="Name for this upload batch"),
    title: Optional[str] = Form(None, description="Optional title"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Upload a markdown file for processing."""
    try:
        # Check file type
        if not file.filename.endswith(('.md', '.markdown', '.txt')):
            raise HTTPException(
                status_code=400,
                detail="Only markdown (.md, .markdown) or text (.txt) files are supported"
            )
        
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Process using markdown upload endpoint
        request = UploadMarkdownRequest(
            content=content_str,
            name=name,
            title=title or file.filename
        )
        
        return await upload_markdown(request, db)
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))