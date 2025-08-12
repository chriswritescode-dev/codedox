"""Progress tracking and notification management."""

import asyncio
import logging
from datetime import datetime
from typing import Any

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
            async def dummy_notify(job_id: str, status: str, data: dict[str, Any]) -> None:
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
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}
        self._tracking_info: dict[str, dict[str, Any]] = {}

    async def start_tracking(self, job_id: str) -> None:
        """Start tracking progress for a job.

        Args:
            job_id: Job ID to track
        """
        # Cancel any existing task
        await self.stop_tracking(job_id)

        # Initialize tracking info for this job
        self._tracking_info[job_id] = {'phase': 'crawling'}

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

        # Clean up tracking info
        if job_id in self._tracking_info:
            del self._tracking_info[job_id]

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
        phase: str | None = None,
        processed_pages: int | None = None,
        total_pages: int | None = None,
        snippets_extracted: int | None = None,
        documents_crawled: int | None = None,
        current_url: str | None = None,
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
        )

        if phase:
            self.job_manager.update_job_status(job_id, phase=phase)
            # Store phase in tracking info for heartbeat
            if job_id in self._tracking_info:
                self._tracking_info[job_id]['phase'] = phase

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
                    "timestamp": datetime.utcnow().isoformat(),
                }

                if current_url:
                    data["current_url"] = current_url

                # Calculate progress percentages
                total_pages = job_status.get("total_pages", 0)
                processed_pages = job_status.get("processed_pages", 0)
                if total_pages > 0:
                    data["crawl_progress"] = min(
                        100, round(processed_pages / total_pages * 100)
                    )


                await self.send_update(job_id, "running", data)

    async def send_update(self, job_id: str, status: str, data: dict[str, Any]) -> None:
        """Send WebSocket update notification.

        Args:
            job_id: Job ID
            status: Job status
            data: Update data
        """
        try:
            notify_func = _get_notify_function()
            await notify_func(job_id, status, data)
            logger.debug(f"[WEBSOCKET] Successfully sent update for job {job_id}: {status}")
        except Exception as e:
            logger.error(f"[WEBSOCKET] Failed to send update for job {job_id}: {e}")
            # Log specific error details for 403 errors
            if "403" in str(e):
                logger.error(f"[WEBSOCKET] 403 Forbidden error - possible authentication issue for job {job_id}")

    async def send_completion(
        self, job_id: str, success: bool = True, error: str | None = None
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

