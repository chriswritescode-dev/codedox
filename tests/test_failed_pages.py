"""Tests for failed pages tracking and retry functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4

from src.crawler.crawl_manager import CrawlManager, CrawlConfig
from src.crawler.page_crawler import CrawlResult
from src.database.models import CrawlJob, FailedPage, Document
from src.database import get_db_manager


@pytest.fixture
def crawl_manager(db):
    """Create a CrawlManager instance for testing with test database session."""
    manager = CrawlManager()
    
    # Mock the session_scope to use our test session
    from contextlib import contextmanager
    
    @contextmanager
    def mock_session_scope():
        """Mock session scope to use test database session."""
        yield db
    
    # Replace the session_scope method for all components that have db_manager
    # After refactoring, db_manager is in multiple components
    if hasattr(manager, 'job_manager') and hasattr(manager.job_manager, 'db_manager'):
        manager.job_manager.db_manager.session_scope = mock_session_scope
    if hasattr(manager, 'result_processor') and hasattr(manager.result_processor, 'db_manager'):
        manager.result_processor.db_manager.session_scope = mock_session_scope
    if hasattr(manager, 'page_crawler') and hasattr(manager.page_crawler, 'db_manager'):
        manager.page_crawler.db_manager.session_scope = mock_session_scope
    if hasattr(manager, 'enrichment_manager') and hasattr(manager.enrichment_manager, 'db_manager'):
        manager.enrichment_manager.db_manager.session_scope = mock_session_scope
    
    return manager


@pytest.fixture
def mock_crawl_job(db):
    """Create a mock crawl job in the database."""
    job = CrawlJob(
        id=uuid4(),
        name="Test Crawl",
        domain="example.com",
        start_urls=["https://example.com"],
        max_depth=2,
        status="running",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)  # Ensure the object is bound to the session
    
    yield job
    
    # Cleanup after test
    try:
        # Delete any failed pages associated with this job
        db.query(FailedPage).filter_by(crawl_job_id=job.id).delete()
        # Delete the job itself
        db.query(CrawlJob).filter_by(id=job.id).delete()
        db.commit()
    except Exception:
        db.rollback()


class TestFailedPagesTracking:
    """Test failed pages tracking functionality."""

    @pytest.mark.asyncio
    async def test_record_failed_page(self, crawl_manager, mock_crawl_job, db):
        """Test recording a failed page."""
        job_id = str(mock_crawl_job.id)
        url = "https://example.com/failed-page"
        error_message = "Timeout 30000ms exceeded"
        
        # Record the failed page
        from src.crawler.page_crawler import PageCrawler
        from src.crawler.config import create_browser_config
        from src.parser import CodeExtractor
        browser_config = create_browser_config()
        code_extractor = CodeExtractor()
        page_crawler = PageCrawler(browser_config, code_extractor)
        await page_crawler._record_failed_page(job_id, url, error_message)
        
        # Verify it was saved
        failed_page = db.query(FailedPage).filter_by(
            crawl_job_id=job_id,
            url=url
        ).first()
        
        assert failed_page is not None
        assert failed_page.url == url
        assert failed_page.error_message == error_message
        assert failed_page.failed_at is not None

    @pytest.mark.asyncio
    async def test_record_failed_page_no_duplicates(self, crawl_manager, mock_crawl_job, db):
        """Test that duplicate failed pages are not recorded."""
        job_id = str(mock_crawl_job.id)
        url = "https://example.com/failed-page"
        error_message = "Timeout 30000ms exceeded"
        
        # Record the same page twice
        from src.crawler.page_crawler import PageCrawler
        from src.crawler.config import create_browser_config
        from src.parser import CodeExtractor
        browser_config = create_browser_config()
        code_extractor = CodeExtractor()
        page_crawler = PageCrawler(browser_config, code_extractor)
        await page_crawler._record_failed_page(job_id, url, error_message)
        await page_crawler._record_failed_page(job_id, url, "Different error")
        
        # Should only have one record
        count = db.query(FailedPage).filter_by(
            crawl_job_id=job_id,
            url=url
        ).count()
        
        assert count == 1

    @pytest.mark.asyncio
    async def test_retry_failed_pages_no_failures(self, crawl_manager, mock_crawl_job):
        """Test retry when there are no failed pages."""
        job_id = str(mock_crawl_job.id)
        
        result = await crawl_manager.retry_failed_pages(job_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_failed_pages_creates_new_job(self, crawl_manager, mock_crawl_job, db):
        """Test that retrying failed pages creates a new crawl job."""
        job_id = str(mock_crawl_job.id)
        
        # Add some failed pages
        failed_urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]
        
        for url in failed_urls:
            failed_page = FailedPage(
                crawl_job_id=job_id,
                url=url,
                error_message="Test error",
                failed_at=datetime.utcnow()
            )
            db.add(failed_page)
        db.commit()
        
        # Mock the start_crawl method
        with patch.object(crawl_manager, 'start_crawl', new_callable=AsyncMock) as mock_start:
            new_job_id = str(uuid4())
            mock_start.return_value = new_job_id
            
            result = await crawl_manager.retry_failed_pages(job_id)
            
            assert result == new_job_id
            
            # Verify start_crawl was called with correct config
            mock_start.assert_called_once()
            config = mock_start.call_args[0][0]
            
            assert isinstance(config, CrawlConfig)
            assert config.name == "Test Crawl - Retry Failed Pages"
            assert set(config.start_urls) == set(failed_urls)
            assert config.max_depth == 0  # Don't crawl deeper
            assert config.max_pages == len(failed_urls)
            assert config.metadata["retry_of_job"] == job_id

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Test needs to be rewritten for new architecture")
    async def test_crawl_records_failed_pages(self, crawl_manager, mock_crawl_job, db):
        """Test that failed pages are recorded during crawl."""
        job_id = str(mock_crawl_job.id)
        
        # Mock a failed crawl result
        mock_result = Mock()
        mock_result.success = False
        mock_result.url = "https://example.com/failed"
        mock_result.error_message = "Page.goto: Timeout 30000ms exceeded"
        
        # Mock the page crawler to return our failed result
        with patch('src.crawler.page_crawler.PageCrawler.crawl_page', new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = mock_result
            
            # Mock result processor to handle the failed result
            with patch('src.crawler.result_processor.ResultProcessor.process_result', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = None  # Failed pages return None
                
                # Run a partial crawl
                config = CrawlConfig(
                    name="Test",
                    start_urls=["https://example.com/failed"],
                    max_depth=0
                )
                
                # We need to mock the entire crawl process
                with patch.object(crawl_manager, '_record_failed_page', new_callable=AsyncMock) as mock_record:
                    # Simulate the crawl loop
                    results = await crawl_manager._crawl_page(
                        "https://example.com/failed", 
                        job_id, 
                        0, 
                        0
                    )
                    
                    # Process the failed result (this is what happens in the actual crawl loop)
                    for result in results:
                        if not result.success:
                            await crawl_manager._record_failed_page(
                                job_id, 
                                result.url, 
                                result.error_message
                            )
                    
                    # Verify the failed page was recorded
                    mock_record.assert_called_once_with(
                        job_id,
                        "https://example.com/failed",
                        "Page.goto: Timeout 30000ms exceeded"
                    )


class TestAPIEndpoint:
    """Test the retry failed pages API endpoint."""

    @pytest.mark.asyncio
    async def test_retry_failed_pages_endpoint(self, client, mock_crawl_job, db):
        """Test the API endpoint for retrying failed pages."""
        job_id = str(mock_crawl_job.id)
        
        # Add a failed page
        failed_page = FailedPage(
            crawl_job_id=job_id,
            url="https://example.com/failed",
            error_message="Test error",
            failed_at=datetime.utcnow()
        )
        db.add(failed_page)
        db.commit()
        
        # Mock the crawl manager
        with patch('src.api.routes.crawl_jobs.CrawlManager') as MockCrawlManager:
            mock_manager = MockCrawlManager.return_value
            new_job_id = str(uuid4())
            mock_manager.retry_failed_pages = AsyncMock(return_value=new_job_id)
            
            response = client.post(f"/api/crawl-jobs/{job_id}/retry-failed")
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Retry job created successfully"
            assert data["job_id"] == job_id
            assert data["new_job_id"] == new_job_id

    @pytest.mark.asyncio
    async def test_retry_failed_pages_endpoint_no_failures(self, client, mock_crawl_job):
        """Test the API endpoint when there are no failed pages."""
        job_id = str(mock_crawl_job.id)
        
        with patch('src.api.routes.crawl_jobs.CrawlManager') as MockCrawlManager:
            mock_manager = MockCrawlManager.return_value
            mock_manager.retry_failed_pages = AsyncMock(return_value=None)
            
            response = client.post(f"/api/crawl-jobs/{job_id}/retry-failed")
            
            assert response.status_code == 400
            data = response.json()
            assert "No failed pages found" in data["detail"]


class TestJobWithFailedPagesCount:
    """Test that job responses include failed pages count."""

    def test_job_to_dict_includes_failed_pages(self, db):
        """Test that CrawlJob.to_dict includes failed_pages_count."""
        job = CrawlJob(
            id=uuid4(),
            name="Test Job",
            domain="example.com",
            start_urls=["https://example.com"],
            status="completed",
            created_at=datetime.utcnow()
        )
        db.add(job)
        
        # Add some failed pages
        for i in range(3):
            failed_page = FailedPage(
                crawl_job_id=job.id,
                url=f"https://example.com/page{i}",
                error_message="Test error",
                failed_at=datetime.utcnow()
            )
            db.add(failed_page)
        
        db.commit()
        
        # Get the job dict
        job_dict = job.to_dict()
        
        assert "failed_pages_count" in job_dict
        assert job_dict["failed_pages_count"] == 3

    @pytest.mark.asyncio
    async def test_get_crawl_job_endpoint_includes_failed_count(self, client, mock_crawl_job, db):
        """Test that the get crawl job endpoint includes failed pages count."""
        job_id = str(mock_crawl_job.id)
        
        # Add failed pages
        for i in range(2):
            failed_page = FailedPage(
                crawl_job_id=job_id,
                url=f"https://example.com/failed{i}",
                error_message="Error",
                failed_at=datetime.utcnow()
            )
            db.add(failed_page)
        db.commit()
        
        response = client.get(f"/api/crawl-jobs/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "failed_pages_count" in data
        assert data["failed_pages_count"] == 2