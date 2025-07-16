"""Pytest configuration and fixtures for API tests."""

import os

# Set testing environment variable before any imports
os.environ["TESTING"] = "true"

import pytest
import asyncio
import logging
from datetime import datetime
from typing import Generator
from uuid import uuid4

# Configure logging to avoid I/O errors during teardown
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Add a null handler to prevent logging errors during teardown
import sys
if "pytest" in sys.modules:
    logging.getLogger().addHandler(logging.NullHandler())

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from src.api.main import app
from src.database import Base, get_db
from src.database.models import CrawlJob, Document, CodeSnippet, FailedPage
from src.database.connection import DatabaseManager

logger = logging.getLogger(__name__)


# For tests, we'll use PostgreSQL with a test schema to avoid conflicts
# Build test database URL from individual components
TEST_DB_HOST = os.getenv("TEST_DB_HOST", os.getenv("DB_HOST", "localhost"))
TEST_DB_PORT = os.getenv("TEST_DB_PORT", os.getenv("DB_PORT", "5432"))
# Use the same database but with a test schema
TEST_DB_NAME = os.getenv("TEST_DB_NAME", os.getenv("DB_NAME", "codedox"))
TEST_DB_USER = os.getenv("TEST_DB_USER", os.getenv("DB_USER", "postgres"))
TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", os.getenv("DB_PASSWORD", "postgres"))

TEST_DATABASE_URL = f"postgresql+psycopg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"

# Create test engine
engine = create_engine(TEST_DATABASE_URL)

# Use a test schema to isolate test data
TEST_SCHEMA = "test_codedox"

@event.listens_for(engine, "connect", insert=True)
def set_search_path(dbapi_connection, connection_record):
    """Set schema search path for all connections."""
    existing_autocommit = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}")
    cursor.execute(f"SET search_path TO {TEST_SCHEMA}, public")
    cursor.close()
    dbapi_connection.autocommit = existing_autocommit

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test function."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    
    # Cancel all pending tasks before closing
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    
    # Close all async generators
    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        pass
    
    loop.close()


