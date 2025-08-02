"""CodeDox API Server."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from .mcp_routes import router as mcp_router
from .mcp_streamable import router as mcp_streamable_router
from .routes import crawl_jobs, search, snippets, sources, upload
from .websocket import websocket_endpoint

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting CodeDox API...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

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
        import asyncio

        from ..crawler.health_monitor import get_health_monitor
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

    logger.info("CodeDox API shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="CodeDox API",
    description="API for code documentation extraction and search",
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

# Include routers
app.include_router(sources.router, prefix="/api", tags=["sources"])
app.include_router(crawl_jobs.router, prefix="/api", tags=["crawl-jobs"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(snippets.router, prefix="/api", tags=["snippets"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(mcp_router, tags=["mcp"])
app.include_router(mcp_streamable_router, tags=["mcp-streamable"])

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_route(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates."""
    await websocket_endpoint(websocket, client_id)

# Root redirect
@app.get("/")
async def root():
    """Redirect to the web UI."""
    return FileResponse(Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html")

# Health check
@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}

@app.get("/api/health/db")
async def health_check_db(db: Session = Depends(get_db)):
    """Database health check endpoint."""
    try:
        # Simple query to test DB connection
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")

# Statistics endpoint
@app.get("/api/statistics")
async def get_statistics(db: Session = Depends(get_db)):
    """Get system statistics."""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import distinct, func

        from ..database.models import CodeSnippet, CrawlJob, Document

        # Get counts
        total_sources = db.query(
            func.count(distinct(CrawlJob.name))
        ).filter(
            CrawlJob.status == 'completed'
        ).scalar() or 0

        total_documents = db.query(func.count(Document.id)).scalar() or 0
        total_snippets = db.query(func.count(CodeSnippet.id)).scalar() or 0

        # Get language distribution
        language_stats = db.query(
            CodeSnippet.language,
            func.count(CodeSnippet.id).label('count')
        ).group_by(CodeSnippet.language).all()

        languages = {lang: count for lang, count in language_stats if lang}

        # Get recent crawls (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_crawls = db.query(CrawlJob).filter(
            CrawlJob.created_at >= seven_days_ago
        ).order_by(CrawlJob.created_at.desc()).limit(10).all()

        return {
            "total_sources": total_sources,
            "total_documents": total_documents,
            "total_snippets": total_snippets,
            "languages": languages,
            "recent_crawls": [job.to_dict() for job in recent_crawls]
        }

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Recent snippets endpoint
@app.get("/api/snippets/recent")
async def get_recent_snippets(
    hours: int = 24,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recently extracted code snippets."""
    try:
        from datetime import datetime, timedelta

        from ..database.models import CodeSnippet, CrawlJob, Document

        # Calculate time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        # Query recent snippets with joins for source info
        snippets = db.query(
            CodeSnippet,
            Document.title.label('document_title'),
            Document.url.label('document_url'),
            CrawlJob.name.label('source_name')
        ).join(
            Document, CodeSnippet.document_id == Document.id
        ).join(
            CrawlJob, Document.crawl_job_id == CrawlJob.id
        ).filter(
            CodeSnippet.created_at >= time_threshold
        ).order_by(
            CodeSnippet.created_at.desc()
        ).limit(limit).all()

        # Format results
        results = []
        for snippet, doc_title, doc_url, source_name in snippets:
            snippet_dict = snippet.to_dict()
            snippet_dict['document_title'] = doc_title
            snippet_dict['document_url'] = doc_url
            snippet_dict['source_name'] = source_name
            results.append(snippet_dict)

        return {
            "snippets": results,
            "hours": hours,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Failed to get recent snippets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Upload endpoints are now in routes/upload.py

# Serve static files for the web UI (in production, use nginx)
if settings.environment == "development":
    from fastapi.staticfiles import StaticFiles
    frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
        logger.info(f"Serving frontend from {frontend_dir}")


def get_application() -> FastAPI:
    """Get the FastAPI application instance."""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.environment == "development"
    )
