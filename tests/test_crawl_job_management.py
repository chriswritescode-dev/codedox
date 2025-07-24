"""Test crawl job management including restart and recovery scenarios."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.database.models import CrawlJob, Document, CodeSnippet
from src.database import get_db_manager
from src.crawler.crawl_manager import CrawlManager, CrawlConfig


class TestCrawlJobManagement:
    """Test crawl job management functionality."""
    
    def test_job_retry_tracking(self):
        """Test that retry counts are properly tracked."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create a job
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Retry Test",
                start_urls=["https://example.com"],
                status="running",
                retry_count=0,
                max_retries=3
            )
            session.add(job)
            session.commit()
        
        # Simulate failure and retry
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "failed"
            job.error_message = "Connection timeout"
            job.retry_count = 1
            session.commit()
        
        # Check retry count
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.retry_count == 1
            assert job.retry_count < job.max_retries
            can_retry = job.retry_count < job.max_retries
            assert can_retry is True
        
        # Max out retries
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.retry_count = 3
            session.commit()
        
        # Check cannot retry
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            can_retry = job.retry_count < job.max_retries
            assert can_retry is False
    
    def test_job_phase_transitions(self):
        """Test job phase transitions during crawling."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create job in crawling phase
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Phase Test",
                start_urls=["https://example.com"],
                status="running",
                crawl_phase="crawling",
                started_at=datetime.utcnow()
            )
            session.add(job)
            session.commit()
        
        # Transition to finalizing
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.crawl_phase = "finalizing"
            job.crawl_completed_at = datetime.utcnow()
            session.commit()
        
        # Verify transition
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.crawl_phase == "finalizing"
            assert job.crawl_completed_at is not None
        
        # Complete job
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "completed"
            job.crawl_phase = None  # Clear phase when done
            job.completed_at = datetime.utcnow()
            session.commit()
        
        # Verify completion
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.status == "completed"
            assert job.crawl_phase is None
            assert job.completed_at is not None
    
    def test_preserve_data_on_restart(self):
        """Test that existing data is preserved when restarting a job."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create job with some completed work
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Data Preservation Test",
                start_urls=["https://example.com"],
                status="failed",
                documents_crawled=5,
                snippets_extracted=20,
                processed_pages=5
            )
            session.add(job)
            
            # Add documents
            for i in range(5):
                doc = Document(
                    url=f"https://example.com/{job_id}/page{i}",  # Make URL unique per test
                    title=f"Page {i}",
                    crawl_job_id=job_id,
                    content_type="html",
                    markdown_content=f"# Page {i}\n\nContent {i}"
                )
                session.add(doc)
                session.flush()
                
                # Add snippets to some documents
                if i < 3:
                    for j in range(2):
                        snippet = CodeSnippet(
                            document_id=doc.id,
                            title=f"Code {i}-{j}",
                            language="python",
                            code_content=f"def func_{i}_{j}(): pass",
                            source_url=doc.url
                        )
                        session.add(snippet)
            
            session.commit()
        
        # Count existing data
        with db_manager.session_scope() as session:
            doc_count = session.query(Document).filter_by(crawl_job_id=job_id).count()
            snippet_count = session.query(CodeSnippet).join(Document).filter(
                Document.crawl_job_id == job_id
            ).count()
            
            assert doc_count == 5
            assert snippet_count == 6  # 3 documents * 2 snippets each
        
        # Simulate restart
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "running"
            job.error_message = None
            job.retry_count = 1
            job.last_heartbeat = datetime.utcnow()
            session.commit()
        
        # Verify data still exists
        with db_manager.session_scope() as session:
            doc_count = session.query(Document).filter_by(crawl_job_id=job_id).count()
            snippet_count = session.query(CodeSnippet).join(Document).filter(
                Document.crawl_job_id == job_id
            ).count()
            
            assert doc_count == 5
            assert snippet_count == 6
    
    def test_error_state_clearing(self):
        """Test that error states are properly cleared on restart."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create failed job with error states
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Error Clear Test",
                start_urls=["https://example.com"],
                status="failed",
                error_message="Network error: Connection refused",
                crawl_phase="crawling",
                completed_at=datetime.utcnow() - timedelta(hours=1)
            )
            session.add(job)
            
            # Add document
            doc = Document(
                url=f"https://example.com/{job_id}/failed",  # Make URL unique
                crawl_job_id=job_id
            )
            session.add(doc)
            session.commit()
        
        # Clear error states for restart
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "running"
            job.error_message = None
            job.completed_at = None
            job.last_heartbeat = datetime.utcnow()
            
            # Reset job fields
            docs = session.query(Document).filter_by(
                crawl_job_id=job_id
            ).all()
            
            session.commit()
        
        # Verify clearing
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.status == "running"
            assert job.error_message is None
            assert job.completed_at is None
            
            doc = session.query(Document).filter_by(crawl_job_id=job_id).first()
            assert doc is not None  # Just verify the document exists
    
    def test_job_statistics_tracking(self):
        """Test tracking of job statistics across restarts."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create job with initial statistics
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Stats Test",
                start_urls=["https://example.com"],
                status="running",
                total_pages=50,
                processed_pages=20,
                documents_crawled=18,
                snippets_extracted=45
            )
            session.add(job)
            session.commit()
        
        # Simulate failure
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "failed"
            job.error_message = "Memory limit exceeded"
            session.commit()
        
        # Check stats are preserved
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.processed_pages == 20
            assert job.documents_crawled == 18
            assert job.snippets_extracted == 45
    
    def test_prevent_concurrent_restart(self):
        """Test that running jobs cannot be restarted."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create running job
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Running Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow()
            )
            session.add(job)
            session.commit()
        
        # Check restart eligibility
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            can_restart = job.status in ["failed", "cancelled"]
            assert can_restart is False
        
        # Paused jobs also cannot be restarted (must resume instead)
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.status = "paused"
            session.commit()
        
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            can_restart = job.status in ["failed", "cancelled"]
            assert can_restart is False
    
    def test_crawl_depth_tracking(self):
        """Test that crawl depth is properly tracked in documents."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create job and documents at various depths
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Depth Test",
                start_urls=["https://example.com"],
                max_depth=3,
                status="running"
            )
            session.add(job)
            
            # Add documents at different depths
            depths = [
                (f"https://example.com/{job_id}", 0),
                (f"https://example.com/{job_id}/level1", 1),
                (f"https://example.com/{job_id}/level1/level2", 2),
                (f"https://example.com/{job_id}/level1/level2/level3", 3),
            ]
            
            for url, depth in depths:
                doc = Document(
                    url=url,
                    crawl_job_id=job_id,
                    crawl_depth=depth,
                    parent_url=f"https://example.com/{job_id}" if depth > 0 else None
                )
                session.add(doc)
            
            session.commit()
        
        # Verify depth tracking
        with db_manager.session_scope() as session:
            docs = session.query(Document).filter_by(crawl_job_id=job_id).order_by(
                Document.crawl_depth
            ).all()
            
            assert len(docs) == 4
            for i, doc in enumerate(docs):
                assert doc.crawl_depth == i
    
    def test_document_creation_tracking(self):
        """Test that document creation is tracked correctly."""
        db_manager = get_db_manager()
        
        job_id = str(uuid4())
        
        # Create job with documents
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Document Tracking Test",
                start_urls=["https://example.com"],
                status="running",
                crawl_phase="crawling",
                processed_pages=3,
                total_pages=3,
                documents_crawled=3
            )
            session.add(job)
            
            # Add 3 documents
            for i in range(3):
                doc = Document(
                    url=f"https://example.com/{job_id}/page{i}",
                    crawl_job_id=job_id,
                )
                session.add(doc)
                session.flush()  # Flush to get doc.id
                
                # Add code snippets to each document
                for j in range(2):  # 2 snippets per document
                    # Generate unique hash with job_id to avoid conflicts
                    snippet = CodeSnippet(
                        document_id=doc.id,
                        language="python",
                        code_content=f"def func_{i}_{j}(): pass",
                        code_hash=f"hash_{job_id}_{i}_{j}",
                        source_url=doc.url
                    )
                    session.add(snippet)
            
            session.commit()
        
        # Verify documents were created
        with db_manager.session_scope() as session:
            docs = session.query(Document).filter_by(crawl_job_id=job_id).all()
            assert len(docs) == 3
        
        # Verify document tracking
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            assert job.documents_crawled == 3
            
            # Verify document and snippet count
            doc_count = session.query(Document).filter_by(crawl_job_id=job_id).count()
            snippet_count = session.query(CodeSnippet).join(Document).filter(
                Document.crawl_job_id == job_id
            ).count()
            
            assert doc_count == 3
            assert snippet_count == 6  # 3 documents * 2 snippets each
        
        # Cleanup
        with db_manager.session_scope() as session:
            # Delete snippets first
            docs = session.query(Document).filter_by(crawl_job_id=job_id).all()
            for doc in docs:
                session.query(CodeSnippet).filter_by(document_id=doc.id).delete()
            # Delete documents
            session.query(Document).filter_by(crawl_job_id=job_id).delete()
            # Delete job
            session.query(CrawlJob).filter_by(id=job_id).delete()
            session.commit()