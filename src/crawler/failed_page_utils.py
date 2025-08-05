"""Utility functions for recording failed pages."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from ..database import CrawlJob, FailedPage, get_db_manager

logger = logging.getLogger(__name__)


async def record_failed_page(job_id: str, url: str, error_message: str) -> None:
    """Record a failed page.

    Args:
        job_id: Job ID
        url: Failed URL
        error_message: Error message
    """
    try:
        # Handle job_id format
        try:
            job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        except ValueError:
            logger.error(f"Invalid job ID format: {job_id}")
            return

        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            # Check if crawl job exists
            crawl_job = session.query(CrawlJob).filter_by(id=job_uuid).first()
            if not crawl_job:
                logger.warning(f"Crawl job {job_uuid} not found - skipping failed page recording")
                return

            # Check if job is cancelled
            if crawl_job.status == "cancelled":
                logger.info(f"Crawl job {job_uuid} is cancelled - stopping crawler")
                raise asyncio.CancelledError("Job cancelled by user")

            # Check if already exists
            existing = session.query(FailedPage).filter_by(crawl_job_id=job_uuid, url=url).first()
            if not existing:
                failed_page = FailedPage(
                    crawl_job_id=job_uuid,
                    url=url,
                    error_message=error_message,
                    failed_at=datetime.now(timezone.utc),
                )
                session.add(failed_page)
                session.commit()
                logger.info(f"Recorded failed page: {url} - {error_message}")
    except asyncio.CancelledError:
        raise  # Re-raise cancellation
    except Exception as e:
        logger.error(f"Failed to record failed page {url}: {e}")


async def record_failed_pages_batch(job_id: str, urls: list[str], error_message: str) -> None:
    """Record multiple failed pages at once.

    Args:
        job_id: Job ID
        urls: List of failed URLs
        error_message: Error message for all URLs
    """
    for url in urls:
        await record_failed_page(job_id, url, error_message)
