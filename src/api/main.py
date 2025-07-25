"""FastAPI application for CodeDox."""

import logging
import hashlib
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, AsyncGenerator

import openai
from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File, Request, Header
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
        allow_origins=settings.api.cors_origins,
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
@app.post("/crawl/init", response_model=Dict[str, Any])
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


@app.get("/crawl/status/{job_id}")
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


@app.post("/crawl/cancel/{job_id}")
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
@app.post("/search")
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


@app.get("/search/languages")
async def get_languages(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    """Get list of available programming languages."""
    try:
        searcher = CodeSearcher(db)
        languages = searcher.get_languages()
        return {"languages": languages}
        
    except Exception as e:
        logger.error(f"Failed to get languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/recent")
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
@app.post("/upload/markdown")
async def upload_markdown(request: UploadMarkdownRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload and process markdown content - NEEDS TO BE UPDATED to use new HTML extraction method."""
    # TODO: Update this endpoint to use the new HTML extraction + LLM description method
    # Currently disabled until the new extraction method is implemented for uploads
    raise HTTPException(
        status_code=501,
        detail="Upload functionality is temporarily disabled while being updated to use the new extraction method. Please use the crawl functionality instead."
    )


@app.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    source_url: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Upload a markdown file for processing."""
    try:
        # Check file type
        if not file.filename.endswith(('.md', '.markdown')):
            raise HTTPException(
                status_code=400,
                detail="Only markdown files (.md, .markdown) are supported"
            )
        
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Use filename as source URL if not provided
        if not source_url:
            source_url = f"file://{file.filename}"
        
        # Process using markdown upload endpoint
        request = UploadMarkdownRequest(
            content=content_str,
            source_url=source_url,
            title=file.filename
        )
        
        return await upload_markdown(request, db)
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Snippet endpoints
@app.get("/snippets/{snippet_id}")
async def get_snippet(snippet_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get details of a specific code snippet."""
    try:
        from ..database.models import CodeSnippet
        
        snippet = db.query(CodeSnippet).filter_by(id=snippet_id).first()
        
        if not snippet:
            raise HTTPException(status_code=404, detail="Snippet not found")
        
        return snippet.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get snippet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Export endpoint
@app.get("/export/{job_id}")
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