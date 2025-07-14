"""Tests for domain uniqueness functionality."""

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.exc import IntegrityError
from src.database.models import CrawlJob
from src.crawler.domain_utils import (
    extract_domain, 
    extract_domains_from_urls, 
    get_primary_domain, 
    domains_match
)
from src.crawler.crawl_manager import CrawlManager
from src.crawler import CrawlConfig


class TestDomainUtils:
    """Test domain utility functions."""
    
    def test_extract_domain_valid_urls(self):
        """Test extracting domains from valid URLs."""
        test_cases = [
            ("https://nextjs.org/docs", "nextjs.org"),
            ("http://example.com/path", "example.com"),
            ("https://www.github.com", "www.github.com"),
            ("nextjs.org", "nextjs.org"),
            ("https://subdomain.domain.com/path?query=1", "subdomain.domain.com"),
        ]
        
        for url, expected_domain in test_cases:
            assert extract_domain(url) == expected_domain
    
    def test_extract_domain_invalid_urls(self):
        """Test extracting domains from invalid URLs."""
        invalid_urls = ["", "not-a-url", "://invalid", "http://"]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                extract_domain(url)
    
    def test_extract_domains_from_urls(self):
        """Test extracting unique domains from URL list."""
        urls = [
            "https://nextjs.org/docs",
            "https://nextjs.org/guide", 
            "https://react.dev/learn",
            "invalid-url",
            "https://nextjs.org/api"  # Duplicate domain
        ]
        
        domains = extract_domains_from_urls(urls)
        assert domains == ["nextjs.org", "react.dev"]
    
    def test_get_primary_domain(self):
        """Test getting primary domain from start URLs."""
        urls = ["https://nextjs.org/docs", "https://nextjs.org/guide"]
        assert get_primary_domain(urls) == "nextjs.org"
        
        # Test with empty list
        assert get_primary_domain([]) is None
        
        # Test with invalid URLs
        assert get_primary_domain(["invalid-url"]) is None
    
    def test_domains_match(self):
        """Test domain matching functionality."""
        assert domains_match("https://nextjs.org/docs", "https://nextjs.org/guide") is True
        assert domains_match("https://nextjs.org", "https://react.dev") is False
        assert domains_match("invalid-url", "https://nextjs.org") is False


class TestCrawlJobDomainUniqueness:
    """Test crawl job domain uniqueness constraints."""
    
    def test_crawl_job_domain_constraint(self, db):
        """Test that database enforces domain uniqueness."""
        # Create first crawl job
        job1 = CrawlJob(
            name="Test Job 1",
            domain="nextjs.org",
            start_urls=["https://nextjs.org/docs"],
            max_depth=1
        )
        db.add(job1)
        db.commit()
        
        # Try to create second job with same domain
        job2 = CrawlJob(
            name="Test Job 2", 
            domain="nextjs.org",
            start_urls=["https://nextjs.org/guide"],
            max_depth=2
        )
        db.add(job2)
        
        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db.commit()
    
    def test_crawl_job_different_domains(self, db):
        """Test that different domains can coexist."""
        # Create jobs with different domains
        job1 = CrawlJob(
            name="NextJS Job",
            domain="nextjs.org", 
            start_urls=["https://nextjs.org/docs"],
            max_depth=1
        )
        job2 = CrawlJob(
            name="React Job",
            domain="react.dev",
            start_urls=["https://react.dev/learn"], 
            max_depth=1
        )
        
        db.add(job1)
        db.add(job2)
        db.commit()  # Should succeed
        
        # Verify both jobs exist
        jobs = db.query(CrawlJob).all()
        assert len(jobs) == 2
        domains = {job.domain for job in jobs}
        assert domains == {"nextjs.org", "react.dev"}


