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
    max_pages: Optional[int] = None
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
        self._task_cleanup_lock = asyncio.Lock()  # Lock for task cleanup

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
        
        # Cleanup task will be started when first crawl starts
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up completed tasks from active tasks dict."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                async with self._task_cleanup_lock:
                    # Find and remove completed tasks
                    completed_tasks = [
                        job_id for job_id, task in self._active_crawl_tasks.items()
                        if task.done()
                    ]
                    for job_id in completed_tasks:
                        self._active_crawl_tasks.pop(job_id, None)
                        logger.debug(f"Cleaned up completed task for job {job_id}")
                    
                    if completed_tasks:
                        logger.info(f"Cleaned up {len(completed_tasks)} completed crawl tasks")
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Continue after error

    async def start_crawl(self, config: CrawlConfig) -> str:
        """Start a new crawl job.

        Args:
            config: Crawl configuration

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
        )

        # Start cleanup task if not already running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.debug("Started periodic cleanup task")
        
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
        return base_snippet_count, 0  # Return base count and 0 for new snippets

    async def _check_job_cancelled(self, job_id: str) -> None:
        """Check if job is cancelled and raise CancelledError if so."""
        job_status = self.job_manager.get_job_status(job_id)
        if job_status and job_status.get("status") == "cancelled":
            logger.info(f"Job {job_id} has been cancelled, stopping crawl")
            raise asyncio.CancelledError("Job cancelled by user")

    async def _update_crawl_progress(
        self, job_id: str, processed_count: int, visited_urls: Set[str], 
        total_snippets: int, docs_count: int, last_ws_count: int, base_snippet_count: int
    ) -> int:
        """Update crawl progress and return new last_ws_count if notification sent."""
        send_notification = self.progress_tracker.should_send_update(
            processed_count, last_ws_count
        )
        
        await self.progress_tracker.update_progress(
            job_id,
            processed_pages=processed_count,
            total_pages=len(visited_urls),
            snippets_extracted=base_snippet_count + total_snippets,
            documents_crawled=docs_count,
            send_notification=send_notification,
        )
        
        return processed_count if send_notification else last_ws_count

    async def _execute_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute the crawl job with global timeout."""
        try:
            # Check if job is already cancelled
            job_status = self.job_manager.get_job_status(job_id)
            if job_status and job_status.get("status") == "cancelled":
                logger.info(f"Job {job_id} is cancelled, not starting crawl")
                return
            # Start tracking
            await self.progress_tracker.start_tracking(job_id)

            # Wrap crawl execution with global timeout
            try:
                await asyncio.wait_for(
                    self._execute_crawl_internal(job_id, config),
                    timeout=self.settings.crawling.global_crawl_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Crawl job {job_id} exceeded global timeout of {self.settings.crawling.global_crawl_timeout}s")
                raise TimeoutError(f"Crawl exceeded maximum allowed time of {self.settings.crawling.global_crawl_timeout}s")

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
        except TimeoutError as e:
            logger.error(f"Crawl job {job_id} timed out: {e}")
            self.job_manager.complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            self.job_manager.complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        finally:
            # Clean up
            await self.progress_tracker.stop_tracking(job_id)
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)

    async def _execute_crawl_internal(self, job_id: str, config: CrawlConfig) -> None:
        """Internal crawl execution without timeout wrapper."""
        # Execute crawl based on depth
        if config.max_depth > 0:
            await self._execute_deep_crawl(job_id, config)
        else:
            # Single page crawl handles both single and multiple URLs
            await self._execute_single_crawl(job_id, config)

    async def _execute_deep_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute deep crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        last_ws_count = 0

        # Initialize tracking
        base_snippet_count, total_snippets = self._initialize_crawl_tracking(job_id)
        logger.info(f"[SNIPPET_COUNT] Starting deep crawl for job {job_id} with base count: {base_snippet_count}")
        
        # Build fresh config for this crawl - don't merge with old config
        job_config = {
            "domain_restrictions": config.domain_restrictions,
            "include_patterns": config.include_patterns,
            "exclude_patterns": config.exclude_patterns,
            "max_pages": config.max_pages,
            "metadata": config.metadata,
            "max_concurrent_crawls": config.max_concurrent_crawls,
        }
        
        # Preserve base_snippet_count for tracking (needed by _initialize_crawl_tracking)
        job_data = self.job_manager.get_job_status(job_id)
        if job_data and job_data.get("config", {}).get("base_snippet_count") is not None:
            job_config["base_snippet_count"] = job_data["config"]["base_snippet_count"]

        for start_url in config.start_urls:
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
                    job_id, processed_count, visited_urls, total_snippets, docs, last_ws_count, base_snippet_count
                )

    async def _execute_single_crawl(self, job_id: str, config: CrawlConfig) -> None:
        """Execute single page crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        last_ws_count = 0
        
        # Initialize tracking
        base_snippet_count, total_snippets = self._initialize_crawl_tracking(job_id)
        logger.info(f"[SNIPPET_COUNT] Starting single crawl for job {job_id} with base count: {base_snippet_count}")

        # Build fresh config for this crawl - don't merge with old config
        job_config = {
            "domain_restrictions": config.domain_restrictions,
            "include_patterns": config.include_patterns,
            "exclude_patterns": config.exclude_patterns,
            "max_pages": config.max_pages,
            "metadata": config.metadata,
            "max_concurrent_crawls": config.max_concurrent_crawls,
        }
        
        # Get job data for base_snippet_count and any special flags
        job_data = self.job_manager.get_job_status(job_id)
        logger.info(f"DEBUG: job_data config = {job_data.get('config') if job_data else 'No job data'}")
        
        # Preserve base_snippet_count and ignore_hash flag if present
        if job_data and job_data.get("config"):
            old_config = job_data["config"]
            if old_config.get("base_snippet_count") is not None:
                job_config["base_snippet_count"] = old_config["base_snippet_count"]
            # Check for ignore_hash in metadata (for recrawl operations)
            if config.metadata and config.metadata.get("ignore_hash"):
                job_config["metadata"]["ignore_hash"] = True

        # If we have multiple URLs, use the efficient arun_many approach
        if len(config.start_urls) > 1:
            logger.info(f"Using multi-URL crawling for {len(config.start_urls)} URLs")
            
            # Check if job is cancelled before starting
            await self._check_job_cancelled(job_id)
            
            # Use the new crawl_multiple_urls method
            results = await self.page_crawler.crawl_multiple_urls(
                config.start_urls, job_id, job_config, self.progress_tracker
            )
            
            if results:
                # Process all results
                for result in results:
                    doc_id, snippet_count = await self.result_processor.process_result_pipeline(
                        result, job_id, 0
                    )
                    processed_count += 1
                    total_snippets += snippet_count
                    visited_urls.add(result.url)
                
                # Final progress update
                await self._update_crawl_progress(
                    job_id, processed_count, visited_urls, total_snippets, processed_count, 0, base_snippet_count
                )
        else:
            # Single URL - use the original approach
            for url in config.start_urls:
                # Check if job is cancelled
                await self._check_job_cancelled(job_id)

                visited_urls.add(url)

                # Crawl single page
                logger.debug(f"DEBUG: About to call crawl_page for single page {url}")
                logger.debug(f"DEBUG: job_config before crawl_page = {job_config}")
                results = await self.page_crawler.crawl_page(
                    url, job_id, 0, 0, job_config, self.progress_tracker
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
                        
                    # Update progress
                    last_ws_count = await self._update_crawl_progress(
                        job_id, processed_count, visited_urls, total_snippets, processed_count, last_ws_count, base_snippet_count
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

        # Check job state - can only resume running jobs (stalled)
        if job_status["status"] not in ["running"]:
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

    async def retry_failed_pages(self, job_id: str, specific_urls: Optional[List[str]] = None) -> Optional[str]:
        """Create a new job to retry by re-running the original configuration.
        
        Args:
            job_id: The ID of the original job
            specific_urls: Optional list of specific URLs to recrawl (if None, recrawls all)
        """
        from ..database import FailedPage, CrawlJob
        from ..database import get_db_manager

        db_manager = get_db_manager()

        with db_manager.session_scope() as session:
            # Get original job
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return None

            # Convert to dict while still in session
            job_dict = job.to_dict()

            # Count failed pages for logging
            failed_count = session.query(FailedPage).filter_by(crawl_job_id=job_id).count()
            logger.info(f"Original job had {failed_count} failed pages, creating retry job with full configuration")

        # Reconstruct the original configuration completely
        original_config = job_dict.get("config", {})
        
        # Preserve all metadata from original job and add retry markers
        original_metadata = original_config.get("metadata", {})
        retry_metadata = {
            **original_metadata,  # Keep all original metadata
            "retry_of_job": job_id,
            "original_job_name": job_dict["name"],
            "failed_pages_count": failed_count
        }
        
        # Determine which URLs to use and appropriate depth
        if specific_urls:
            # Use only the specific URLs provided
            start_urls = specific_urls
            # For specific failed pages, only crawl those exact pages (depth=0)
            crawl_depth = 0
            logger.info(f"Using {len(specific_urls)} specific URLs for retry with depth=0 (single page only)")
        else:
            # Use all original start URLs
            start_urls = job_dict["start_urls"]
            # For full recrawl, use original depth
            crawl_depth = job_dict["max_depth"]
            logger.info(f"Using all {len(start_urls)} original start URLs for retry with depth={crawl_depth}")
        
        # Create retry config with appropriate settings
        original_name = job_dict['name']
        retry_name = f"{original_name} - Retry"
        logger.info(f"[RETRY DEBUG] Creating retry job - Original name: '{original_name}', Retry name: '{retry_name}'")
        
        retry_config = CrawlConfig(
            name=retry_name,
            start_urls=start_urls,  # Use filtered or original URLs
            max_depth=crawl_depth,  # Use 0 for specific URLs, original depth for full recrawl
            domain_restrictions=job_dict.get("domain_restrictions", []),
            include_patterns=original_config.get("include_patterns", []),
            exclude_patterns=original_config.get("exclude_patterns", []),
            max_pages=original_config.get("max_pages", None) if not specific_urls else len(specific_urls),  # Limit max_pages for specific URLs
            max_concurrent_crawls=original_config.get("max_concurrent_crawls", self.settings.crawling.max_concurrent_crawls),
            metadata=retry_metadata,
        )

        # Start new job with appropriate configuration
        new_job_id = await self.start_crawl(retry_config)
        logger.info(f"Created retry job {new_job_id} with configuration (depth={crawl_depth}, urls={len(start_urls)})")

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
            max_pages=config_data.get("max_pages", None),
            max_concurrent_crawls=config_data.get("max_concurrent_crawls", self.settings.crawling.max_concurrent_crawls),
            metadata=config_data.get("metadata", {}),
        )
    
    async def shutdown(self) -> None:
        """Shutdown the crawl manager and cleanup resources."""
        logger.info("Shutting down CrawlManager...")
        
        # Cancel cleanup task
        if hasattr(self, '_cleanup_task') and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active crawl tasks
        async with self._task_cleanup_lock:
            for job_id, task in self._active_crawl_tasks.items():
                if not task.done():
                    logger.info(f"Cancelling active crawl task for job {job_id}")
                    task.cancel()
            
            # Wait for all tasks to complete
            tasks = list(self._active_crawl_tasks.values())
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self._active_crawl_tasks.clear()
        
        # Cleanup result processor
        if hasattr(self, 'result_processor'):
            self.result_processor.cleanup()
        
        logger.info("CrawlManager shutdown complete")
