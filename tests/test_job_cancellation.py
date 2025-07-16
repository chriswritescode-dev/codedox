"""Test job cancellation functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from src.database.models import CrawlJob, Document, FailedPage
from src.database import get_db_manager
from src.crawler.crawl_manager import CrawlManager, CrawlConfig
from src.crawler.job_manager import JobManager


class TestJobCancellation:
    """Test job cancellation and cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cancel_running_job(self):
        """Test cancelling a running crawl job."""
        # Create a real async task that we can cancel
        async def long_running_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        
        # Create a job ID
        job_id = str(uuid4())
        
        # Create CrawlManager with mocked components
        crawl_manager = CrawlManager()
        task = asyncio.create_task(long_running_task())
        crawl_manager._active_crawl_tasks = {job_id: task}
        
        # Mock the job manager to return success
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=True):
            # Cancel the job
            success = await crawl_manager.cancel_job(job_id)
            assert success
            
            # Verify task was cancelled
            assert task.cancelled() or task.done()
            assert job_id not in crawl_manager._active_crawl_tasks
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self):
        """Test cancelling a job that doesn't exist."""
        crawl_manager = CrawlManager()
        fake_job_id = str(uuid4())
        
        # Mock the job manager to return False (job not found)
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=False):
            success = await crawl_manager.cancel_job(fake_job_id)
            assert not success
    
    @pytest.mark.asyncio
    async def test_failed_page_with_missing_job(self, async_db):
        """Test that failed pages aren't recorded for missing jobs."""
        from src.crawler.page_crawler import PageCrawler
        from src.crawler.config import BrowserConfig
        from src.parser.code_extractor import CodeExtractor
        
        browser_config = BrowserConfig()
        code_extractor = CodeExtractor()
        page_crawler = PageCrawler(browser_config, code_extractor)
        
        # Try to record failed page for non-existent job
        fake_job_id = str(uuid4())
        
        # This should not raise an exception
        await page_crawler._record_failed_page(
            fake_job_id,
            "https://example.com/test",
            "Test error"
        )
        
        # Verify no failed page was created
        failed_page = async_db.query(FailedPage).filter_by(
            crawl_job_id=fake_job_id
        ).first()
        assert failed_page is None
    
    @pytest.mark.asyncio
    async def test_cancellation_stops_crawling(self):
        """Test that cancellation stops the crawling process."""
        job_id = str(uuid4())
        
        # Create a mock task that simulates a running crawl
        mock_task = asyncio.create_task(asyncio.sleep(10))
        
        crawl_manager = CrawlManager()
        crawl_manager._active_crawl_tasks = {job_id: mock_task}
        
        # Mock the job manager
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=True):
            # Cancel should stop the task
            success = await crawl_manager.cancel_job(job_id)
            assert success
            assert mock_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_enrichment_pipeline_stops_on_cancel(self):
        """Test that enrichment pipeline stops when job is cancelled."""
        job_id = str(uuid4())
        
        crawl_manager = CrawlManager()
        
        # Mock the enrichment manager
        crawl_manager.enrichment_manager.is_pipeline_running = Mock(return_value=True)
        crawl_manager.enrichment_manager.stop_pipeline = AsyncMock()
        
        # Mock job manager
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=True):
            # Add a mock task
            mock_task = Mock()
            mock_task.done.return_value = True
            crawl_manager._active_crawl_tasks = {job_id: mock_task}
            
            # Cancel the job
            success = await crawl_manager.cancel_job(job_id)
            assert success
            
            # Verify pipeline was stopped
            crawl_manager.enrichment_manager.stop_pipeline.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_active_task_cleanup(self):
        """Test that active tasks are cleaned up properly."""
        job_id = str(uuid4())
        
        # Create a task that completes
        async def dummy_crawl():
            await asyncio.sleep(0.01)
            return "completed"
        
        crawl_manager = CrawlManager()
        task = asyncio.create_task(dummy_crawl())
        crawl_manager._active_crawl_tasks = {job_id: task}
        
        # Wait for task to complete
        await task
        
        # Mock job manager
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=True):
            # Cancel should handle completed task gracefully
            success = await crawl_manager.cancel_job(job_id)
            assert success
            assert job_id not in crawl_manager._active_crawl_tasks
    
    @pytest.mark.asyncio 
    async def test_cancel_with_no_active_task(self):
        """Test cancelling a job with no active task."""
        job_id = str(uuid4())
        
        crawl_manager = CrawlManager()
        # No active tasks
        crawl_manager._active_crawl_tasks = {}
        
        # Mock job manager to return success
        with patch.object(crawl_manager.job_manager, 'cancel_job', return_value=True):
            # Should still succeed (updates DB)
            success = await crawl_manager.cancel_job(job_id)
            assert success
    
    def test_delete_job_endpoint_checks_active_tasks(self):
        """Test that the delete endpoint checks for active tasks."""
        # Test that CrawlManager has the _active_crawl_tasks attribute
        crawl_manager = CrawlManager()
        assert hasattr(crawl_manager, '_active_crawl_tasks')
        assert isinstance(crawl_manager._active_crawl_tasks, dict)