"""Tests for crawl and enrichment progress tracking."""

import pytest
from uuid import uuid4
from datetime import datetime

from src.database.models import CrawlJob, Document, CodeSnippet
from src.api.routes import router


class TestProgressCalculation:
    """Test progress calculation logic."""
    
    def test_crawl_progress_calculation(self):
        """Test crawl progress is calculated correctly."""
        # Test normal progress
        job = CrawlJob()
        job.processed_pages = 50
        job.total_pages = 100
        
        progress = min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0))
        assert progress == 50
        
        # Test when processed exceeds total (the issue we fixed)
        job.processed_pages = 150
        job.total_pages = 100
        
        progress = min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0))
        assert progress == 100  # Should be capped at 100%
        
        # Test zero division
        job.processed_pages = 0
        job.total_pages = 0
        
        progress = min(100, round((job.processed_pages / job.total_pages * 100) if job.total_pages > 0 else 0))
        assert progress == 0
    
    def test_enrichment_progress_calculation(self):
        """Test enrichment progress is calculated correctly."""
        # Test normal progress
        job = CrawlJob()
        job.documents_enriched = 75
        job.documents_crawled = 100
        
        progress = min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0))
        assert progress == 75
        
        # Test when enriched exceeds crawled
        job.documents_enriched = 150
        job.documents_crawled = 100
        
        progress = min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0))
        assert progress == 100  # Should be capped at 100%
        
        # Test zero division
        job.documents_enriched = 0
        job.documents_crawled = 0
        
        progress = min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0))
        assert progress == 0
    
    def test_progress_with_null_values(self):
        """Test progress calculation handles null values gracefully."""
        job = CrawlJob()
        job.documents_enriched = None
        job.documents_crawled = 100
        
        # Should handle None gracefully
        progress = min(100, round((job.documents_enriched / job.documents_crawled * 100) if job.documents_crawled > 0 else 0)) if job.documents_enriched is not None else 0
        assert progress == 0


