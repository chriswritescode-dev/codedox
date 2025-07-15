"""Tests for ResultProcessor with pipeline submission."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
from uuid import uuid4

from src.crawler.result_processor import ResultProcessor
from src.crawler.page_crawler import CrawlResult
from src.parser.code_extractor import CodeBlock
from src.language.detector import LanguageDetector
from src.database.models import Document, CrawlJob


@pytest.fixture
def mock_code_extractor():
    """Create a mock code extractor."""
    extractor = Mock()
    return extractor


@pytest.fixture
def mock_language_detector():
    """Create a mock language detector."""
    detector = Mock(spec=LanguageDetector)
    return detector


@pytest.fixture
def mock_enrichment_pipeline():
    """Create a mock enrichment pipeline."""
    pipeline = Mock()
    pipeline.is_running = True
    pipeline.add_document = AsyncMock()
    return pipeline


@pytest.fixture
def result_processor(mock_code_extractor, mock_language_detector, mock_enrichment_pipeline, db):
    """Create a ResultProcessor instance with mocks."""
    processor = ResultProcessor(
        code_extractor=mock_code_extractor,
        language_detector=mock_language_detector,
        metadata_enricher=None,
        enrichment_pipeline=mock_enrichment_pipeline
    )
    # Override the db_manager to use test database
    from unittest.mock import Mock
    mock_db_manager = Mock()
    mock_db_manager.session_scope = Mock()
    mock_db_manager.session_scope().__enter__ = Mock(return_value=db)
    mock_db_manager.session_scope().__exit__ = Mock(return_value=None)
    processor.db_manager = mock_db_manager
    return processor


@pytest.fixture
def sample_crawl_result():
    """Create a sample crawl result with code blocks."""
    code_blocks = [
        CodeBlock(
            content="def hello():\n    print('Hello')",
            language="python",
            line_start=1,
            line_end=2,
            extraction_metadata={"type": "function"}
        ),
        CodeBlock(
            content="function test() { return true; }",
            language="javascript",
            line_start=5,
            line_end=5,
            extraction_metadata={"type": "function"}
        )
    ]
    
    result = CrawlResult(
        url="https://example.com/test",
        title="Test Page",
        content="Test content",
        content_hash="hash123",
        links=[],
        code_blocks=code_blocks,
        metadata={"depth": 0},
        markdown_content="# Test\n```python\ndef hello():\n    print('Hello')\n```"
    )
    return result


class TestResultProcessorPipeline:
    """Test ResultProcessor pipeline functionality."""
    
    @pytest.mark.asyncio
    async def test_process_result_pipeline_returns_task(self, result_processor, sample_crawl_result, db):
        """Test that process_result_pipeline returns a task when pipeline is available."""
        # Create a crawl job first
        job_id = uuid4()
        # Use the provided db session instead of creating a new one
        # Create crawl job
        job = CrawlJob(
            id=job_id,
            name="Test Job",
            domain="test-pipeline-example.com",
            start_urls=["https://test-pipeline-example.com"],
            max_depth=0,
            status="running",
            created_at=datetime.utcnow()
        )
        db.add(job)
        
        # Ensure no existing document
        existing = db.query(Document).filter_by(url=sample_crawl_result.url).first()
        if existing:
            db.delete(existing)
        db.commit()
        
        # Process result with pipeline
        doc_id, snippet_count, task = await result_processor.process_result_pipeline(
            sample_crawl_result, str(job_id), 0
        )
        
        # Verify return values
        assert isinstance(doc_id, int)
        assert snippet_count == 2  # Two code blocks
        assert isinstance(task, asyncio.Task)
        
        # Wait for the task to complete
        await task
        
        # Verify pipeline was called
        result_processor.enrichment_pipeline.add_document.assert_called_once()
        call_args = result_processor.enrichment_pipeline.add_document.call_args[1]
        assert call_args['document_id'] == doc_id
        assert call_args['document_url'] == sample_crawl_result.url
        assert call_args['job_id'] == str(job_id)
        assert len(call_args['code_blocks']) == 2
        
        # Cleanup
        # Delete documents
        db.query(Document).filter_by(crawl_job_id=job_id).delete()
        # Delete job
        db.query(CrawlJob).filter_by(id=job_id).delete()
        db.commit()
    
    @pytest.mark.asyncio
    async def test_process_result_pipeline_no_pipeline(self, mock_code_extractor, mock_language_detector, 
                                                      sample_crawl_result, db):
        """Test process_result_pipeline when no pipeline is available."""
        # Create processor without pipeline
        processor = ResultProcessor(
            code_extractor=mock_code_extractor,
            language_detector=mock_language_detector,
            metadata_enricher=None,
            enrichment_pipeline=None
        )
        # Override the db_manager to use test database
        from unittest.mock import Mock
        mock_db_manager = Mock()
        mock_db_manager.session_scope = Mock()
        mock_db_manager.session_scope().__enter__ = Mock(return_value=db)
        mock_db_manager.session_scope().__exit__ = Mock(return_value=None)
        processor.db_manager = mock_db_manager
        
        # Create a crawl job first
        job_id = uuid4()
        # Use the provided db session
        # Create crawl job
        job = CrawlJob(
            id=job_id,
            name="Test Job No Pipeline",
            domain="test-no-pipeline-example.com",
            start_urls=["https://test-no-pipeline-example.com"],
            max_depth=0,
            status="running",
            created_at=datetime.utcnow()
        )
        db.add(job)
        
        # Ensure no existing document
        existing = db.query(Document).filter_by(url=sample_crawl_result.url).first()
        if existing:
            db.delete(existing)
        db.commit()
        
        # Process result without pipeline
        doc_id, snippet_count, task = await processor.process_result_pipeline(
            sample_crawl_result, str(job_id), 0
        )
        
        # Verify return values
        assert isinstance(doc_id, int)
        assert snippet_count == 0  # No snippets processed without pipeline
        assert task is None  # No task created
        
        # Cleanup
        with processor.db_manager.session_scope() as session:
            # Delete documents
            session.query(Document).filter_by(crawl_job_id=job_id).delete()
            # Delete job
            session.query(CrawlJob).filter_by(id=job_id).delete()
            session.commit()
    
    @pytest.mark.asyncio
    async def test_process_batch_handles_mixed_returns(self, result_processor, sample_crawl_result, db):
        """Test that process_batch handles both 2-tuple and 3-tuple returns."""
        # Create a crawl job first
        job_id = uuid4()
        # Use the provided db session
        # Create crawl job
        job = CrawlJob(
            id=job_id,
            name="Test Job Batch",
            domain="test-batch-example.com",
            start_urls=["https://test-batch-example.com"],
            max_depth=0,
            status="running",
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        
        # Create a second result without code blocks
        result_no_blocks = CrawlResult(
            url="https://example.com/no-blocks",
            title="No Blocks",
            content="Test content",
            content_hash="hash456",
            links=[],
            code_blocks=[],
            metadata={"depth": 0},
            markdown_content="# Test"
        )
        
        results = [sample_crawl_result, result_no_blocks]
        
        # Process batch
        total_docs, total_snippets, all_links = await result_processor.process_batch(
            results, str(job_id), use_pipeline=True
        )
        
        # Verify results
        assert total_docs == 2
        assert total_snippets == 2  # Only first result has code blocks
        assert isinstance(all_links, list)
        
        # Verify pipeline was called for result with code blocks
        assert result_processor.enrichment_pipeline.add_document.call_count == 1
        
        # Cleanup
        # Delete documents
        db.query(Document).filter_by(crawl_job_id=job_id).delete()
        # Delete job
        db.query(CrawlJob).filter_by(id=job_id).delete()
        db.commit()