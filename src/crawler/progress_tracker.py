"""Progress tracking and notification management."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

from .job_manager import JobManager

# Import at runtime to avoid circular imports
_notify_crawl_update = None

def _get_notify_function():
    """Get the notify function, importing it lazily."""
    global _notify_crawl_update
    if _notify_crawl_update is None:
        try:
            from ..api.websocket import notify_crawl_update
            _notify_crawl_update = notify_crawl_update
        except ImportError as e:
            logger.warning(f"Failed to import WebSocket notify function: {e}")
            # Fallback function
            async def dummy_notify(job_id: str, status: str, data: Dict[str, Any]) -> None:
                logger.debug(f"WebSocket notification skipped for job {job_id}: {status}")
            _notify_crawl_update = dummy_notify
    return _notify_crawl_update


logger = logging.getLogger(__name__)

# Constants
HEARTBEAT_INTERVAL = 5  # seconds
WS_UPDATE_INTERVAL = 3  # pages


class ProgressTracker:
    """Tracks crawl progress and sends notifications."""

    def __init__(self, job_manager: JobManager):
        """Initialize progress tracker.

        Args:
            job_manager: Job manager instance
        """
        self.job_manager = job_manager
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    async def start_tracking(self, job_id: str) -> None:
        """Start tracking progress for a job.

        Args:
            job_id: Job ID to track
        """
        # Cancel any existing task
        await self.stop_tracking(job_id)

        # Start new heartbeat task
        self._heartbeat_tasks[job_id] = asyncio.create_task(self._heartbeat_loop(job_id))

        # Send initial notification
        await self.send_update(
            job_id,
            "running",
            {
                "urls_crawled": 0,
                "total_pages": 1,
                "snippets_extracted": 0,
                "crawl_phase": "crawling",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def stop_tracking(self, job_id: str) -> None:
        """Stop tracking progress for a job.

        Args:
            job_id: Job ID to stop tracking
        """
        if job_id in self._heartbeat_tasks:
            task = self._heartbeat_tasks[job_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self._heartbeat_tasks[job_id]

    async def stop_all(self) -> None:
        """Stop all tracking tasks."""
        tasks = list(self._heartbeat_tasks.keys())
        for job_id in tasks:
            await self.stop_tracking(job_id)

    async def _heartbeat_loop(self, job_id: str) -> None:
        """Background task to update heartbeat periodically.

        Args:
            job_id: Job ID
        """
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                # Check if job is still active
                if not self.job_manager.is_job_active(job_id):
                    logger.info(f"Job {job_id} no longer active, stopping heartbeat")
                    break

                # Update heartbeat
                self.job_manager.update_heartbeat(job_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat task for job {job_id}: {e}")

    async def update_progress(
        self,
        job_id: str,
        phase: Optional[str] = None,
        processed_pages: Optional[int] = None,
        total_pages: Optional[int] = None,
        snippets_extracted: Optional[int] = None,
        documents_crawled: Optional[int] = None,
        documents_enriched: Optional[int] = None,
        current_url: Optional[str] = None,
        send_notification: bool = True,
    ) -> None:
        """Update job progress and optionally send notification.

        Args:
            job_id: Job ID
            phase: Current phase
            processed_pages: Pages processed
            total_pages: Total pages
            snippets_extracted: Snippets extracted
            documents_crawled: Documents crawled
            documents_enriched: Documents enriched
            current_url: Current URL being processed
            send_notification: Whether to send WebSocket notification
        """
        # Update job in database
        self.job_manager.update_job_progress(
            job_id,
            processed_pages=processed_pages,
            total_pages=total_pages,
            snippets_extracted=snippets_extracted,
            documents_crawled=documents_crawled,
            documents_enriched=documents_enriched,
        )

        if phase:
            self.job_manager.update_job_status(job_id, phase=phase)

        # Send WebSocket notification if requested
        if send_notification:
            # Get job status instead of job object to avoid DetachedInstanceError
            job_status = self.job_manager.get_job_status(job_id)
            if job_status:
                data = {
                    "urls_crawled": job_status.get("processed_pages", 0),
                    "total_pages": job_status.get("total_pages", 0),
                    "snippets_extracted": job_status.get("snippets_extracted", 0),
                    "crawl_phase": job_status.get("crawl_phase"),
                    "documents_crawled": job_status.get("documents_crawled", 0),
                    "documents_enriched": job_status.get("documents_enriched", 0),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                if current_url:
                    data["current_url"] = current_url

                # Calculate progress percentages
                total_pages = job_status.get("total_pages", 0)
                processed_pages = job_status.get("processed_pages", 0)
                if total_pages > 0:
                    data["crawl_progress"] = min(
                        100, round((processed_pages / total_pages * 100))
                    )

                documents_crawled = job_status.get("documents_crawled", 0)
                documents_enriched = job_status.get("documents_enriched", 0)
                if documents_crawled and documents_crawled > 0:
                    data["enrichment_progress"] = min(
                        100, round((documents_enriched / documents_crawled * 100))
                    )

                await self.send_update(job_id, "running", data)

    async def send_update(self, job_id: str, status: str, data: Dict[str, Any]) -> None:
        """Send WebSocket update notification.

        Args:
            job_id: Job ID
            status: Job status
            data: Update data
        """
        try:
            notify_func = _get_notify_function()
            await notify_func(job_id, status, data)
        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {e}")

    async def send_completion(
        self, job_id: str, success: bool = True, error: Optional[str] = None
    ) -> None:
        """Send completion notification.

        Args:
            job_id: Job ID
            success: Whether job completed successfully
            error: Error message if failed
        """
        # Get job status instead of job object to avoid DetachedInstanceError
        job_status = self.job_manager.get_job_status(job_id)
        if not job_status:
            return

        status = "completed" if success else "failed"
        data = {
            "processed_pages": job_status.get("processed_pages", 0),
            "total_pages": job_status.get("total_pages", 0),
            "snippets_extracted": job_status.get("snippets_extracted", 0),
            "documents_enriched": job_status.get("documents_enriched", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }

        if error:
            data["error"] = error

        await self.send_update(job_id, status, data)

    def should_send_update(
        self, current_count: int, last_update_count: int, interval: int = WS_UPDATE_INTERVAL
    ) -> bool:
        """Check if we should send an update based on interval.

        Args:
            current_count: Current count
            last_update_count: Last update count
            interval: Update interval

        Returns:
            True if update should be sent
        """
        return current_count - last_update_count >= interval or current_count == 1

    async def monitor_enrichment_pipeline(
        self, job_id: str, pipeline: Any, total_documents: int
    ) -> None:
        """Monitor enrichment pipeline progress.

        Args:
            job_id: Job ID
            pipeline: Enrichment pipeline instance
            total_documents: Total documents to enrich
        """
        last_update_time = time.time()
        last_completed_count = 0
        stall_counter = 0
        max_stall_checks = 12  # 2 minutes of no progress

        while True:
            # Get current pipeline stats
            stats = pipeline.get_stats()
            enrichment_queue = stats["enrichment_queue_size"]
            storage_queue = stats["storage_queue_size"]
            active_tasks = stats["active_tasks"]
            completed_count = stats["completed_count"]
            completed_documents = stats.get("completed_documents", 0)
            error_count = stats["error_count"]

            logger.info(
                f"Enrichment progress - "
                f"Queue: {enrichment_queue}, "
                f"Storage: {storage_queue}, "
                f"Active: {active_tasks}, "
                f"Completed: {completed_count}/{total_documents}, "
                f"Errors: {error_count}"
            )

            # Check if enrichment is complete
            if enrichment_queue == 0 and storage_queue == 0 and active_tasks == 0:
                logger.info(f"Enrichment completed! Processed {completed_count} items")
                break

            # Check for stalled progress
            if completed_count == last_completed_count:
                stall_counter += 1
                if stall_counter >= max_stall_checks:
                    logger.warning("Enrichment appears stalled, proceeding...")
                    break
            else:
                stall_counter = 0
                last_completed_count = completed_count

            # Send update every 10 seconds
            current_time = time.time()
            if current_time - last_update_time >= 10:
                await self.update_progress(
                    job_id, phase="enriching", documents_enriched=completed_documents
                )

                # Calculate enrichment progress
                enrichment_progress = round(
                    (completed_count / total_documents * 100) if total_documents > 0 else 0, 1
                )

                await self.send_update(
                    job_id,
                    "running",
                    {
                        "crawl_phase": "enriching",
                        "enrichment_queue": enrichment_queue,
                        "documents_enriched": completed_documents,
                        "total_documents": total_documents,
                        "enrichment_progress": enrichment_progress,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                last_update_time = current_time

            # Wait before next check
            await asyncio.sleep(10)
