"""Simplified crawl manager that orchestrates crawling operations."""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field

from ..config import get_settings
from .config import create_browser_config
from .job_manager import JobManager
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor
from .page_crawler import PageCrawler

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CrawlConfig:
    """Configuration for a crawl job."""

    name: str
    start_urls: List[str]
    max_depth: int = 0
    domain_restrictions: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    max_pages: int = 100
    max_concurrent_crawls: int = 5
    respect_robots_txt: bool = False
    content_types: List[str] = field(default_factory=lambda: ["text/markdown", "text/plain"])
    min_content_length: int = 100
    extract_code_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CrawlManager:
    """Simplified crawl manager that orchestrates crawling operations."""

    def __init__(self) -> None:
        """Initialize the crawl manager."""
        self.settings = settings
        self._active_crawl_tasks: Dict[str, asyncio.Task] = {}  # Track active crawl tasks

        # Initialize components
        self.job_manager = JobManager()
        self.progress_tracker = ProgressTracker(self.job_manager)

        # Get user agent from settings
        user_agent = self.settings.crawling.user_agent
        
        # Initialize browser config
        self.browser_config = create_browser_config(
            headless=True,
            viewport_width=1200,
            viewport_height=800,
            user_agent=user_agent,
        )

        # Initialize crawler and processor
        self.page_crawler = PageCrawler(self.browser_config)
        self.result_processor = ResultProcessor()

    async def start_crawl(self, config: CrawlConfig, user_id: Optional[str] = None) -> str:
        """Start a new crawl job.

        Args:
            config: Crawl configuration
            user_id: User identifier

        Returns:
            Job ID
        """
        # Create or reuse job
        job_config = {
            "include_patterns": config.include_patterns,
            "exclude_patterns": config.exclude_patterns,
            "max_pages": config.max_pages,
            "metadata": config.metadata,
            "max_concurrent_crawls": config.max_concurrent_crawls,
        }

        job_id = self.job_manager.get_or_create_job(
            config.name,
            config.start_urls,
            config.max_depth,
            config.domain_restrictions,
            job_config,
            user_id,
        )

        # Cancel any existing active task for this job
        existing_task = self._active_crawl_tasks.get(job_id)
        logger.info(f"Checking for existing task for job {job_id}: {existing_task is not None}")
        if existing_task and not existing_task.done():
            logger.info(f"Cancelling existing crawl task for job {job_id}")
            existing_task.cancel()
            # Wait briefly for cancellation to complete
            try:
                await asyncio.wait_for(existing_task, timeout=self.settings.crawling.task_cancellation_timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)
        elif existing_task:
            logger.info(f"Existing task for job {job_id} is already done, removing from active tasks")
            self._active_crawl_tasks.pop(job_id, None)

        # Start async crawl
        task = asyncio.create_task(self._execute_crawl(job_id, config))
        self._active_crawl_tasks[job_id] = task

        return job_id

    def _initialize_crawl_tracking(self, job_id: str) -> tuple[int, int]:
        """Initialize tracking variables for crawl execution."""
        job_data = self.job_manager.get_job_status(job_id)
        job_config = job_data.get("config", {}) if job_data else {}
        base_snippet_count = job_config.get("base_snippet_count", 0)
        return base_snippet_count, base_snippet_count

    async def _check_job_cancelled(self, job_id: str) -> None:
        """Check if job is cancelled and raise CancelledError if so."""
        job_status = self.job_manager.get_job_status(job_id)
        if job_status and job_status.get("status") == "cancelled":
            logger.info(f"Job {job_id} has been cancelled, stopping crawl")
            raise asyncio.CancelledError("Job cancelled by user")

    async def _update_crawl_progress(
        self, job_id: str, processed_count: int, visited_urls: Set[str], 
        total_snippets: int, docs_count: int, last_ws_count: int
    ) -> int:
        """Update crawl progress and return new last_ws_count if notification sent."""
        send_notification = self.progress_tracker.should_send_update(
            processed_count, last_ws_count
        )
        
        await self.progress_tracker.update_progress(
            job_id,
            processed_pages=processed_count,
            total_pages=len(visited_urls),
            snippets_extracted=total_snippets,
            documents_crawled=docs_count,
            send_notification=send_notification,
        )
        
        return processed_count if send_notification else last_ws_count

    async def _execute_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute the crawl job."""
        try:
            # Check if job is already cancelled
            job_status = self.job_manager.get_job_status(job_id)
            if job_status and job_status.get("status") == "cancelled":
                logger.info(f"Job {job_id} is cancelled, not starting crawl")
                return
            # Start tracking
            await self.progress_tracker.start_tracking(job_id)

            # Execute crawl based on depth - single page or deep crawl
            if config.max_depth > 0:
                await self._execute_deep_crawl(job_id, config)
            else:
                await self._execute_single_crawl(job_id, config)

            # Get final job status to preserve snippet count
            final_status = self.job_manager.get_job_status(job_id)
            final_snippet_count = final_status.get("snippets_extracted", 0) if final_status else 0
            base_count = final_status.get("config", {}).get("base_snippet_count", 0) if final_status else 0
            
            logger.info(f"[SNIPPET_COUNT] Job {job_id} completion - Base: {base_count}, Final: {final_snippet_count}, New: {final_snippet_count - base_count}")

            # Complete job immediately after crawl
            self.job_manager.complete_job(job_id, success=True)

            await self.progress_tracker.send_completion(job_id, success=True)

        except asyncio.CancelledError:
            logger.info(f"Crawl job {job_id} was cancelled")
            # Job status is already set to cancelled by cancel_job
            await self.progress_tracker.send_completion(
                job_id, success=False, error="Cancelled by user"
            )
            raise  # Re-raise to properly handle task cancellation
        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            self.job_manager.complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        finally:
            # Clean up
            await self.progress_tracker.stop_tracking(job_id)
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)

    async def _execute_deep_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute deep crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        last_ws_count = 0

        # Initialize tracking
        base_snippet_count, total_snippets = self._initialize_crawl_tracking(job_id)
        logger.info(f"[SNIPPET_COUNT] Starting deep crawl for job {job_id} with base count: {base_snippet_count}")
        
        # Get job config for domain restrictions
        job_data = self.job_manager.get_job_status(job_id)
        job_config = job_data.get("config", {}) if job_data else {}

        # Add domain restrictions to job config
        job_config["domain_restrictions"] = config.domain_restrictions
        job_config["include_patterns"] = config.include_patterns
        job_config["exclude_patterns"] = config.exclude_patterns
        job_config["max_pages"] = config.max_pages

        for start_url in config.start_urls:
            if processed_count >= config.max_pages:
                break

            # Check if job is cancelled
            await self._check_job_cancelled(job_id)

            # Crawl from this start URL
            logger.info(f"DEBUG: About to call crawl_page for {start_url}")
            results = await self.page_crawler.crawl_page(
                start_url, job_id, 0, config.max_depth, job_config, self.progress_tracker
            )

            if results:
                logger.info(f"Deep crawl completed! Received {len(results)} pages")

                # Process results
                docs, snippets = await self.result_processor.process_batch(
                    results, job_id, use_pipeline=False
                )

                processed_count += len(results)
                total_snippets += snippets
                visited_urls.update(r.url for r in results)
                
                logger.info(f"[SNIPPET_COUNT] Deep crawl batch - New snippets: {snippets}, Total: {total_snippets} (base: {base_snippet_count})")

                # Update progress
                last_ws_count = await self._update_crawl_progress(
                    job_id, processed_count, visited_urls, total_snippets, docs, last_ws_count
                )

    async def _execute_single_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute single page crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        last_ws_count = 0
        
        # Initialize tracking
        base_snippet_count, total_snippets = self._initialize_crawl_tracking(job_id)
        logger.info(f"[SNIPPET_COUNT] Starting single crawl for job {job_id} with base count: {base_snippet_count}")

        # Process each URL
        for url in config.start_urls:
            if processed_count >= config.max_pages:
                break

            if url in visited_urls:
                continue

            # Check if job is cancelled
            await self._check_job_cancelled(job_id)

            visited_urls.add(url)

            # Crawl single page
            logger.info(f"DEBUG: About to call crawl_page for single page {url}")
            results = await self.page_crawler.crawl_page(
                url, job_id, 0, 0, None, self.progress_tracker
            )

            if results:
                logger.debug(f"Processing {len(results)} results")

                # Process results
                for result in results:
                    logger.debug(
                        f"Processing result for {result.url} with {len(result.code_blocks) if result.code_blocks else 0} code blocks"
                    )

                    doc_id, snippet_count = await self.result_processor.process_result_pipeline(
                        result, job_id, 0
                    )

                    logger.debug(f"Result: doc_id={doc_id}, snippet_count={snippet_count}")

                    processed_count += 1
                    total_snippets += snippet_count
                    
                    logger.info(f"[SNIPPET_COUNT] Single crawl page - New snippets: {snippet_count}, Total: {total_snippets} (base: {base_snippet_count})")

                # Update progress
                last_ws_count = await self._update_crawl_progress(
                    job_id, processed_count, visited_urls, total_snippets, processed_count, last_ws_count
                )

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a crawl job."""
        # First update the database status
        success = self.job_manager.cancel_job(job_id)

        if success and job_id in self._active_crawl_tasks:
            # Cancel the active crawl task
            task = self._active_crawl_tasks[job_id]
            if not task.done():
                logger.info(f"Cancelling active crawl task for job {job_id}")
                task.cancel()
                # Wait a moment for cancellation to propagate
                try:
                    await asyncio.wait_for(task, timeout=self.settings.crawling.task_cancellation_timeout)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)

        return success

    async def resume_job(self, job_id: str) -> bool:
        """Resume a failed or stalled job by retrying failed pages."""
        # Get job status to avoid DetachedInstanceError
        job_status = self.job_manager.get_job_status(job_id)
        if not job_status:
            return False

        # Check job state
        if job_status["status"] not in ["failed", "running", "cancelled"]:
            logger.error(f"Job {job_id} is in {job_status['status']} state, cannot resume")
            return False

        # Check if stalled
        if job_status["status"] == "running" and job_status.get("last_heartbeat"):
            from datetime import datetime, timezone

            last_heartbeat = datetime.fromisoformat(
                job_status["last_heartbeat"].replace("Z", "+00:00")
            )
            time_since_heartbeat = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()
            if time_since_heartbeat < self.settings.crawling.heartbeat_stall_threshold:
                logger.info(f"Job {job_id} is still active")
                return False

        # Check if there are failed pages to retry
        from ..database import FailedPage
        from ..database import get_db_manager

        db_manager = get_db_manager()
        with db_manager.session_scope() as session:
            failed_count = session.query(FailedPage).filter_by(crawl_job_id=job_id).count()

        if failed_count > 0:
            # Retry failed pages instead of restarting the entire crawl
            logger.info(f"Found {failed_count} failed pages for job {job_id}, retrying them")
            new_job_id = await self.retry_failed_pages(job_id)
            if new_job_id:
                # Update the original job to running state with the new job as continuation
                self.job_manager.update_job_status(
                    job_id,
                    status="running",
                    error_message=f"Resumed with new job {new_job_id} for {failed_count} failed pages",
                )
                return True
            else:
                logger.error(f"Failed to create retry job for {job_id}")
                return False
        else:
            # No failed pages, restart the entire crawl
            logger.info(f"No failed pages found for job {job_id}, restarting entire crawl")

            # Reset job status
            self.job_manager.update_job_status(
                job_id,
                status="running",
                error_message=None,
                processed_pages=job_status.get("processed_pages", 0),
                retry_count=job_status.get("retry_count", 0) + 1,
            )

            # Restart crawl
            config = self._reconstruct_config(job_status)
            task = asyncio.create_task(self._execute_crawl(job_id, config))
            self._active_crawl_tasks[job_id] = task
            return True

    async def retry_failed_pages(self, job_id: str, user_id: Optional[str] = None) -> Optional[str]:
        """Create a new job to retry failed pages."""
        from ..database import FailedPage, CrawlJob
        from ..database import get_db_manager

        db_manager = get_db_manager()

        with db_manager.session_scope() as session:
            # Get failed pages
            failed_pages = session.query(FailedPage).filter_by(crawl_job_id=job_id).all()

            if not failed_pages:
                logger.info(f"No failed pages for job {job_id}")
                return None

            # Get original job in the same session
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return None

            # Convert to dict while still in session
            job_dict = job.to_dict()

            # Extract URLs before session closes
            failed_urls = [str(fp.url) for fp in failed_pages]
            failed_count = len(failed_pages)

        # Create retry config outside session, preserving max_concurrent_crawls
        original_config = job_dict.get("config", {})
        max_concurrent = original_config.get("max_concurrent_crawls", self.settings.crawling.max_concurrent_crawls)
        
        retry_config = CrawlConfig(
            name=f"{job_dict['name']} - Retry Failed Pages",
            start_urls=failed_urls,
            max_depth=0,
            domain_restrictions=job_dict.get("domain_restrictions", []),
            max_pages=failed_count,
            max_concurrent_crawls=max_concurrent,
            metadata={"retry_of_job": job_id, "original_job_name": job_dict["name"]},
        )

        # Start new job
        new_job_id = await self.start_crawl(retry_config, user_id)
        logger.info(f"Created retry job {new_job_id} for {failed_count} failed pages with max_concurrent_crawls={max_concurrent}")

        return new_job_id

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status."""
        return self.job_manager.get_job_status(job_id)

    def _reconstruct_config(self, job_dict: Dict[str, Any]) -> CrawlConfig:
        """Reconstruct config from job data."""
        config_data = job_dict.get("config", {})
        return CrawlConfig(
            name=job_dict["name"],
            start_urls=job_dict["start_urls"],
            max_depth=job_dict["max_depth"],
            domain_restrictions=job_dict.get("domain_restrictions", []),
            include_patterns=config_data.get("include_patterns", []),
            exclude_patterns=config_data.get("exclude_patterns", []),
            max_pages=config_data.get("max_pages", 100),
            max_concurrent_crawls=config_data.get("max_concurrent_crawls", self.settings.crawling.max_concurrent_crawls),
            metadata=config_data.get("metadata", {}),
        )