class TestCrawlManagerDomainReuse:
    """Test crawl manager domain reuse functionality."""
    
    @pytest.fixture
    def crawl_manager(self):
        """Create crawl manager instance."""
        return CrawlManager()
    
    @pytest.fixture
    def sample_config(self):
        """Create sample crawl configuration."""
        return CrawlConfig(
            name="Test Crawl",
            start_urls=["https://nextjs.org/docs"],
            max_depth=1,
            domain_restrictions=["nextjs.org"]
        )
    
    @patch('src.crawler.crawl_manager.asyncio.create_task')
    async def test_start_crawl_new_domain(self, mock_create_task, crawl_manager, sample_config, db):
        """Test starting crawl for new domain creates new job."""
        mock_create_task.return_value = AsyncMock()
        
        job_id = await crawl_manager.start_crawl(sample_config)
        
        # Verify job was created
        job = db.query(CrawlJob).filter_by(id=job_id).first()
        assert job is not None
        assert job.domain == "nextjs.org"
        assert job.name == "Test Crawl"
        assert job.status == "running"
        
        # Verify async task was started
        mock_create_task.assert_called_once()
    
    @patch('src.crawler.crawl_manager.asyncio.create_task')
    async def test_start_crawl_existing_domain_reuses_job(self, mock_create_task, crawl_manager, sample_config, db):
        """Test starting crawl for existing domain reuses existing job."""
        mock_create_task.return_value = AsyncMock()
        
        # Create existing job
        existing_job = CrawlJob(
            name="Old Crawl",
            domain="nextjs.org",
            start_urls=["https://nextjs.org/old"],
            max_depth=2,
            status="completed"
        )
        db.add(existing_job)
        db.commit()
        existing_job_id = str(existing_job.id)
        
        # Start new crawl with same domain
        job_id = await crawl_manager.start_crawl(sample_config)
        
        # Should return same job ID
        assert job_id == existing_job_id
        
        # Verify job was updated, not created
        job = db.query(CrawlJob).filter_by(id=job_id).first()
        assert job.name == "Test Crawl"  # Updated name
        assert job.start_urls == ["https://nextjs.org/docs"]  # Updated URLs
        assert job.max_depth == 1  # Updated depth
        assert job.status == "running"  # Reset status
        assert job.domain == "nextjs.org"  # Same domain
        
        # Verify only one job exists for this domain
        jobs_count = db.query(CrawlJob).filter_by(domain="nextjs.org").count()
        assert jobs_count == 1
        
        # Verify async task was started
        mock_create_task.assert_called_once()
    
    async def test_start_crawl_invalid_domain(self, crawl_manager):
        """Test starting crawl with invalid URLs raises error."""
        invalid_config = CrawlConfig(
            name="Invalid Crawl",
            start_urls=["invalid-url"],
            max_depth=1
        )
        
        with pytest.raises(ValueError, match="No valid domain found"):
            await crawl_manager.start_crawl(invalid_config)


class TestDomainApiIntegration:
    """Test API integration with domain functionality."""
    
    def test_get_crawl_jobs_includes_domain(self, client, sample_crawl_job):
        """Test that get crawl jobs API includes domain field."""
        # Set domain on sample job
        sample_crawl_job.domain = "nextjs.org"
        
        response = client.get("/api/crawl-jobs")
        assert response.status_code == 200
        
        jobs = response.json()
        assert len(jobs) > 0
        assert "domain" in jobs[0]
        assert jobs[0]["domain"] == "nextjs.org"
    
    def test_get_crawl_job_includes_domain(self, client, sample_crawl_job):
        """Test that get single crawl job API includes domain field."""
        # Set domain on sample job
        sample_crawl_job.domain = "nextjs.org"
        
        response = client.get(f"/api/crawl-jobs/{sample_crawl_job.id}")
        assert response.status_code == 200
        
        job = response.json()
        assert "domain" in job
        assert job["domain"] == "nextjs.org"
    
    def test_get_sources_includes_domain(self, client, sample_crawl_job):
        """Test that get sources API includes domain field."""
        # Set domain and mark as completed
        sample_crawl_job.domain = "nextjs.org"
        sample_crawl_job.status = "completed"
        
        response = client.get("/api/sources")
        assert response.status_code == 200
        
        sources = response.json()
        assert len(sources) > 0
        assert "domain" in sources[0]
        assert sources[0]["domain"] == "nextjs.org"


@pytest.mark.integration
class TestDomainUniquenessEndToEnd:
    """End-to-end tests for domain uniqueness."""
    
    def test_create_multiple_crawls_same_domain_via_api(self, client):
        """Test creating multiple crawls for same domain via API reuses job."""
        # Create first crawl job
        response1 = client.post("/api/crawl-jobs", json={
            "name": "NextJS Docs",
            "base_url": "https://nextjs.org/docs",
            "max_depth": 1
        })
        assert response1.status_code == 200
        job1_data = response1.json()
        job1_id = job1_data["id"]
        
        # Create second crawl job with same domain
        response2 = client.post("/api/crawl-jobs", json={
            "name": "NextJS Guide", 
            "base_url": "https://nextjs.org/guide",
            "max_depth": 2
        })
        assert response2.status_code == 200
        job2_data = response2.json()
        job2_id = job2_data["id"]
        
        # Should return same job ID (reused existing job)
        assert job1_id == job2_id
        
        # Verify the second response shows updated configuration
        assert job2_data["library_name"] == "NextJS Guide"  # Updated to latest name
        assert job2_data["max_depth"] == 2  # Updated to latest depth
        assert job2_data["start_urls"] == ["https://nextjs.org/guide"]  # Updated URLs
    
    def test_create_crawls_different_domains_via_api(self, client):
        """Test creating crawls for different domains creates separate jobs."""
        # Create NextJS crawl job
        response1 = client.post("/api/crawl-jobs", json={
            "name": "NextJS Docs",
            "base_url": "https://nextjs.org/docs", 
            "max_depth": 1
        })
        assert response1.status_code == 200
        job1_data = response1.json()
        job1_id = job1_data["id"]
        
        # Create React crawl job (different domain)
        response2 = client.post("/api/crawl-jobs", json={
            "name": "React Docs",
            "base_url": "https://react.dev/learn",
            "max_depth": 1
        })
        assert response2.status_code == 200
        job2_data = response2.json()
        job2_id = job2_data["id"]
        
        # Should have different job IDs
        assert job1_id != job2_id
        
        # Verify each response has the correct domain restrictions
        assert job1_data["domain_restrictions"] == ["nextjs.org"]
        assert job2_data["domain_restrictions"] == ["react.dev"]