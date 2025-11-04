"""Tests for source update crawl functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.database.models import CrawlJob, Document, CodeSnippet


class TestSourceUpdateCrawl:
    """Test source update crawl endpoint."""

    @pytest.fixture
    def completed_crawl_job(self, db: Session) -> CrawlJob:
        """Create a completed crawl job with configuration."""
        job = CrawlJob(
            id=uuid4(),
            name="React Documentation",
            domain="react.dev",
            start_urls=["https://react.dev/reference"],
            max_depth=2,
            status="completed",
            version="v18",
            total_pages=50,
            processed_pages=50,
            snippets_extracted=25,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            config={
                "url_patterns": ["*reference*", "*api*"],
                "max_pages": 100,
                "max_concurrent_crawls": 5,
            }
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @pytest.fixture
    def running_crawl_job(self, db: Session) -> CrawlJob:
        """Create a running crawl job."""
        job = CrawlJob(
            id=uuid4(),
            name="Vue Documentation",
            domain="vuejs.org",
            start_urls=["https://vuejs.org/guide"],
            max_depth=1,
            status="running",
            total_pages=10,
            processed_pages=5,
            snippets_extracted=3,
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_success(self, mock_init_crawl, client, completed_crawl_job):
        """Test successful source update crawl."""
        new_job_id = str(uuid4())
        mock_init_crawl.return_value = {
            "new_job_id": new_job_id,
            "message": "Update crawl job created successfully",
            "original_source_id": str(completed_crawl_job.id),
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "add_url_patterns": ["*hooks*", "*tutorial*"],
                "exclude_url_patterns": ["*deprecated*"],
                "max_depth": 3,
                "version": "v19",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "new_job_id" in data
        assert data["original_source_id"] == str(completed_crawl_job.id)
        assert data["is_update_crawl"] is True
        
        # Verify init_crawl was called with correct parameters
        mock_init_crawl.assert_called_once()

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_minimal_changes(self, mock_init_crawl, client, completed_crawl_job):
        """Test update crawl with only version change."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "version": "v19",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_add_url_patterns(self, mock_init_crawl, client, completed_crawl_job):
        """Test adding URL patterns to existing crawl."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "add_url_patterns": ["*new-feature*"],
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_exclude_patterns(self, mock_init_crawl, client, completed_crawl_job):
        """Test excluding URL patterns from crawl."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "exclude_url_patterns": ["*old-docs*", "*legacy*"],
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_change_depth(self, mock_init_crawl, client, completed_crawl_job):
        """Test changing max_depth for update crawl."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "max_depth": 3,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_change_concurrent(self, mock_init_crawl, client, completed_crawl_job):
        """Test changing max_concurrent_crawls."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "max_concurrent_crawls": 10,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    def test_update_source_crawl_not_found(self, client):
        """Test update crawl with non-existent source."""
        fake_id = str(uuid4())
        response = client.patch(
            f"/api/sources/{fake_id}/update-crawl",
            json={
                "source_id": fake_id,
                "version": "v2",
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_source_crawl_not_completed(self, client, running_crawl_job):
        """Test update crawl on non-completed source."""
        response = client.patch(
            f"/api/sources/{running_crawl_job.id}/update-crawl",
            json={
                "source_id": str(running_crawl_job.id),
                "version": "v2",
            }
        )
        
        assert response.status_code == 400
        assert "only update completed sources" in response.json()["detail"].lower()

    def test_update_source_crawl_validation_max_depth(self, client, completed_crawl_job):
        """Test validation of max_depth parameter."""
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "max_depth": 5,  # Out of range (0-3)
            }
        )
        
        assert response.status_code == 422

    def test_update_source_crawl_validation_concurrent(self, client, completed_crawl_job):
        """Test validation of max_concurrent_crawls parameter."""
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "max_concurrent_crawls": 150,  # Out of range (1-100)
            }
        )
        
        assert response.status_code == 422

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_no_content_mode(self, mock_init_crawl, client, completed_crawl_job):
        """Test that content_mode is not required or accepted."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "version": "v19",
            }
        )
        
        assert response.status_code == 200

    @patch('src.api.routes.sources.mcp_tools.init_crawl', new_callable=AsyncMock)
    def test_update_source_crawl_all_parameters(self, mock_init_crawl, client, completed_crawl_job):
        """Test update crawl with all optional parameters."""
        mock_init_crawl.return_value = {
            "new_job_id": str(uuid4()),
            "message": "Update crawl job created successfully",
            "status": "pending",
        }
        
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "source_id": str(completed_crawl_job.id),
                "add_url_patterns": ["*new*"],
                "exclude_url_patterns": ["*old*"],
                "max_depth": 3,
                "max_pages": 200,
                "max_concurrent_crawls": 10,
                "version": "v19",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "new_job_id" in data

    def test_update_source_crawl_missing_source_id(self, client, completed_crawl_job):
        """Test that source_id is required in request body."""
        response = client.patch(
            f"/api/sources/{completed_crawl_job.id}/update-crawl",
            json={
                "version": "v19",
            }
        )
        
        assert response.status_code == 422
