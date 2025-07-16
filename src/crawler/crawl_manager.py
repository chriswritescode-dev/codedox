"""Simplified crawl manager that orchestrates crawling operations."""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field

from ..config import get_settings
from ..parser import CodeExtractor
from ..language import LanguageDetector
from .config import create_browser_config
from .job_manager import JobManager
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor
from .page_crawler import PageCrawler
from .enrichment_manager import EnrichmentManager
from .utils import should_crawl_url

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
    max_concurrent_crawls: int = 20
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
        self.enrichment_manager = EnrichmentManager()

        # Initialize extractors
        self.code_extractor = CodeExtractor(
            context_chars=2000,
            min_code_lines=settings.code_extraction.min_code_lines,
            use_tree_sitter=getattr(settings.code_extraction, "use_tree_sitter_validation", True),
            min_quality_score=getattr(settings.code_extraction, "min_ast_quality_score", 0.7),
        )
        self.language_detector = LanguageDetector()

        # Initialize browser config
        self.browser_config = create_browser_config(
            headless=True,
            viewport_width=1200,
            viewport_height=800,
            
        )

        # Initialize crawler and processor
        self.page_crawler = PageCrawler(self.browser_config, self.code_extractor)
        self.result_processor = ResultProcessor(
            self.code_extractor,
            self.language_detector,
            self.enrichment_manager.metadata_enricher,
            self.enrichment_manager.enrichment_pipeline,
        )

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

        # Start async crawl
        task = asyncio.create_task(self._execute_crawl(job_id, config))
        self._active_crawl_tasks[job_id] = task

        return job_id

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

            # Initialize enrichment if needed
            use_pipeline = await self.enrichment_manager.ensure_pipeline()
            if use_pipeline:
                logger.info("Enrichment pipeline ready for crawl job")
                # Update processor to use pipeline
                logger.debug(f"Updating result processor pipeline reference")
                logger.debug(f"Pipeline before update: {self.result_processor.enrichment_pipeline}")
                self.result_processor.enrichment_pipeline = (
                    self.enrichment_manager.enrichment_pipeline
                )
                logger.debug(f"Pipeline after update: {self.result_processor.enrichment_pipeline}")
                logger.debug(f"Pipeline is running: {self.result_processor.enrichment_pipeline.is_running if self.result_processor.enrichment_pipeline else 'N/A'}")

            # Execute crawl based on depth
            if config.max_depth > 0:
                await self._execute_deep_crawl(job_id, config, use_pipeline)
            else:
                await self._execute_single_crawl(job_id, config, use_pipeline)

            # Mark crawl phase complete
            self.job_manager.mark_crawl_complete(job_id)

            # Wait for enrichment if using pipeline
            if use_pipeline and self.enrichment_manager.is_pipeline_running():
                logger.info("Waiting for enrichment pipeline to complete...")

                # Get total documents from job
                job_status = self.job_manager.get_job_status(job_id)
                total_docs = job_status.get("documents_crawled", 0) if job_status else 0

                await self.progress_tracker.monitor_enrichment_pipeline(
                    job_id, self.enrichment_manager.enrichment_pipeline, total_docs
                )

                # Stop pipeline
                await self.enrichment_manager.stop_pipeline()

            # Complete job
            self.job_manager.complete_job(job_id, success=True)
            await self.progress_tracker.send_completion(job_id, success=True)

        except asyncio.CancelledError:
            logger.info(f"Crawl job {job_id} was cancelled")
            # Job status is already set to cancelled by cancel_job
            await self.progress_tracker.send_completion(job_id, success=False, error="Cancelled by user")
            raise  # Re-raise to properly handle task cancellation
        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            self.job_manager.complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        finally:
            # Clean up
            await self.progress_tracker.stop_tracking(job_id)
            if self.enrichment_manager.is_pipeline_running():
                await self.enrichment_manager.stop_pipeline()
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)

    async def _execute_deep_crawl(
        self, job_id: str, config: CrawlConfig, use_pipeline: bool
    ) -> None:
        """Execute deep crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        total_snippets = 0
        last_ws_count = 0

        # Get job config
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
            job_status = self.job_manager.get_job_status(job_id)
            if job_status and job_status.get("status") == "cancelled":
                logger.info(f"Job {job_id} has been cancelled, stopping crawl")
                raise asyncio.CancelledError("Job cancelled by user")

            # Crawl from this start URL
            results = await self.page_crawler.crawl_page(
                start_url, job_id, 0, config.max_depth, job_config
            )

            if results:
                logger.info(f"Deep crawl completed! Received {len(results)} pages")

                # Process results
                docs, snippets, links = await self.result_processor.process_batch(
                    results, job_id, use_pipeline
                )

                processed_count += len(results)
                total_snippets += snippets
                visited_urls.update(r.url for r in results)

                # Store links
                if links:
                    asyncio.create_task(self.result_processor.store_links_batch(job_id, links))

                # Update progress
                await self.progress_tracker.update_progress(
                    job_id,
                    processed_pages=processed_count,
                    total_pages=len(visited_urls),
                    snippets_extracted=total_snippets,
                    documents_crawled=docs,
                    send_notification=self.progress_tracker.should_send_update(
                        processed_count, last_ws_count
                    ),
                )

                if self.progress_tracker.should_send_update(processed_count, last_ws_count):
                    last_ws_count = processed_count

    async def _execute_single_crawl(
        self, job_id: str, config: CrawlConfig, use_pipeline: bool
    ) -> None:
        """Execute single page crawl."""
        visited_urls: Set[str] = set()
        processed_count = 0
        total_snippets = 0
        last_ws_count = 0

        # Process each URL
        for url in config.start_urls:
            if processed_count >= config.max_pages:
                break

            if url in visited_urls:
                continue

            # Check if job is cancelled
            job_status = self.job_manager.get_job_status(job_id)
            if job_status and job_status.get("status") == "cancelled":
                logger.info(f"Job {job_id} has been cancelled, stopping crawl")
                raise asyncio.CancelledError("Job cancelled by user")

            visited_urls.add(url)

            # Crawl single page
            results = await self.page_crawler.crawl_page(url, job_id, 0, 0)

            if results:
                logger.debug(f"Processing {len(results)} results, use_pipeline={use_pipeline}")
                submission_tasks = []
                
                # Process results
                for result in results:
                    logger.debug(f"Processing result for {result.url} with {len(result.code_blocks) if result.code_blocks else 0} code blocks")
                    
                    if use_pipeline:
                        doc_id, snippet_count, task = await self.result_processor.process_result_pipeline(result, job_id, 0)
                        if task:
                            submission_tasks.append(task)
                    else:
                        doc_id, snippet_count = await self.result_processor.process_result(result, job_id, 0)
                    
                    logger.debug(f"Result: doc_id={doc_id}, snippet_count={snippet_count}")

                    processed_count += 1
                    total_snippets += snippet_count
                
                # Wait for all submission tasks to complete before proceeding
                if submission_tasks:
                    logger.info(f"Waiting for {len(submission_tasks)} pipeline submissions to complete...")
                    await asyncio.gather(*submission_tasks, return_exceptions=True)

                # Update progress
                await self.progress_tracker.update_progress(
                    job_id,
                    processed_pages=processed_count,
                    total_pages=len(visited_urls),
                    snippets_extracted=total_snippets,
                    documents_crawled=processed_count,
                    send_notification=self.progress_tracker.should_send_update(
                        processed_count, last_ws_count
                    ),
                )

                if self.progress_tracker.should_send_update(processed_count, last_ws_count):
                    last_ws_count = processed_count

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
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            # Remove from active tasks
            self._active_crawl_tasks.pop(job_id, None)
            
            # Also stop enrichment pipeline if running
            if self.enrichment_manager.is_pipeline_running():
                await self.enrichment_manager.stop_pipeline()
        
        return success

    async def resume_job(self, job_id: str) -> bool:
        """Resume a failed or stalled job."""
        # Get job status to avoid DetachedInstanceError
        job_status = self.job_manager.get_job_status(job_id)
        if not job_status:
            return False

        # Check job state
        if job_status["status"] not in ["failed", "running"]:
            logger.error(f"Job {job_id} is in {job_status['status']} state, cannot resume")
            return False

        # Check if stalled
        if job_status["status"] == "running" and job_status.get("last_heartbeat"):
            from datetime import datetime

            last_heartbeat = datetime.fromisoformat(job_status["last_heartbeat"].replace('Z', '+00:00'))
            time_since_heartbeat = (datetime.utcnow() - last_heartbeat).total_seconds()
            if time_since_heartbeat < 300:  # 5 minutes
                logger.info(f"Job {job_id} is still active")
                return False

        # Determine resume point
        if not job_status.get("crawl_completed_at"):
            # Resume crawl
            logger.info(f"Resuming job {job_id} from crawl phase")
            config = self._reconstruct_config(job_status)
            task = asyncio.create_task(self._execute_crawl(job_id, config))
            self._active_crawl_tasks[job_id] = task
        else:
            # Resume enrichment
            logger.info(f"Resuming job {job_id} from enrichment phase")
            task = asyncio.create_task(self._resume_enrichment(job_id))
            self._active_crawl_tasks[job_id] = task

        return True

    async def restart_enrichment(self, job_id: str) -> bool:
        """Restart enrichment for a completed job."""
        success = await self.enrichment_manager.resume_job_enrichment(job_id)
        if success:
            self.job_manager.complete_job(job_id, success=True)
        return success

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

        # Create retry config outside session
        retry_config = CrawlConfig(
            name=f"{job_dict['name']} - Retry Failed Pages",
            start_urls=failed_urls,
            max_depth=0,
            domain_restrictions=job_dict.get("domain_restrictions", []),
            max_pages=failed_count,
            metadata={"retry_of_job": job_id, "original_job_name": job_dict["name"]},
        )

        # Start new job
        new_job_id = await self.start_crawl(retry_config, user_id)
        logger.info(f"Created retry job {new_job_id} for {failed_count} failed pages")

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
            metadata=config_data.get("metadata", {}),
        )

    async def _resume_enrichment(self, job_id: str) -> None:
        """Resume enrichment for a job."""
        try:
            # Start tracking
            await self.progress_tracker.start_tracking(job_id)

            # Update status
            self.job_manager.update_job_status(job_id, phase="enriching")

            # Resume enrichment
            success = await self.enrichment_manager.resume_job_enrichment(job_id)

            if success:
                self.job_manager.complete_job(job_id, success=True)
                await self.progress_tracker.send_completion(job_id, success=True)
            else:
                raise Exception("Failed to resume enrichment")

        except Exception as e:
            logger.error(f"Resume enrichment failed: {e}")
            self.job_manager.complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        finally:
            await self.progress_tracker.stop_tracking(job_id)
