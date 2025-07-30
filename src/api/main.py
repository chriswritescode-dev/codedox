"""FastAPI application for CodeDox."""

import logging
import hashlib
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, AsyncGenerator

import openai
from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File, Request, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db, init_db, CodeSearcher
from ..crawler import CrawlManager, CrawlConfig
from ..mcp_server import MCPTools
from .routes import router
from .mcp_routes import router as mcp_router
from .websocket import websocket_endpoint
from .mcp_server import create_mcp_server
from .mcp_streamable import StreamableTransport

logger = logging.getLogger(__name__)
settings = get_settings()


# Pydantic models for API
class CrawlRequest(BaseModel):
    """Request model for starting a crawl."""
    name: Optional[str] = Field(None, description="Name of the library/framework (auto-detected if not provided)")
    start_urls: List[str] = Field(..., description="URLs to start crawling")
    max_depth: int = Field(default=1, ge=0, le=3, description="Maximum crawl depth")
    domain_filter: Optional[str] = Field(None, description="Domain restriction pattern")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchRequest(BaseModel):
    """Request model for searching code."""
    query: Optional[str] = Field(None, description="Search query")
    source: Optional[str] = Field(None, description="Filter by source/library name")
    language: Optional[str] = Field(None, description="Filter by programming language")
    job_id: Optional[str] = Field(None, description="Filter by crawl job ID")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class UploadMarkdownRequest(BaseModel):
    """Request model for uploading markdown content."""
    content: str = Field(..., description="Markdown content to process")
    source_url: str = Field(..., description="Source URL for the content")
    title: Optional[str] = Field(None, description="Optional title")


# Application lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting CodeDox API...")
    
    # Test database connection
    from ..database import get_db_manager
    db_manager = get_db_manager()
    if not db_manager.test_connection():
        logger.error("Failed to connect to database. Please ensure PostgreSQL is running and the database exists.")
        logger.error("Run 'python cli.py init' to initialize the database.")
        raise RuntimeError("Database connection failed")
    
    # Start health monitor (skip in test environment)
    import os
    if os.getenv("TESTING") != "true":
        from ..crawler.health_monitor import get_health_monitor
        import asyncio
        health_monitor = get_health_monitor()
        health_task = asyncio.create_task(health_monitor.start())
        logger.info("Started crawl job health monitor")
    else:
        health_monitor = None
        health_task = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down CodeDox API...")
    
    # Stop health monitor if running
    if health_monitor and health_task:
        await health_monitor.stop()
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass


def get_application() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="CodeDox API",
        description="API for code extraction and search from documentation",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.get_cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


# Create app instance
app = get_application()

# Initialize services
crawl_manager = CrawlManager()
mcp_tools = MCPTools()

# Register API routes
app.include_router(router)
app.include_router(mcp_router)

# WebSocket endpoint
app.websocket("/ws/{client_id}")(websocket_endpoint)

# Create MCP server
mcp_server = create_mcp_server()

# Note: SSE transport integration is complex and requires proper session management
# For now, keeping the existing MCP routes in mcp_routes.py as legacy support

# Mount MCP server using Streamable HTTP transport (newest)
streamable_transport = StreamableTransport(mcp_server)

