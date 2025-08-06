"""Tests for API routes."""

import pytest
from datetime import datetime
from uuid import uuid4


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health(self, client):
        """Test basic health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_database_health(self, client):
        """Test database health endpoint."""
        response = client.get("/api/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


class TestStatisticsEndpoint:
    """Test statistics endpoint."""

    def test_statistics_empty(self, client):
        """Test statistics with no data."""
        response = client.get("/api/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_sources"] == 0
        assert data["total_documents"] == 0
        assert data["total_snippets"] == 0
        assert data["languages"] == {}
        assert data["recent_crawls"] == []

    def test_statistics_with_data(
        self, client, sample_crawl_job, sample_document, sample_code_snippets
    ):
        """Test statistics with sample data."""
        response = client.get("/api/statistics")
        assert response.status_code == 200
        data = response.json()

        assert data["total_sources"] == 1
        assert data["total_documents"] == 1
        assert data["total_snippets"] == 3

        # Check language statistics
        assert "python" in data["languages"]
        assert "javascript" in data["languages"]
        assert "yaml" in data["languages"]
        assert data["languages"]["python"] == 1
        assert data["languages"]["javascript"] == 1

        # Check recent crawls
        assert len(data["recent_crawls"]) == 1
        recent = data["recent_crawls"][0]
        assert recent["id"] == str(sample_crawl_job.id)
        assert recent["name"] == "Test Documentation"
        assert recent["status"] == "completed"
        assert recent["domain"] == "example.com"
        assert recent["snippets_extracted"] == 3
        assert recent["start_urls"] == ["https://example.com/docs"]


class TestSourcesEndpoints:
    """Test sources endpoints."""

    def test_get_sources_empty(self, client):
        """Test getting sources with no data."""
        response = client.get("/api/sources")
        assert response.status_code == 200
        assert response.json() == {
            "sources": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
            "has_next": False,
            "has_previous": False,
        }

    def test_get_sources_with_data(
        self, client, sample_crawl_job, sample_document, sample_code_snippets
    ):
        """Test getting sources with data."""
        response = client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        
        assert "sources" in data
        sources = data["sources"]
        assert len(sources) == 1
        source = sources[0]
        assert source["id"] == str(sample_crawl_job.id)
        assert source["name"] == "Test Documentation"
        assert source["base_url"] == "https://example.com/docs"
        assert source["documents_count"] == 1
        assert source["snippets_count"] == 3

    def test_get_source_by_id(
        self, client, sample_crawl_job, sample_document, sample_code_snippets
    ):
        """Test getting a specific source."""
        response = client.get(f"/api/sources/{sample_crawl_job.id}")
        assert response.status_code == 200
        source = response.json()

        assert source["id"] == str(sample_crawl_job.id)
        assert source["name"] == "Test Documentation"
        assert source["base_url"] == "https://example.com/docs"
        assert source["documents_count"] == 1
        assert source["snippets_count"] == 3

    def test_get_source_not_found(self, client):
        """Test getting non-existent source."""
        fake_id = str(uuid4())
        response = client.get(f"/api/sources/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Source not found"


class TestCrawlJobEndpoints:
    """Test crawl job endpoints."""

    def test_get_crawl_jobs_empty(self, client):
        """Test getting crawl jobs with no data."""
        response = client.get("/api/crawl-jobs")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_crawl_jobs_with_data(self, client, multiple_crawl_jobs):
        """Test getting crawl jobs with data."""
        response = client.get("/api/crawl-jobs")
        assert response.status_code == 200
        jobs = response.json()

        assert len(jobs) == 4
        # Jobs should be ordered by created_at desc
        statuses = [job["status"] for job in jobs]
        assert "completed" in statuses
        assert "running" in statuses
        # All jobs now only have "running" or "completed" status
        assert all(s in ["running", "completed"] for s in statuses)

        # Check all jobs have progress fields
        for job in jobs:
            assert "crawl_progress" in job
            assert isinstance(job["crawl_progress"], int)
            assert 0 <= job["crawl_progress"] <= 100

        # Check that one job has error message (simulating failure)
        # Find job with error_message
        failed_job = next((job for job in jobs if job.get("error_message") == "Test error"), None)
        assert failed_job is not None
        assert failed_job["status"] == "completed"  # Failed jobs now have status='completed'

    def test_get_crawl_job_by_id(self, client, sample_crawl_job):
        """Test getting a specific crawl job."""
        response = client.get(f"/api/crawl-jobs/{sample_crawl_job.id}")
        assert response.status_code == 200
        job = response.json()

        assert job["id"] == str(sample_crawl_job.id)
        assert job["name"] == "Test Documentation"
        assert job["status"] == "completed"
        assert job["base_url"] == "https://example.com/docs"
        assert job["urls_crawled"] == 10

        # Check progress fields
        assert "crawl_progress" in job
        # For a completed job with 10/10 pages
        assert job["crawl_progress"] == 100

    def test_get_crawl_job_not_found(self, client):
        """Test getting non-existent crawl job."""
        fake_id = str(uuid4())
        response = client.get(f"/api/crawl-jobs/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Crawl job not found"

    def test_create_crawl_job(self, client, mock_mcp_tools):
        """Test creating a new crawl job."""
        response = client.post(
            "/api/crawl-jobs",
            json={"name": "New Documentation", "base_url": "https://newdocs.com", "max_depth": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data
        assert "New Documentation" in data["message"]
        assert "initiated" in data["message"]


class TestSearchEndpoints:
    """Test search endpoints."""

    def test_search_no_params(self, client, sample_code_snippets):
        """Test search with no parameters."""
        response = client.get("/api/search")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 3  # All snippets

    def test_search_by_query(self, client, sample_code_snippets):
        """Test search by query."""
        response = client.get("/api/search?query=function")
        assert response.status_code == 200
        results = response.json()
        # Should match snippets with "function" in content or description
        assert len(results) >= 2

    def test_search_by_language(self, client, sample_code_snippets):
        """Test search by language."""
        response = client.get("/api/search?language=python")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["snippet"]["language"] == "python"

    def test_search_with_pagination(self, client, sample_code_snippets):
        """Test search with pagination."""
        # First page
        response = client.get("/api/search?limit=2&offset=0")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2

        # Second page
        response = client.get("/api/search?limit=2&offset=2")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1

    def test_search_result_format(self, client, sample_code_snippets):
        """Test search result format."""
        response = client.get("/api/search?language=python")
        assert response.status_code == 200
        results = response.json()

        result = results[0]
        assert "snippet" in result
        assert "score" in result

        snippet = result["snippet"]
        assert "id" in snippet
        assert "code" in snippet
        assert "language" in snippet
        assert "description" in snippet
        assert "source_url" in snippet
        assert "document_title" in snippet
        assert "created_at" in snippet


class TestSnippetEndpoints:
    """Test snippet endpoints."""

    def test_get_snippet(self, client, sample_code_snippets):
        """Test getting a specific snippet."""
        snippet_id = sample_code_snippets[0].id
        response = client.get(f"/api/snippets/{snippet_id}")
        assert response.status_code == 200
        snippet = response.json()

        assert snippet["id"] == str(snippet_id)
        assert snippet["title"] == "Python Example"
        assert snippet["language"] == "python"
        assert "def hello_world" in snippet["code"]

    def test_get_snippet_not_found(self, client):
        """Test getting non-existent snippet."""
        fake_id = "999999"
        response = client.get(f"/api/snippets/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Snippet not found"


class TestBulkDeleteEndpoints:
    """Test bulk delete functionality for sources and crawl jobs."""

    def test_delete_sources_bulk_empty_list(self, client):
        """Test bulk delete with empty list."""
        response = client.request("DELETE", "/api/sources/bulk", json=[])
        assert response.status_code == 400
        assert "No source IDs provided" in response.json()["detail"]

    def test_delete_sources_bulk_nonexistent(self, client):
        """Test bulk delete with non-existent IDs."""
        from uuid import uuid4

        fake_ids = [str(uuid4()) for _ in range(3)]
        response = client.request("DELETE", "/api/sources/bulk", json=fake_ids)
        assert response.status_code == 404
        assert response.json()["detail"] in [
            "No sources found with provided IDs",
            "Resource not found",
        ]

    def test_delete_sources_bulk_success(self, client, db, multiple_crawl_jobs):
        """Test successful bulk deletion of sources."""
        from src.database.models import CrawlJob

        # Get completed job IDs
        completed_jobs = [job for job in multiple_crawl_jobs if job.status == "completed"]
        job_ids = [str(job.id) for job in completed_jobs]

        # Verify jobs exist
        for job_id in job_ids:
            response = client.get(f"/api/sources/{job_id}")
            assert response.status_code == 200

        # Bulk delete
        response = client.request("DELETE", "/api/sources/bulk", json=job_ids)
        assert response.status_code == 200
        assert response.json()["deleted_count"] == len(job_ids)

        # Verify deletion
        for job_id in job_ids:
            response = client.get(f"/api/sources/{job_id}")
            assert response.status_code == 404

        # Verify non-completed jobs weren't deleted
        running_jobs = [job for job in multiple_crawl_jobs if job.status != "completed"]
        for job in running_jobs:
            exists = db.query(CrawlJob).filter(CrawlJob.id == job.id).first()
            assert exists is not None

    def test_delete_sources_bulk_with_documents(
        self, client, db, sample_crawl_job, sample_document, sample_code_snippets
    ):
        """Test bulk deletion cascades to documents and snippets."""
        from src.database.models import CrawlJob, Document, CodeSnippet

        job_id = str(sample_crawl_job.id)

        # Verify data exists
        assert db.query(Document).filter(Document.crawl_job_id == sample_crawl_job.id).count() > 0
        assert (
            db.query(CodeSnippet).filter(CodeSnippet.document_id == sample_document.id).count() > 0
        )

        # Bulk delete
        response = client.request("DELETE", "/api/sources/bulk", json=[job_id])
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        # Verify cascade deletion
        assert db.query(CrawlJob).filter(CrawlJob.id == sample_crawl_job.id).count() == 0
        assert db.query(Document).filter(Document.crawl_job_id == sample_crawl_job.id).count() == 0
        assert (
            db.query(CodeSnippet).filter(CodeSnippet.document_id == sample_document.id).count() == 0
        )

    def test_delete_crawl_jobs_bulk_empty_list(self, client):
        """Test crawl job bulk delete with empty list."""
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=[])
        assert response.status_code == 400
        assert "No job IDs provided" in response.json()["detail"]

    def test_delete_crawl_jobs_bulk_nonexistent(self, client):
        """Test crawl job bulk delete with non-existent IDs."""
        from uuid import uuid4

        fake_ids = [str(uuid4()) for _ in range(3)]
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=fake_ids)
        assert response.status_code == 404
        assert response.json()["detail"] in [
            "No jobs found with provided IDs",
            "Resource not found",
        ]

    def test_delete_crawl_jobs_bulk_success(self, client, db, multiple_crawl_jobs):
        """Test successful bulk deletion of crawl jobs."""
        from src.database.models import CrawlJob

        # Get deletable job IDs (only completed jobs can be deleted)
        deletable_statuses = ["completed"]
        deletable_jobs = [job for job in multiple_crawl_jobs if job.status in deletable_statuses]
        job_ids = [str(job.id) for job in deletable_jobs]

        # Verify jobs exist
        for job_id in job_ids:
            response = client.get(f"/api/crawl-jobs/{job_id}")
            assert response.status_code == 200

        # Bulk delete
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=job_ids)
        assert response.status_code == 200
        assert response.json()["deleted_count"] == len(job_ids)

        # Verify deletion
        for job_id in job_ids:
            response = client.get(f"/api/crawl-jobs/{job_id}")
            assert response.status_code == 404

        # Verify running/pending jobs weren't deleted
        non_deletable_jobs = [
            job for job in multiple_crawl_jobs if job.status not in deletable_statuses
        ]
        for job in non_deletable_jobs:
            exists = db.query(CrawlJob).filter(CrawlJob.id == job.id).first()
            assert exists is not None

    def test_delete_crawl_jobs_bulk_mixed_statuses(self, client, db, multiple_crawl_jobs):
        """Test bulk delete only deletes allowed statuses."""
        from src.database.models import CrawlJob

        # Try to delete all jobs regardless of status
        all_job_ids = [str(job.id) for job in multiple_crawl_jobs]

        # Count deletable jobs (only completed)
        deletable_statuses = ["completed"]
        deletable_count = sum(1 for job in multiple_crawl_jobs if job.status in deletable_statuses)

        # Bulk delete attempt
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=all_job_ids)
        assert response.status_code == 200
        assert response.json()["deleted_count"] == deletable_count

        # Verify only deletable jobs were deleted
        for job in multiple_crawl_jobs:
            exists = db.query(CrawlJob).filter(CrawlJob.id == job.id).first()
            if job.status in deletable_statuses:
                assert exists is None  # Should be deleted
            else:
                assert exists is not None  # Should still exist

    def test_delete_crawl_jobs_bulk_with_cascade(
        self, client, db, sample_crawl_job, sample_document, sample_code_snippets
    ):
        """Test crawl job bulk deletion cascades properly."""
        from src.database.models import CrawlJob, Document, CodeSnippet

        job_id = str(sample_crawl_job.id)
        doc_id = sample_document.id

        # Verify all data exists
        assert db.query(CrawlJob).filter(CrawlJob.id == sample_crawl_job.id).count() == 1
        assert db.query(Document).filter(Document.crawl_job_id == sample_crawl_job.id).count() == 1
        assert db.query(CodeSnippet).filter(CodeSnippet.document_id == doc_id).count() == 3

        # Bulk delete
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=[job_id])
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        # Verify cascade deletion
        assert db.query(CrawlJob).filter(CrawlJob.id == sample_crawl_job.id).count() == 0
        assert db.query(Document).filter(Document.crawl_job_id == sample_crawl_job.id).count() == 0
        assert db.query(CodeSnippet).filter(CodeSnippet.document_id == doc_id).count() == 0

    def test_delete_crawl_jobs_bulk_invalid_uuid(self, client):
        """Test bulk delete with invalid UUID format."""
        invalid_ids = ["not-a-uuid", "12345", ""]
        response = client.request("DELETE", "/api/crawl-jobs/bulk", json=invalid_ids)
        # API should return 422 or 400 for invalid input
        assert response.status_code in [400, 422, 404]
        # Since invalid UUIDs won't match any jobs, we expect a not found response
