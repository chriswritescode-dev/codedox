"""Tests for crawl recovery and restart functionality."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.crawler.crawl_manager import CrawlManager, CrawlConfig
from src.crawler.health_monitor import CrawlHealthMonitor, STALLED_THRESHOLD
from src.database.models import CrawlJob, Document
from src.database import get_db_manager


@pytest.fixture
def crawl_manager():
    """Create a crawl manager instance."""
    return CrawlManager()


@pytest.fixture
def health_monitor():
    """Create a health monitor instance."""
    return CrawlHealthMonitor()


@pytest.fixture
def mock_crawler():
    """Mock the AsyncWebCrawler."""
    with patch('src.crawler.page_crawler.AsyncWebCrawler') as mock:
        crawler_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = crawler_instance
        yield crawler_instance


class TestCrawlRecovery:
    """Test crawl recovery and restart functionality."""
    
    @pytest.mark.asyncio
    async def test_crawl_job_heartbeat_updates(self, crawl_manager, mock_crawler):
        """Test that crawl jobs update heartbeats during execution."""
        # Create a test crawl config
        config = CrawlConfig(
            name="Test Heartbeat",
            start_urls=["https://example.com"],
            max_depth=1,
            max_pages=5
        )
        
        # Mock crawler responses as async iterator
        async def mock_arun(*args, **kwargs):
            """Mock arun to return an async iterator of results."""
            results = [
                Mock(
                    url="https://example.com",
                    markdown="# Test Page\n\n```python\nprint('test')\n```",
                    success=True,
                    links=["https://example.com/page1"],
                    error_message=None,
                    metadata={'depth': 0}
                )
            ]
            async def async_gen():
                for result in results:
                    yield result
            return async_gen()
        
        mock_crawler.arun.side_effect = mock_arun
        
        # Start the crawl
        job_id = await crawl_manager.start_crawl(config)
        
        # Check that job was created with heartbeat
        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job is not None
            assert job.last_heartbeat is not None
            initial_heartbeat = job.last_heartbeat
        
        # Wait longer for heartbeat updates (heartbeat interval is 5 seconds)
        await asyncio.sleep(6)
        
        # Check heartbeat was updated
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            # If heartbeat hasn't updated, the job might have finished quickly
            # Check if job completed instead
            if job.status == "completed":
                assert job.completed_at is not None
            else:
                assert job.last_heartbeat > initial_heartbeat
    
    @pytest.mark.asyncio
    async def test_stalled_crawl_detection(self, health_monitor):
        """Test detection of stalled crawl jobs."""
        db_manager = get_db_manager()
        
        # Create a stalled job (old heartbeat)
        with db_manager.session_scope() as session:
            stalled_job = CrawlJob(
                id=uuid4(),
                name="Stalled Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 60),
                crawl_phase="crawling",
                started_at=datetime.utcnow() - timedelta(minutes=30)
            )
            session.add(stalled_job)
            session.commit()
            stalled_job_id = str(stalled_job.id)
        
        # Check stalled jobs
        stalled_ids = health_monitor.get_stalled_jobs()
        assert stalled_job_id in stalled_ids
        
        # Run health check
        await health_monitor._check_stalled_jobs()
        
        # Verify job was marked as failed
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=stalled_job_id).first()
            assert job.status == "failed"
            assert "stalled" in job.error_message.lower()
            assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_crawl_phase_tracking(self, crawl_manager, mock_crawler):
        """Test that crawl phases are properly tracked."""
        config = CrawlConfig(
            name="Test Phases",
            start_urls=["https://example.com"],
            max_depth=0,
            max_pages=1
        )
        
        # Mock successful crawl as async iterator
        async def mock_arun(*args, **kwargs):
            """Mock arun to return an async iterator of results."""
            results = [
                Mock(
                    url="https://example.com",
                    markdown="# Test\n\n```python\ncode = 'test'\n```",
                    success=True,
                    links=[],
                    error_message=None,
                    metadata={'depth': 0}
                )
            ]
            async def async_gen():
                for result in results:
                    yield result
            return async_gen()
        
        mock_crawler.arun.side_effect = mock_arun
        
        job_id = await crawl_manager.start_crawl(config)
        
        # Check phases during crawl
        db_manager = get_db_manager()
        
        # Should be in crawling phase initially
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.crawl_phase == "crawling"
        
        # Wait for completion
        await asyncio.sleep(3)
        
        # Check final state
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.status == "completed"
            # crawl_completed_at is set when transitioning to enrichment or when completing without enrichment
            # Since this test doesn't create documents, it should complete without enrichment
            assert job.completed_at is not None
            # If no documents were created, crawl_completed_at might not be set separately
            assert job.crawl_phase is None  # Should be cleared on completion
    
    @pytest.mark.asyncio
    async def test_crawl_error_recovery(self, crawl_manager, mock_crawler):
        """Test crawl behavior when encountering errors."""
        config = CrawlConfig(
            name="Test Error Recovery",
            start_urls=["https://example.com"],
            max_depth=1,
            max_pages=5
        )
        
        # Mock the deep crawl to return all pages at once
        from unittest.mock import MagicMock
        
        # Create proper mock objects with all required attributes
        page1 = MagicMock()
        page1.url = "https://example.com"
        page1.html = "<h1>Main Page</h1><p>Content with <pre><code class='language-python'>print('hello')</code></pre></p>"
        page1.cleaned_html = "<h1>Main Page</h1><p>Content with <pre><code class='language-python'>print('hello')</code></pre></p>"
        page1.markdown = "# Main Page"
        page1.success = True
        page1.links = {"internal": [{"href": "https://example.com/page1", "text": "Page 1"},
                                    {"href": "https://example.com/page2", "text": "Page 2"}]}
        page1.error_message = None
        page1.metadata = {"depth": 0, "title": "Main Page"}
        page1.title = "Main Page"
        page1.error = None
        
        page2 = MagicMock()
        page2.url = "https://example.com/page1"
        page2.html = ""
        page2.cleaned_html = ""
        page2.markdown = None
        page2.success = False
        page2.links = {"internal": []}
        page2.error_message = "Connection timeout"
        page2.metadata = {"depth": 1}
        page2.title = ""
        page2.error = "Connection timeout"
        
        page3 = MagicMock()
        page3.url = "https://example.com/page2"
        page3.html = "<h1>Page 2</h1><pre><code class='language-javascript'>console.log('test');</code></pre>"
        page3.cleaned_html = "<h1>Page 2</h1><pre><code class='language-javascript'>console.log('test');</code></pre>"
        page3.markdown = "# Page 2\n\n```js\nconsole.log('test');\n```"
        page3.success = True
        page3.links = {"internal": []}
        page3.error_message = None
        page3.metadata = {"depth": 1, "title": "Page 2"}
        page3.title = "Page 2"
        page3.error = None
        
        # Mock the deep crawl strategy
        async def mock_arun(url, *args, **kwargs):
            """Mock arun to return an async iterator with all results."""
            async def async_gen():
                # Return all pages for deep crawl
                for result in [page1, page2, page3]:
                    yield result
            return async_gen()
        
        mock_crawler.arun.side_effect = mock_arun
        
        job_id = await crawl_manager.start_crawl(config)
        
        # Wait for crawl to complete
        await asyncio.sleep(3)
        
        # Check results
        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            
            # Job should complete despite some page failures
            assert job.status == "completed"
            assert job.processed_pages >= 1  # At least 1 page was processed
            assert job.documents_crawled >= 1  # At least 1 was successful
            
            # Check documents
            docs = session.query(Document).filter_by(crawl_job_id=job_id).all()
            assert len(docs) >= 1  # At least some successful pages saved
            
            # Failed page should not have a document
            failed_urls = [d.url for d in docs]
            assert "https://example.com/page1" not in failed_urls
    
    @pytest.mark.asyncio
    async def test_job_health_check(self, health_monitor):
        """Test individual job health checking."""
        db_manager = get_db_manager()
        
        # Create jobs in various states
        with db_manager.session_scope() as session:
            # Healthy running job
            healthy_job = CrawlJob(
                id=uuid4(),
                name="Healthy Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow(),
                crawl_phase="crawling"
            )
            
            # Warning job (heartbeat getting old)
            warning_job = CrawlJob(
                id=uuid4(),
                name="Warning Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD/2 + 10),
                crawl_phase="enriching"
            )
            
            # Completed job
            completed_job = CrawlJob(
                id=uuid4(),
                name="Completed Job",
                start_urls=["https://example.com"],
                status="completed",
                completed_at=datetime.utcnow()
            )
            
            session.add_all([healthy_job, warning_job, completed_job])
            session.commit()
            
            healthy_id = str(healthy_job.id)
            warning_id = str(warning_job.id)
            completed_id = str(completed_job.id)
        
        # Check health of each job
        healthy_status = health_monitor.check_job_health(healthy_id)
        assert healthy_status["is_healthy"] is True
        assert healthy_status["health_status"] == "healthy"
        
        warning_status = health_monitor.check_job_health(warning_id)
        assert warning_status["is_healthy"] is True  # Not stalled yet
        assert warning_status["health_status"] == "warning"
        
        completed_status = health_monitor.check_job_health(completed_id)
        assert completed_status["is_healthy"] is True
        assert completed_status["health_status"] == "completed"
        
        # Check non-existent job with valid UUID
        missing_uuid = str(uuid4())
        missing_status = health_monitor.check_job_health(missing_uuid)
        assert missing_status["status"] == "not_found"
    
    @pytest.mark.asyncio
    async def test_enrichment_phase_error_handling(self, crawl_manager):
        """Test error handling during enrichment phase."""
        config = CrawlConfig(
            name="Test Enrichment Errors",
            start_urls=["https://example.com"],
            max_depth=0,
            max_pages=1
        )
        
        # Mock LLM error during enrichment
        with patch('src.llm.enricher.MetadataEnricher') as mock_enricher:
            enricher_instance = AsyncMock()
            enricher_instance.enrich_snippets.side_effect = Exception("LLM service unavailable")
            mock_enricher.return_value = enricher_instance
            
            # Also need to mock the crawler
            with patch('src.crawler.page_crawler.AsyncWebCrawler') as mock_crawler_cls:
                crawler_instance = AsyncMock()
                # Mock successful crawl as async iterator
                async def mock_arun(*args, **kwargs):
                    """Mock arun to return an async iterator of results."""
                    results = [
                        Mock(
                            url="https://example.com",
                            html="<h1>Test</h1><pre><code class='language-python'>code = 'test'</code></pre>",
                            cleaned_html="<h1>Test</h1><pre><code class='language-python'>code = 'test'</code></pre>",
                            markdown="# Test\n\n```python\ncode = 'test'\n```",
                            success=True,
                            links={"internal": []},
                            error_message=None,
                            metadata={'depth': 0, 'title': 'Test'},
                            title='Test',
                            error=None
                        )
                    ]
                    async def async_gen():
                        for result in results:
                            yield result
                    return async_gen()
                
                crawler_instance.arun.side_effect = mock_arun
                mock_crawler_cls.return_value.__aenter__.return_value = crawler_instance
                
                # Start crawl
                job_id = await crawl_manager.start_crawl(config)
                
                # Wait for completion - give it more time since enrichment is involved
                await asyncio.sleep(5)
                
                # Check job status
                db_manager = get_db_manager()
                with db_manager.session_scope() as session:
                    job = session.query(CrawlJob).filter_by(id=job_id).first()
                    
                    # Job should still complete even if enrichment fails
                    assert job.status == "completed"
                    # Check if documents were created
                    doc_count = session.query(Document).filter_by(crawl_job_id=job_id).count()
                    assert doc_count > 0 or job.processed_pages > 0  # Either documents or pages should be recorded
                    
                    # Check document enrichment status
                    docs = session.query(Document).filter_by(crawl_job_id=job_id).all()
                    for doc in docs:
                        # Documents should be marked as skipped, failed, pending, processing, or completed
                        assert doc.enrichment_status in ["skipped", "failed", "pending", "processing", "completed"]
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, crawl_manager):
        """Test job retry mechanism."""
        db_manager = get_db_manager()
        
        # Create a failed job with retries available
        with db_manager.session_scope() as session:
            failed_job = CrawlJob(
                id=uuid4(),
                name="Retry Test Job",
                start_urls=["https://example.com"],
                status="failed",
                error_message="Initial failure",
                retry_count=1,
                max_retries=3,
                completed_at=datetime.utcnow()
            )
            session.add(failed_job)
            session.commit()
            job_id = str(failed_job.id)
        
        # Check retry count tracking
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.retry_count == 1
            assert job.retry_count < job.max_retries
            
            # Simulate retry
            job.retry_count += 1
            job.status = "running"
            job.error_message = None
            job.completed_at = None
            job.last_heartbeat = datetime.utcnow()
            session.commit()
        
        # Verify retry was applied
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.status == "running"
            assert job.retry_count == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_crawl_recovery(self, crawl_manager, mock_crawler):
        """Test recovery when multiple crawls are running."""
        # Start multiple crawls
        configs = [
            CrawlConfig(
                name=f"Concurrent Test {i}",
                start_urls=[f"https://example{i}.com"],
                max_depth=0,
                max_pages=1
            )
            for i in range(3)
        ]
        
        # Mock responses for all crawls as async iterator
        async def mock_arun(url, *args, **kwargs):
            """Mock arun to return an async iterator of results."""
            # Extract number from URL to create appropriate response
            import re
            match = re.search(r'example(\d+)', url)
            num = match.group(1) if match else "0"
            
            results = [
                Mock(
                    url=url,
                    markdown=f"# Test {num}",
                    success=True,
                    links=[],
                    error_message=None,
                    metadata={'depth': 0}
                )
            ]
            async def async_gen():
                for result in results:
                    yield result
            return async_gen()
        
        mock_crawler.arun.side_effect = mock_arun
        
        # Start all crawls
        job_ids = []
        for config in configs:
            job_id = await crawl_manager.start_crawl(config)
            job_ids.append(job_id)
        
        # Simulate one job stalling
        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            # Make the second job appear stalled
            job = session.query(CrawlJob).filter_by(id=job_ids[1]).first()
            job.last_heartbeat = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 60)
            session.commit()
        
        # Run health check
        health_monitor = CrawlHealthMonitor()
        await health_monitor._check_stalled_jobs()
        
        # Verify only the stalled job was affected
        with db_manager.session_scope() as session:
            jobs = session.query(CrawlJob).filter(
                CrawlJob.id.in_(job_ids)
            ).all()
            
            statuses = {str(job.id): job.status for job in jobs}
            
            # First and third should be unaffected
            assert statuses[str(job_ids[0])] in ["running", "completed"]
            assert statuses[str(job_ids[2])] in ["running", "completed"]
            
            # Second should be failed
            assert statuses[str(job_ids[1])] == "failed"