@pytest.fixture(scope="session")
def setup_database():
    """Create test schema and tables in the existing database."""
    # Create tables in a test schema within the existing database
    with engine.begin() as conn:
        # Drop and recreate the test schema to ensure clean state
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        
        # Create extensions in public schema (they're global)
        conn.execute(text("SET search_path TO public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\""))
        
        # Switch back to test schema
        conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        
        # Create tables using SQLAlchemy models
        Base.metadata.create_all(bind=conn)
        
        # Add the search_vector column and trigger manually
        conn.execute(text("""
            ALTER TABLE code_snippets 
            ADD COLUMN IF NOT EXISTS search_vector tsvector
        """))
        
        # Create the update_search_vector function
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_search_vector()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.search_vector := 
                    setweight(to_tsvector(COALESCE(NEW.title, '')), 'A') ||
                    setweight(to_tsvector(COALESCE(NEW.description, '')), 'B') ||
                    setweight(to_tsvector(COALESCE(NEW.code_content, '')), 'C') ||
                    setweight(to_tsvector(COALESCE(array_to_string(NEW.functions, ' '), '')), 'B') ||
                    setweight(to_tsvector(COALESCE(array_to_string(NEW.imports, ' '), '')), 'C');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        
        # Create the trigger
        conn.execute(text("""
            DROP TRIGGER IF EXISTS update_code_snippets_search_vector ON code_snippets
        """))
        conn.execute(text("""
            CREATE TRIGGER update_code_snippets_search_vector 
            BEFORE INSERT OR UPDATE OF title, description, code_content, functions, imports 
            ON code_snippets
            FOR EACH ROW EXECUTE FUNCTION update_search_vector()
        """))
        
        # Create index on search_vector
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_snippets_search_vector 
            ON code_snippets USING GIN(search_vector)
        """))
    
    yield
    
    # Drop the test schema and all its tables
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
            print(f"\n✓ Successfully cleaned up test schema: {TEST_SCHEMA}")
            logger.info(f"Cleaned up test schema: {TEST_SCHEMA}")
    except Exception as e:
        print(f"\n✗ Failed to clean up test schema: {TEST_SCHEMA} - {e}")
        logger.error(f"Failed to clean up test schema: {TEST_SCHEMA} - {e}")
    
    # Final cleanup: Remove any test data from main schema
    try:
        with engine.begin() as conn:
            # Clean up any test data that might have leaked
            result = conn.execute(text("""
                DELETE FROM code_snippets 
                WHERE document_id IN (
                    SELECT id FROM documents 
                    WHERE crawl_job_id IN (
                        SELECT id FROM crawl_jobs 
                        WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                           OR start_urls[1] LIKE '%example%'
                    )
                )
            """))
            snippets_deleted = result.rowcount
            
            result = conn.execute(text("""
                DELETE FROM documents 
                WHERE crawl_job_id IN (
                    SELECT id FROM crawl_jobs 
                    WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                       OR start_urls[1] LIKE '%example%'
                )
            """))
            docs_deleted = result.rowcount
            
            result = conn.execute(text("""
                DELETE FROM page_links 
                WHERE crawl_job_id IN (
                    SELECT id FROM crawl_jobs 
                    WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                       OR start_urls[1] LIKE '%example%'
                )
            """))
            links_deleted = result.rowcount
            
            result = conn.execute(text("""
                DELETE FROM crawl_jobs 
                WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                   OR start_urls[1] LIKE '%example%'
            """))
            jobs_deleted = result.rowcount
            
            if any([snippets_deleted, docs_deleted, links_deleted, jobs_deleted]):
                print(f"\n✓ Final cleanup removed leaked test data: {jobs_deleted} jobs, {docs_deleted} docs, {snippets_deleted} snippets, {links_deleted} links")
            else:
                print("\n✓ No leaked test data found in main schema")
    except Exception as e:
        print(f"\n⚠ Warning: Failed to perform final cleanup: {e}")


@pytest.fixture
def db(setup_database) -> Generator[Session, None, None]:
    """Get test database session with automatic cleanup."""
    connection = engine.connect()
    trans = connection.begin()
    
    # Configure session to use our transaction
    session = TestingSessionLocal(bind=connection)
    
    # Set search path to test schema
    session.execute(text(f"SET search_path TO {TEST_SCHEMA}, public"))
    
    yield session
    
    # Clean up ALL data from test schema after each test
    try:
        # Create a new connection for cleanup
        cleanup_conn = engine.connect()
        cleanup_trans = cleanup_conn.begin()
        
        # Delete all test data in correct order
        cleanup_conn.execute(text(f"SET search_path TO {TEST_SCHEMA}, public"))
        cleanup_conn.execute(text("DELETE FROM code_snippets"))
        cleanup_conn.execute(text("DELETE FROM documents"))
        cleanup_conn.execute(text("DELETE FROM page_links"))
        cleanup_conn.execute(text("DELETE FROM failed_pages"))
        cleanup_conn.execute(text("DELETE FROM crawl_jobs"))
        
        cleanup_trans.commit()
        cleanup_conn.close()
    except Exception as e:
        print(f"Warning: Failed to cleanup test data: {e}")
    
    # Close the test session
    session.close()
    trans.rollback()
    connection.close()
    
    # Extra safety: Clean up any test data that might have leaked to the main schema
    try:
        with engine.begin() as cleanup_conn:
            # Delete test data from main schema that matches test patterns
            cleanup_conn.execute(text("""
                DELETE FROM code_snippets 
                WHERE document_id IN (
                    SELECT id FROM documents 
                    WHERE crawl_job_id IN (
                        SELECT id FROM crawl_jobs 
                        WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                           OR start_urls[1] LIKE '%example.com%'
                           OR start_urls[1] LIKE '%example0.com%'
                           OR start_urls[1] LIKE '%example1.com%'
                           OR start_urls[1] LIKE '%example2.com%'
                           OR start_urls[1] LIKE '%example3.com%'
                           OR start_urls[1] LIKE '%example4.com%'
                    )
                )
            """))
            
            cleanup_conn.execute(text("""
                DELETE FROM documents 
                WHERE crawl_job_id IN (
                    SELECT id FROM crawl_jobs 
                    WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                       OR start_urls[1] LIKE '%example.com%'
                       OR start_urls[1] LIKE '%example0.com%'
                       OR start_urls[1] LIKE '%example1.com%'
                       OR start_urls[1] LIKE '%example2.com%'
                       OR start_urls[1] LIKE '%example3.com%'
                       OR start_urls[1] LIKE '%example4.com%'
                )
            """))
            
            cleanup_conn.execute(text("""
                DELETE FROM page_links 
                WHERE crawl_job_id IN (
                    SELECT id FROM crawl_jobs 
                    WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                       OR start_urls[1] LIKE '%example.com%'
                       OR start_urls[1] LIKE '%example0.com%'
                       OR start_urls[1] LIKE '%example1.com%'
                       OR start_urls[1] LIKE '%example2.com%'
                       OR start_urls[1] LIKE '%example3.com%'
                       OR start_urls[1] LIKE '%example4.com%'
                )
            """))
            
            cleanup_conn.execute(text("""
                DELETE FROM crawl_jobs 
                WHERE name LIKE '%Test%' OR name LIKE '%test%' 
                   OR start_urls[1] LIKE '%example.com%'
                   OR start_urls[1] LIKE '%example0.com%'
                   OR start_urls[1] LIKE '%example1.com%'
                   OR start_urls[1] LIKE '%example2.com%'
                   OR start_urls[1] LIKE '%example3.com%'
                   OR start_urls[1] LIKE '%example4.com%'
            """))
    except Exception:
        # Ignore cleanup errors - they're not critical
        pass


@pytest.fixture
def async_db(setup_database):
    """Get test database session for async tests."""
    # For async tests, we'll use the same sync session approach
    # This works because the tests will run in the event loop
    connection = engine.connect()
    trans = connection.begin()
    
    # Configure session to use our transaction
    session = TestingSessionLocal(bind=connection)
    
    # Set search path to test schema
    session.execute(text(f"SET search_path TO {TEST_SCHEMA}, public"))
    
    yield session
    
    # Clean up
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """Get test client with database override."""
    # Store original overrides
    original_overrides = app.dependency_overrides.copy()
    
    # Set test database override
    app.dependency_overrides[get_db] = lambda: db
    
    # Create test client
    test_client = TestClient(app)
    
    try:
        yield test_client
    finally:
        # Ensure cleanup happens even on failure
        test_client.close()
        
        # Restore original overrides
        app.dependency_overrides = original_overrides
        
        # Small delay to ensure connections are closed
        import time
        time.sleep(0.05)


@pytest.fixture
def sample_crawl_job(db: Session) -> CrawlJob:
    """Create a sample crawl job."""
    job = CrawlJob(
        id=uuid4(),
        name="Test Documentation",
        start_urls=["https://example.com/docs"],
        max_depth=2,
        status="completed",
        total_pages=10,
        processed_pages=10,
        snippets_extracted=25,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.fixture
def sample_document(db: Session, sample_crawl_job: CrawlJob) -> Document:
    """Create a sample document."""
    doc = Document(
        url="https://example.com/docs/getting-started",
        title="Getting Started",
        content_type="html",
        markdown_content="# Getting Started\n\nSample content for testing",
        crawl_job_id=sample_crawl_job.id,
        crawl_depth=1,
        parent_url="https://example.com/docs",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture
def sample_code_snippets(db: Session, sample_document: Document) -> list[CodeSnippet]:
    """Create sample code snippets."""
    snippets = []
    
    # Python snippet
    python_snippet = CodeSnippet(
        document_id=sample_document.id,
        title="Python Example",
        description="A simple Python function",
        language="python",
        code_content="def hello_world():\n    print('Hello, World!')",
        code_hash=f"hash_python_{uuid4()}",
        line_start=1,
        line_end=2,
        functions=["hello_world"],
        snippet_type="function",
        source_url=sample_document.url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    snippets.append(python_snippet)
    
    # JavaScript snippet
    js_snippet = CodeSnippet(
        document_id=sample_document.id,
        title="JavaScript Example",
        description="A JavaScript async function",
        language="javascript",
        code_content="async function fetchData() {\n  const response = await fetch('/api/data');\n  return response.json();\n}",
        code_hash=f"hash_js_{uuid4()}",
        line_start=10,
        line_end=14,
        functions=["fetchData"],
        imports=["fetch"],
        snippet_type="function",
        source_url=sample_document.url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    snippets.append(js_snippet)
    
    # Configuration snippet
    config_snippet = CodeSnippet(
        document_id=sample_document.id,
        title="Configuration Example",
        description="Sample configuration",
        language="yaml",
        code_content="database:\n  host: localhost\n  port: 5432",
        code_hash=f"hash_config_{uuid4()}",
        snippet_type="config",
        source_url=sample_document.url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    snippets.append(config_snippet)
    
    for snippet in snippets:
        db.add(snippet)
    
    db.commit()
    for snippet in snippets:
        db.refresh(snippet)
    
    return snippets


@pytest.fixture
def multiple_crawl_jobs(db: Session) -> list[CrawlJob]:
    """Create multiple crawl jobs with different statuses."""
    jobs = []
    
    statuses = ["completed", "running", "failed", "pending"]
    for i, status in enumerate(statuses):
        job = CrawlJob(
            id=uuid4(),
            name=f"Test Job {i+1}",
            start_urls=[f"https://example{i+1}.com"],
            max_depth=1,
            status=status,
            total_pages=10 if status != "pending" else 0,
            processed_pages=10 if status == "completed" else 5 if status == "running" else 0,
            snippets_extracted=20 if status == "completed" else 10 if status == "running" else 0,
            started_at=datetime.utcnow() if status != "pending" else None,
            completed_at=datetime.utcnow() if status in ["completed", "failed"] else None,
            error_message="Test error" if status == "failed" else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        jobs.append(job)
        db.add(job)
    
    db.commit()
    for job in jobs:
        db.refresh(job)
    
    return jobs


@pytest.fixture
def mock_mcp_tools(monkeypatch):
    """Mock MCP tools to avoid external dependencies."""
    async def mock_init_crawl(self, name: str, start_urls: list, max_depth: int = 1, domain_filter: str = None, metadata: dict = None):
        return {
            "job_id": str(uuid4()),
            "status": "started",
            "library_name": name,
            "message": f"Crawl job '{name}' initiated with {len(start_urls)} URLs at depth {max_depth}",
            "start_urls": start_urls,
            "max_depth": max_depth,
            "domain_restrictions": []
        }
    
    async def mock_search_libraries(self, query: str, max_results: int = 10):
        return {
            "status": "success",
            "selected_library": {
                "library_id": str(uuid4()),
                "name": "Test Source",
                "description": "Test description",
                "snippet_count": 100
            },
            "explanation": "Exact match found for 'test'"
        }
    
    async def mock_get_content(self, library_id: str, query: str = None, language: str = None, max_results: int = 10):
        return """Found 1 results in Test Source