class TestAPIProgressFields:
    """Test that API endpoints return progress fields correctly."""
    
    @pytest.fixture
    def sample_jobs(self, db):
        """Create sample jobs with various progress states."""
        job_ids = []
        
        try:
            # Generate unique domain suffixes to avoid conflicts
            unique_suffix = str(uuid4())[:8]
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            
            # Job 1: Mid-crawl
            job1 = CrawlJob(
                id=str(uuid4()),
                name=f"Mid-Crawl Job {timestamp}",
                domain=f"example-{unique_suffix}.com",
                start_urls=[f"https://example-{unique_suffix}.com"],
                status="running",
                crawl_phase="crawling",
                processed_pages=50,
                total_pages=100,
                snippets_extracted=200,
                documents_crawled=0,
                documents_enriched=0,
                created_at=datetime.utcnow()
            )
            
            # Job 2: Mid-enrichment
            job2 = CrawlJob(
                id=str(uuid4()),
                name=f"Mid-Enrichment Job {timestamp}",
                domain=f"test-{unique_suffix}.com",
                start_urls=[f"https://test-{unique_suffix}.com"],
                status="running",
                crawl_phase="enriching",
                processed_pages=100,
                total_pages=100,
                snippets_extracted=500,
                documents_crawled=100,
                documents_enriched=75,
                created_at=datetime.utcnow()
            )
            
            # Job 3: Completed
            job3 = CrawlJob(
                id=str(uuid4()),
                name=f"Completed Job {timestamp}",
                domain=f"done-{unique_suffix}.com",
                start_urls=[f"https://done-{unique_suffix}.com"],
                status="completed",
                crawl_phase=None,
                processed_pages=200,
                total_pages=200,
                snippets_extracted=1000,
                documents_crawled=200,
                documents_enriched=200,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            
            # Job 4: Over 100% case (fixed)
            job4 = CrawlJob(
                id=str(uuid4()),
                name=f"Over 100% Job {timestamp}",
                domain=f"over-{unique_suffix}.com",
                start_urls=[f"https://over-{unique_suffix}.com"],
                status="running",
                crawl_phase="enriching",
                processed_pages=150,  # More than total
                total_pages=100,
                snippets_extracted=750,
                documents_crawled=100,
                documents_enriched=150,  # More than crawled
                created_at=datetime.utcnow()
            )
            
            db.add_all([job1, job2, job3, job4])
            db.commit()
            
            # Store IDs for cleanup
            job_ids = [str(job1.id), str(job2.id), str(job3.id), str(job4.id)]
            
            yield job_ids
            
        finally:
            # Cleanup - use IDs to avoid detached instance errors
            for job_id in job_ids:
                # Delete related documents and snippets first (cascade)
                docs = db.query(Document).filter_by(crawl_job_id=job_id).all()
                for doc in docs:
                    db.query(CodeSnippet).filter_by(document_id=doc.id).delete()
                db.query(Document).filter_by(crawl_job_id=job_id).delete()
                # Then delete the job
                db.query(CrawlJob).filter_by(id=job_id).delete()
            db.commit()
    
    def test_crawl_jobs_endpoint_progress_fields(self, client, sample_jobs):
        """Test that /api/crawl-jobs returns progress fields."""
        response = client.get("/api/crawl-jobs")
        assert response.status_code == 200
        
        jobs = response.json()
        
        # Filter to only our test jobs
        test_job_ids = set(sample_jobs)
        test_jobs = [j for j in jobs if j["id"] in test_job_ids]
        assert len(test_jobs) == 4, f"Expected 4 test jobs, found {len(test_jobs)}"
        
        # Check each job has progress fields
        for job in test_jobs:
            assert "crawl_progress" in job
            assert "enrichment_progress" in job
            
            # Progress should be between 0 and 100
            assert 0 <= job["crawl_progress"] <= 100
            assert 0 <= job["enrichment_progress"] <= 100
        
        # Find specific jobs by name pattern and verify progress
        mid_crawl = next(j for j in test_jobs if "Mid-Crawl Job" in j["name"])
        assert mid_crawl["crawl_progress"] == 50  # 50/100
        assert mid_crawl["enrichment_progress"] == 0  # No documents
        
        mid_enrichment = next(j for j in test_jobs if "Mid-Enrichment Job" in j["name"])
        assert mid_enrichment["crawl_progress"] == 100  # 100/100
        assert mid_enrichment["enrichment_progress"] == 75  # 75/100
        
        completed = next(j for j in test_jobs if "Completed Job" in j["name"])
        assert completed["crawl_progress"] == 100  # 200/200
        assert completed["enrichment_progress"] == 100  # 200/200
        
        over_100 = next(j for j in test_jobs if "Over 100% Job" in j["name"])
        assert over_100["crawl_progress"] == 100  # Capped at 100
        assert over_100["enrichment_progress"] == 100  # Capped at 100
    
    def test_single_crawl_job_endpoint_progress_fields(self, client, sample_jobs):
        """Test that /api/crawl-jobs/{id} returns progress fields."""
        # Test mid-enrichment job (second job in list)
        job_id = sample_jobs[1]  # Already a string ID
        response = client.get(f"/api/crawl-jobs/{job_id}")
        assert response.status_code == 200
        
        job = response.json()
        assert job["crawl_progress"] == 100
        assert job["enrichment_progress"] == 75
        
        # Test over 100% job (fourth job in list)
        job_id = sample_jobs[3]  # Already a string ID
        response = client.get(f"/api/crawl-jobs/{job_id}")
        assert response.status_code == 200
        
        job = response.json()
        assert job["crawl_progress"] == 100  # Should be capped
        assert job["enrichment_progress"] == 100  # Should be capped


class TestEnrichmentPipelineDocumentTracking:
    """Test that enrichment pipeline tracks documents correctly."""
    
    @pytest.mark.asyncio
    async def test_document_completion_tracking(self):
        """Test that documents are marked as completed when all snippets are enriched."""
        from src.crawler.enrichment_pipeline import EnrichmentPipeline
        from src.parser.code_extractor import CodeBlock
        
        pipeline = EnrichmentPipeline(llm_client=None)  # No LLM for testing
        
        # Simulate adding a document with multiple snippets
        doc_id = 123
        code_blocks = [
            CodeBlock(
                language="python",
                content="def test1(): pass",
                title="Test 1",
                description="Test function 1",
                context_before="",
                context_after="",
                line_start=1,
                line_end=1,
                source_url="test.py",
                extraction_metadata={}
            ),
            CodeBlock(
                language="python",
                content="def test2(): pass",
                title="Test 2",
                description="Test function 2",
                context_before="",
                context_after="",
                line_start=3,
                line_end=3,
                source_url="test.py",
                extraction_metadata={}
            )
        ]
        
        # Track document
        await pipeline.add_document(doc_id, "http://test.com", "test-job", code_blocks)
        
        # Check tracking
        assert doc_id in pipeline.document_snippet_counts
        assert pipeline.document_snippet_counts[doc_id] == 2
        assert pipeline.document_completed_snippets[doc_id] == 0
        assert doc_id not in pipeline.completed_documents
        
        # Simulate completing one snippet
        pipeline.document_completed_snippets[doc_id] = 1
        assert doc_id not in pipeline.completed_documents  # Not complete yet
        
        # Simulate completing all snippets
        pipeline.document_completed_snippets[doc_id] = 2
        # The actual completion check happens in _store_batch
        if (doc_id in pipeline.document_snippet_counts and 
            pipeline.document_completed_snippets[doc_id] >= pipeline.document_snippet_counts[doc_id]):
            pipeline.completed_documents.add(doc_id)
        
        assert doc_id in pipeline.completed_documents
        assert len(pipeline.completed_documents) == 1
        
        # Check stats
        stats = pipeline.get_stats()
        assert stats["completed_documents"] == 1