"""Tests for crawl job deletion endpoints."""
import hashlib
from uuid import uuid4

from sqlalchemy.orm import Session

from src.database.models import CodeSnippet, CrawlJob, Document


def test_delete_single_crawl_job_success(client, db: Session):
    """Test successful deletion of a single completed crawl job."""
    # Create a completed crawl job with associated data
    job = CrawlJob(
        id=uuid4(),
        name="Test Job",
        start_urls=["https://example.com"],
        status="completed",
        processed_pages=5,
        snippets_extracted=10
    )
    db.add(job)

    # Add a document
    doc = Document(
        crawl_job_id=job.id,
        url="https://example.com/page1",
        title="Test Page",
        content_type="html"
    )
    db.add(doc)

    # Add a code snippet
    code_content = "print('hello')"
    snippet = CodeSnippet(
        document_id=doc.id,
        code_content=code_content,
        code_hash=hashlib.md5(code_content.encode()).hexdigest(),
        language="python",
        line_start=1,
        line_end=1
    )
    db.add(snippet)
    db.commit()

    # Delete the job
    response = client.delete(f"/api/crawl-jobs/{job.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Crawl job deleted successfully"

    # Verify job and related data are deleted
    assert db.query(CrawlJob).filter_by(id=job.id).first() is None
    assert db.query(Document).filter_by(crawl_job_id=job.id).first() is None
    assert db.query(CodeSnippet).filter_by(document_id=doc.id).first() is None


def test_delete_single_crawl_job_not_found(client, db: Session):
    """Test deletion of non-existent crawl job."""
    fake_id = str(uuid4())
    response = client.delete(f"/api/crawl-jobs/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Crawl job not found"


def test_delete_running_crawl_job_fails(client, db: Session):
    """Test that running jobs cannot be deleted."""
    # Create a running crawl job
    job = CrawlJob(
        id=uuid4(),
        name="Running Job",
        start_urls=["https://example.com"],
        status="running"
    )
    db.add(job)
    db.commit()

    # Try to delete the running job
    response = client.delete(f"/api/crawl-jobs/{job.id}")
    assert response.status_code == 400
    assert "Cannot delete job with status 'running'" in response.json()["detail"]

    # Verify job still exists
    assert db.query(CrawlJob).filter_by(id=job.id).first() is not None


def test_bulk_delete_crawl_jobs_success(client, db: Session):
    """Test successful bulk deletion of multiple crawl jobs."""
    # Create multiple jobs with different statuses
    jobs = []
    # All deletable jobs must have status='completed'
    for i in range(3):
        job = CrawlJob(
            id=uuid4(),
            name=f"Test Job {i}",
            start_urls=[f"https://example{i}.com"],
            status="completed",
            processed_pages=i * 5,
            snippets_extracted=i * 10,
            error_message="Test error" if i == 1 else None  # Simulate one with error
        )
        jobs.append(job)
        db.add(job)

    db.commit()

    # Bulk delete the jobs
    job_ids = [str(job.id) for job in jobs]
    response = client.request("DELETE", "/api/crawl-jobs/bulk", json=job_ids)
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 3
    assert "Successfully deleted 3 job(s)" in response.json()["message"]

    # Verify all jobs are deleted
    for job_id in job_ids:
        assert db.query(CrawlJob).filter_by(id=job_id).first() is None


def test_bulk_delete_empty_list(client):
    """Test bulk delete with empty list of IDs."""
    response = client.request("DELETE", "/api/crawl-jobs/bulk", json=[])
    assert response.status_code == 400
    assert response.json()["detail"] == "No job IDs provided"


def test_bulk_delete_mixed_statuses(client, db: Session):
    """Test bulk delete with mix of deletable and non-deletable jobs."""
    # Create jobs with different statuses
    completed_job = CrawlJob(
        id=uuid4(),
        name="Completed Job",
        start_urls=["https://example.com"],
        status="completed"
    )
    running_job = CrawlJob(
        id=uuid4(),
        name="Running Job",
        start_urls=["https://example.com"],
        status="running"
    )
    pending_job = CrawlJob(
        id=uuid4(),
        name="Running Job 2",
        start_urls=["https://example.com"],
        status="running"
    )
    failed_job = CrawlJob(
        id=uuid4(),
        name="Completed Job 2",
        start_urls=["https://example.com"],
        status="completed",
        error_message="Test error"
    )

    db.add_all([completed_job, running_job, pending_job, failed_job])
    db.commit()

    # Try to bulk delete all jobs
    job_ids = [str(job.id) for job in [completed_job, running_job, pending_job, failed_job]]
    response = client.request("DELETE", "/api/crawl-jobs/bulk", json=job_ids)

    # Should only delete completed jobs (both completed_job and failed_job have status='completed')
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    assert "Successfully deleted 2 job(s)" in response.json()["message"]

    # Verify only deletable jobs were deleted
    assert db.query(CrawlJob).filter_by(id=completed_job.id).first() is None
    assert db.query(CrawlJob).filter_by(id=failed_job.id).first() is None  # This also has status='completed'
    assert db.query(CrawlJob).filter_by(id=running_job.id).first() is not None
    assert db.query(CrawlJob).filter_by(id=pending_job.id).first() is not None  # This has status='running'


def test_bulk_delete_nonexistent_jobs(client, db: Session):
    """Test bulk delete with non-existent job IDs."""
    fake_ids = [str(uuid4()) for _ in range(3)]
    response = client.request("DELETE", "/api/crawl-jobs/bulk", json=fake_ids)
    assert response.status_code == 404
    assert response.json()["detail"] == "No jobs found with provided IDs"


def test_cascade_delete_documents_and_snippets(client, db: Session):
    """Test that deleting a job cascades to documents and snippets."""
    # Create a job with multiple documents and snippets
    job = CrawlJob(
        id=uuid4(),
        name="Job with Data",
        start_urls=["https://example.com"],
        status="completed"
    )
    db.add(job)

    # Add multiple documents
    docs = []
    for i in range(3):
        doc = Document(
            crawl_job_id=job.id,
            url=f"https://example.com/page{i}",
            title=f"Page {i}",
            content_type="html"
        )
        docs.append(doc)
        db.add(doc)

    db.flush()

    # Add snippets to each document
    snippet_count = 0
    for doc in docs:
        for j in range(2):
            code_content = f"code_{snippet_count}"
            snippet = CodeSnippet(
                document_id=doc.id,
                code_content=code_content,
                code_hash=hashlib.md5(code_content.encode()).hexdigest(),
                language="python",
                line_start=j * 10,
                line_end=(j + 1) * 10
            )
            db.add(snippet)
            snippet_count += 1

    db.commit()

    # Verify data exists
    assert db.query(Document).filter_by(crawl_job_id=job.id).count() == 3
    assert db.query(CodeSnippet).join(Document).filter(Document.crawl_job_id == job.id).count() == 6

    # Delete the job
    response = client.delete(f"/api/crawl-jobs/{job.id}")
    assert response.status_code == 200

    # Verify all related data is deleted
    assert db.query(CrawlJob).filter_by(id=job.id).first() is None
    assert db.query(Document).filter_by(crawl_job_id=job.id).count() == 0
    assert db.query(CodeSnippet).join(Document).filter(Document.crawl_job_id == job.id).count() == 0