@app.post("/mcp")
async def mcp_streamable_endpoint(
    request: Request,
    mcp_session_id: Optional[str] = Header(None),
    accept: str = Header(None),
    origin: Optional[str] = Header(None),
    last_event_id: Optional[str] = Header(None)
) -> Any:
    """Handle MCP requests using the newest streamable HTTP transport."""
    return await streamable_transport.handle_request(
        request,
        mcp_session_id,
        accept,
        origin,
        last_event_id
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Check API health status."""
    return {
        "status": "healthy",
        "service": "codedox",
        "version": "1.0.1"
    }


# Crawl endpoints
@app.post("/api/crawl/init", response_model=Dict[str, Any])
async def init_crawl(request: CrawlRequest) -> Dict[str, Any]:
    """Initialize a new crawl job."""
    try:
        result = await mcp_tools.init_crawl(
            name=request.name,
            start_urls=request.start_urls,
            max_depth=request.max_depth,
            domain_filter=request.domain_filter,
            metadata=request.metadata
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to initialize crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/crawl/status/{job_id}")
async def get_crawl_status(job_id: str) -> Dict[str, Any]:
    """Get status of a crawl job."""
    try:
        result = await mcp_tools.get_crawl_status(job_id)
        
        if "error" in result and result["error"] == "Job not found":
            raise HTTPException(status_code=404, detail="Crawl job not found")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get crawl status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/crawl/cancel/{job_id}")
async def cancel_crawl(job_id: str) -> Dict[str, Any]:
    """Cancel a running crawl job."""
    try:
        result = await mcp_tools.cancel_crawl(job_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to cancel crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Source management endpoints are in routes.py


# Search endpoints
@app.post("/api/search")
async def search_code(request: SearchRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Search for code snippets."""
    try:
        searcher = CodeSearcher(db)
        
        snippets, total_count = searcher.search(
            query=request.query,
            source=request.source,
            language=request.language,
            job_id=request.job_id,
            limit=request.limit,
            offset=request.offset
        )
        
        # Convert snippets to dict format
        results = [snippet.to_dict() for snippet in snippets]
        
        return {
            "results": results,
            "total": total_count,
            "limit": request.limit,
            "offset": request.offset
        }
        
    except Exception as e:
        logger.error(f"Failed to search code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/languages")
async def get_languages(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    """Get list of available programming languages."""
    try:
        searcher = CodeSearcher(db)
        languages = searcher.get_languages()
        return {"languages": languages}
        
    except Exception as e:
        logger.error(f"Failed to get languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/recent")
async def get_recent_snippets(
    hours: int = Query(default=24, ge=1, le=168),
    language: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get recently added snippets."""
    try:
        searcher = CodeSearcher(db)
        snippets = searcher.get_recent_snippets(
            hours=hours,
            language=language,
            limit=limit
        )
        
        results = [snippet.to_dict() for snippet in snippets]
        
        return {
            "results": results,
            "hours": hours,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent snippets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Upload endpoints
@app.post("/api/upload/markdown")
async def upload_markdown(request: UploadMarkdownRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload and process markdown content using the new extraction method."""
    try:
        from ..crawler import UploadProcessor, UploadConfig
        
        processor = UploadProcessor()
        
        # Create upload configuration
        config = UploadConfig(
            name=request.title or "Uploaded Markdown",
            files=[{
                'content': request.content,
                'source_url': request.source_url,
                'content_type': 'markdown'
            }],
            metadata={
                'uploaded_via': 'api',
                'original_title': request.title
            }
        )
        
        # Start processing
        job_id = await processor.process_upload(config)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Markdown content submitted for processing",
            "status_url": f"/upload/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to process markdown upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    source_url: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Upload a markdown or text file for processing."""
    try:
        # Check file type
        allowed_extensions = ('.md', '.markdown', '.txt', '.rst', '.adoc')
        if not file.filename.endswith(allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Only these file types are supported: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Use filename as source URL if not provided
        if not source_url:
            source_url = f"file://{file.filename}"
        
        # Determine content type from extension
        content_type = 'markdown'
        if file.filename.endswith('.rst'):
            content_type = 'restructuredtext'
        elif file.filename.endswith('.adoc'):
            content_type = 'asciidoc'
        elif file.filename.endswith('.txt'):
            content_type = 'text'
        
        from ..crawler import UploadProcessor, UploadConfig
        
        processor = UploadProcessor()
        
        # Create upload configuration
        config = UploadConfig(
            name=file.filename,
            files=[{
                'content': content_str,
                'source_url': source_url,
                'content_type': content_type
            }],
            metadata={
                'uploaded_via': 'api_file',
                'original_filename': file.filename,
                'content_type': file.content_type
            }
        )
        
        # Start processing
        job_id = await processor.process_upload(config)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"File '{file.filename}' submitted for processing",
            "status_url": f"/upload/status/{job_id}"
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload/files")
async def upload_files(
    files: List[UploadFile] = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Upload multiple markdown or text files for processing in a single job."""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Check file types
        allowed_extensions = ('.md', '.markdown', '.txt', '.rst', '.adoc')
        file_configs = []
        
        for file in files:
            if not file.filename.endswith(allowed_extensions):
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' has unsupported type. Allowed: {', '.join(allowed_extensions)}"
                )
            
            # Read file content
            content = await file.read()
            content_str = content.decode('utf-8')
            
            # Use filename as source URL
            source_url = f"file://{file.filename}"
            
            # Determine content type from extension
            content_type = 'markdown'
            if file.filename.endswith('.rst'):
                content_type = 'restructuredtext'
            elif file.filename.endswith('.adoc'):
                content_type = 'asciidoc'
            elif file.filename.endswith('.txt'):
                content_type = 'text'
            
            file_configs.append({
                'content': content_str,
                'source_url': source_url,
                'content_type': content_type
            })
        
        from ..crawler import UploadProcessor, UploadConfig
        
        processor = UploadProcessor()
        
        # Create upload configuration for all files
        config = UploadConfig(
            name=title or f"Batch Upload ({len(files)} files)",
            files=file_configs,
            metadata={
                'uploaded_via': 'api_files_batch',
                'file_count': len(files),
                'filenames': [f.filename for f in files]
            }
        )
        
        # Start processing
        job_id = await processor.process_upload(config)
        
        return {
            "status": "processing",
            "job_id": job_id,
            "file_count": len(files),
            "message": f"Upload job started for {len(files)} files"
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        logger.error(f"Failed to upload files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/upload/status/{job_id}")
async def get_upload_status(job_id: str) -> Dict[str, Any]:
    """Get the status of an upload job."""
    try:
        from ..crawler import UploadProcessor
        
        processor = UploadProcessor()
        status = processor.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Upload job not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Snippet endpoints are now in routes/snippets.py


# Export endpoint
@app.get("/api/export/{job_id}")
async def export_snippets(
    job_id: str,
    format: str = Query(default="json", regex="^(json|markdown)$"),
    db: Session = Depends(get_db)
) -> Any:
    """Export snippets from a crawl job."""
    try:
        searcher = CodeSearcher(db)
        
        # Get all snippets for the job
        snippets, total = searcher.search(job_id=job_id, limit=1000)
        
        if format == "json":
            return {
                "job_id": job_id,
                "total_snippets": total,
                "snippets": [snippet.to_dict() for snippet in snippets]
            }
        else:  # markdown
            formatted = searcher.format_search_results(snippets)
            return JSONResponse(
                content={"content": formatted},
                media_type="application/json"
            )
            
    except Exception as e:
        logger.error(f"Failed to export snippets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug,
        log_level=settings.logging.level.lower()
    )