TITLE: Test Result
DESCRIPTION: Test description
SOURCE: https://example.com/test

LANGUAGE: python
CODE:
```python
print('test')
```

----------------------------------------"""
    
    async def mock_get_snippet_details(self, snippet_id: int):
        if snippet_id == 123:
            return {
                "id": 123,
                "title": "Test Snippet",
                "description": "A test code snippet",
                "language": "python",
                "source_url": "https://example.com/test",
                "code": "def test():\n    print('Hello, World!')",
                "line_start": 10,
                "line_end": 12,
                "functions": ["test"],
                "imports": [],
                "keywords": [],
                "snippet_type": "function",
                "context_before": "# This is a test function",
                "context_after": "# End of test",
                "section_title": "Testing Functions",
                "section_content": None,
                "related_snippets": [],
                "metadata": {},
                "created_at": "2024-01-01T00:00:00",
                "updated_at": None,
                "document": {
                    "id": 1,
                    "url": "https://example.com/test",
                    "title": "Test Document",
                    "crawl_depth": 1,
                    "parent_url": "https://example.com",
                    "last_crawled": "2024-01-01T00:00:00",
                    "markdown_content": "# Test Document\n\nThis is a test document with code:\n\n```python\nprint('hello')\n```"
                }
            }
        else:
            return {
                "error": "Snippet not found",
                "snippet_id": snippet_id
            }
    
    # Patch the MCPTools methods
    from src.mcp_server.tools import MCPTools
    monkeypatch.setattr(MCPTools, "init_crawl", mock_init_crawl)
    monkeypatch.setattr(MCPTools, "search_libraries", mock_search_libraries)
    monkeypatch.setattr(MCPTools, "get_content", mock_get_content)
    monkeypatch.setattr(MCPTools, "get_snippet_details", mock_get_snippet_details)


@pytest.fixture
def mock_llm_client(monkeypatch):
    """Mock LLM client for health check tests."""
    class MockLLMClient:
        def __init__(self, debug=False):
            self.model = "gpt-4"
            self.api_key = "test-key"
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        
        async def test_connection(self):
            return {
                "status": "connected",
                "provider": "openai",
                "endpoint": "https://api.openai.com",
                "models": ["gpt-4", "gpt-3.5-turbo"]
            }
    
    # Patch at the import location
    import src.llm.client
    monkeypatch.setattr(src.llm.client, "LLMClient", MockLLMClient)