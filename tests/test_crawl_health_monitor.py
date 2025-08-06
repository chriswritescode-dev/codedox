"""Focused tests for crawl health monitoring and recovery."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.crawler.health_monitor import CrawlHealthMonitor, STALLED_THRESHOLD, get_health_monitor
from src.database.models import CrawlJob
from src.database import get_db_manager


class TestHealthMonitor:
    """Test the crawl health monitoring system."""
    
    def test_health_monitor_singleton(self):
        """Test that get_health_monitor returns singleton instance."""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        assert monitor1 is monitor2
    
    @pytest.mark.asyncio
    async def test_detect_stalled_jobs(self):
        """Test detection of stalled crawl jobs."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        # Create test jobs
        healthy_job_id = str(uuid4())
        stalled_job_id = str(uuid4())
        completed_job_id = str(uuid4())
        
        with db_manager.session_scope() as session:
            # Healthy running job
            healthy_job = CrawlJob(
                id=healthy_job_id,
                name="Healthy Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow(),
                crawl_phase="crawling"
            )
            
            # Stalled job
            stalled_job = CrawlJob(
                id=stalled_job_id,
                name="Stalled Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 10),
                crawl_phase="crawling",
                processed_pages=5
            )
            
            # Completed job (should be ignored)
            completed_job = CrawlJob(
                id=completed_job_id,
                name="Completed Job",
                start_urls=["https://example.com"],
                status="completed",
                completed_at=datetime.utcnow()
            )
            
            session.add_all([healthy_job, stalled_job, completed_job])
            session.commit()
        
        # Get stalled jobs
        stalled_ids = monitor.get_stalled_jobs()
        assert stalled_job_id in stalled_ids
        assert healthy_job_id not in stalled_ids
        assert completed_job_id not in stalled_ids
        
        # Run health check
        await monitor._check_stalled_jobs()
        
        # Verify stalled job was marked as failed
        with db_manager.session_scope() as session:
            stalled = session.query(CrawlJob).filter_by(id=stalled_job_id).first()
            assert stalled.status == "completed"
            assert "stalled" in stalled.error_message.lower()
            assert "crawling" in stalled.error_message
            assert stalled.completed_at is not None
            
            # Healthy job should be unchanged
            healthy = session.query(CrawlJob).filter_by(id=healthy_job_id).first()
            assert healthy.status == "running"
            assert healthy.error_message is None
    
    def test_job_health_status(self):
        """Test individual job health status checking."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        job_id = str(uuid4())
        
        # Create job in different states over time
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Test Job",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=datetime.utcnow(),
                crawl_phase="crawling"
            )
            session.add(job)
            session.commit()
        
        # Check healthy status
        health = monitor.check_job_health(job_id)
        assert health["is_healthy"] is True
        assert health["health_status"] == "healthy"
        assert health["phase"] == "crawling"
        assert "seconds_since_heartbeat" in health
        
        # Update to warning state
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.last_heartbeat = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD/2 + 10)
            session.commit()
        
        health = monitor.check_job_health(job_id)
        assert health["is_healthy"] is True
        assert health["health_status"] == "warning"
        
        # Update to stalled state
        with db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            job.last_heartbeat = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 10)
            session.commit()
        
        health = monitor.check_job_health(job_id)
        assert health["is_healthy"] is False  # Stalled = not healthy
        assert health["health_status"] == "stalled"
        
        # Test non-existent job
        fake_id = str(uuid4())
        health = monitor.check_job_health(fake_id)
        assert health["status"] == "not_found"
    
    @pytest.mark.asyncio
    async def test_multiple_stalled_jobs(self):
        """Test handling multiple stalled jobs at once."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        # Create multiple stalled jobs
        stalled_ids = []
        with db_manager.session_scope() as session:
            for i in range(3):
                job = CrawlJob(
                    id=uuid4(),
                    name=f"Stalled Job {i}",
                    start_urls=[f"https://example{i}.com"],
                    status="running",
                    last_heartbeat=datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 60 + i*10),
                    crawl_phase="crawling"
                )
                session.add(job)
                stalled_ids.append(str(job.id))
            session.commit()
        
        # Check all are detected
        detected = monitor.get_stalled_jobs()
        for job_id in stalled_ids:
            assert job_id in detected
        
        # Mark all as failed
        await monitor._check_stalled_jobs()
        
        # Verify all were marked as failed
        with db_manager.session_scope() as session:
            for job_id in stalled_ids:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                assert job.status == "completed"
                assert job.error_message is not None
    
    @pytest.mark.asyncio
    async def test_phase_tracking_in_errors(self):
        """Test that error messages include the phase where failure occurred."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        phases = ["crawling", "finalizing"]
        job_ids = []
        
        with db_manager.session_scope() as session:
            for phase in phases:
                job = CrawlJob(
                    id=uuid4(),
                    name=f"Job in {phase}",
                    start_urls=["https://example.com"],
                    status="running",
                    last_heartbeat=datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD + 30),
                    crawl_phase=phase
                )
                session.add(job)
                job_ids.append((str(job.id), phase))
            session.commit()
        
        # Run health check
        await monitor._check_stalled_jobs()
        
        # Verify phase is in error message
        with db_manager.session_scope() as session:
            for job_id, expected_phase in job_ids:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                assert job.status == "completed"
                assert expected_phase in job.error_message
    
    def test_heartbeat_timing(self):
        """Test heartbeat timing calculations."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        job_id = str(uuid4())
        
        # Create job with specific heartbeat
        test_time = datetime.utcnow() - timedelta(seconds=123)
        with db_manager.session_scope() as session:
            job = CrawlJob(
                id=job_id,
                name="Timing Test",
                start_urls=["https://example.com"],
                status="running",
                last_heartbeat=test_time
            )
            session.add(job)
            session.commit()
        
        health = monitor.check_job_health(job_id)
        assert "seconds_since_heartbeat" in health
        # Should be approximately 123 seconds (allow small variance)
        assert 120 < health["seconds_since_heartbeat"] < 130
    
    @pytest.mark.asyncio
    async def test_completed_jobs_not_marked_stalled(self):
        """Test that completed/failed jobs are not marked as stalled."""
        db_manager = get_db_manager()
        monitor = CrawlHealthMonitor()
        
        # Create jobs in final states with old heartbeats
        job_ids = []
        with db_manager.session_scope() as session:
            for status in ["completed", "failed", "cancelled"]:
                job = CrawlJob(
                    id=uuid4(),
                    name=f"{status} Job",
                    start_urls=["https://example.com"],
                    status=status,
                    last_heartbeat=datetime.utcnow() - timedelta(hours=1),
                    completed_at=datetime.utcnow() if status == "completed" else None
                )
                session.add(job)
                job_ids.append(str(job.id))
            session.commit()
        
        # Check none are detected as stalled
        stalled = monitor.get_stalled_jobs()
        for job_id in job_ids:
            assert job_id not in stalled
        
        # Run health check
        await monitor._check_stalled_jobs()
        
        # Verify none were changed
        with db_manager.session_scope() as session:
            for job_id in job_ids:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                assert job.status in ["completed", "failed", "cancelled"]