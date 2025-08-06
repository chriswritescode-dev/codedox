"""Health monitoring for crawl jobs."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from ..config import get_settings
from ..database import CrawlJob, get_db_manager

logger = logging.getLogger(__name__)
settings = get_settings()

# How often to check for stalled jobs (seconds)
HEALTH_CHECK_INTERVAL = 10  # Check every 10 seconds

# How long without heartbeat before considering job stalled (seconds)
STALLED_THRESHOLD = 60  # 1 minute


class CrawlHealthMonitor:
    """Monitor health of running crawl jobs."""

    def __init__(self) -> None:
        """Initialize the health monitor."""
        self.db_manager = get_db_manager()
        self.running = False

    async def start(self) -> None:
        """Start the health monitoring loop."""
        self.running = True
        logger.info("Starting crawl health monitor")

        while self.running:
            try:
                await self._check_stalled_jobs()
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def stop(self) -> None:
        """Stop the health monitoring loop."""
        logger.info("Stopping crawl health monitor")
        self.running = False

    async def _check_stalled_jobs(self) -> None:
        """Check for stalled jobs and mark them as failed."""
        with self.db_manager.session_scope() as session:
            # Find running jobs with old heartbeats
            cutoff_time = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD)

            stalled_jobs = session.query(CrawlJob).filter(
                CrawlJob.status == 'running',
                CrawlJob.last_heartbeat < cutoff_time
            ).all()

            for job in stalled_jobs:
                time_since_heartbeat = (datetime.utcnow() - job.last_heartbeat).total_seconds()
                logger.warning(
                    f"Job {job.id} appears stalled - no heartbeat for {time_since_heartbeat:.0f} seconds"
                )

                # Mark stalled job as completed
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.error_message = (
                    f"Job stalled - no heartbeat for {time_since_heartbeat:.0f} seconds. "
                    f"Last phase: {job.crawl_phase or 'unknown'}"
                )
                if job.snippets_extracted and job.snippets_extracted > 0:
                    logger.info(f"Job {job.id} stalled with {job.snippets_extracted} snippets - marking as completed")
                else:
                    logger.info(f"Job {job.id} stalled with no data - marking as completed")

                # Log which phase it failed in
                if job.crawl_phase:
                    logger.error(f"Job {job.id} stalled during {job.crawl_phase} phase")

            if stalled_jobs:
                session.commit()
                logger.info(f"Marked {len(stalled_jobs)} stalled jobs as failed")

    def get_stalled_jobs(self) -> list[str]:
        """Get list of currently stalled job IDs.
        
        Returns:
            List of job IDs that appear to be stalled
        """
        with self.db_manager.session_scope() as session:
            cutoff_time = datetime.utcnow() - timedelta(seconds=STALLED_THRESHOLD)

            stalled_jobs = session.query(CrawlJob).filter(
                CrawlJob.status == 'running',
                CrawlJob.last_heartbeat < cutoff_time
            ).all()

            return [str(job.id) for job in stalled_jobs]

    def check_job_health(self, job_id: str) -> dict[str, Any]:
        """Check health status of a specific job.
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Health status dictionary
        """
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()

            if not job:
                return {"status": "not_found"}

            health = {
                "job_id": str(job.id),
                "status": job.status,
                "phase": job.crawl_phase,
                "last_heartbeat": job.last_heartbeat.isoformat() if job.last_heartbeat else None,
            }

            if job.status == 'running' and job.last_heartbeat:
                time_since_heartbeat = (datetime.utcnow() - job.last_heartbeat).total_seconds()
                health["seconds_since_heartbeat"] = time_since_heartbeat
                health["is_healthy"] = time_since_heartbeat < STALLED_THRESHOLD

                if time_since_heartbeat > STALLED_THRESHOLD:
                    health["health_status"] = "stalled"
                elif time_since_heartbeat > 30:  # Warning at 30 seconds
                    health["health_status"] = "warning"
                else:
                    health["health_status"] = "healthy"
            else:
                health["is_healthy"] = True
                health["health_status"] = job.status

            return health


# Global instance
_health_monitor = None


def get_health_monitor() -> CrawlHealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = CrawlHealthMonitor()
    return _health_monitor
