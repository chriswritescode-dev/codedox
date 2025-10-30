"""Page crawling implementation using Crawl4AI."""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from crawl4ai import (
    AsyncWebCrawler,
    RateLimiter,
    SemaphoreDispatcher,
)

from ..config import get_settings
from ..database import get_db_manager
from .config import BrowserConfig, create_crawler_config
from .extractors.html import HTMLCodeExtractor
from .extractors.models import ExtractedCodeBlock
from .failed_page_utils import record_failed_page
from .llm_retry import LLMDescriptionGenerator

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result from crawling a single page."""

    url: str
    title: str
    content: str
    content_hash: str
    code_blocks: list[ExtractedCodeBlock]
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PageCrawler:
    """Handles page crawling operations."""

    def __init__(self, browser_config: BrowserConfig):
        """Initialize page crawler.

        Args:
            browser_config: Browser configuration
        """
        self.browser_config = browser_config
        self.db_manager = get_db_manager()
        self.description_generator = None
        self.html_extractor = HTMLCodeExtractor()
    
    @property
    def settings(self):
        return get_settings()

    async def crawl_page(
        self,
        url: str,
        job_id: str,
        depth: int,
        max_depth: int = 0,
        job_config: dict[str, Any] | None = None,
        progress_tracker: Any | None = None,
    ) -> list[CrawlResult] | None:
        """Crawl a page or site using Crawl4AI.

        Args:
            url: URL to crawl
            job_id: Job ID for tracking
            depth: Current crawl depth
            max_depth: Maximum depth for deep crawling (0 for single page)
            job_config: Job configuration

        Returns:
            List of CrawlResult objects or None if failed
        """
        logger.info(f"Starting crawl for URL: {url}, job_id: {job_id}, max_depth: {max_depth}")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"crawl_page called with url={url}, max_depth={max_depth}")

        # Get API key for LLM extraction
        api_key = None
        if self.settings.code_extraction.llm_api_key:
            api_key = self.settings.code_extraction.llm_api_key.get_secret_value()

        if not api_key:
            logger.error("LLM extraction API key not found. Please set CODE_LLM_API_KEY in your .env file")
            raise ValueError("LLM extraction API key is required")

        # Get user agent from settings
        user_agent = self.settings.crawling.user_agent

        try:
            # Check job status before starting
            if await self._is_job_cancelled(job_id):
                logger.info(f"Job {job_id} is already cancelled before starting crawl")
                raise asyncio.CancelledError("Job cancelled before crawl started")

            if logger.isEnabledFor(logging.DEBUG):
                current_task = asyncio.current_task()
                logger.debug(f"Current task: {current_task}, cancelled: {current_task.cancelled() if current_task else 'No task'}")
                logger.debug(f"Creating AsyncWebCrawler with config: {self.browser_config}")
                logger.debug(f"Browser config details - headless: {self.browser_config.headless}, viewport: {self.browser_config.viewport_width}x{self.browser_config.viewport_height}")

            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("AsyncWebCrawler created successfully")
                results = []

                # Configure rate limiter and dispatcher
                max_concurrent = job_config.get("max_concurrent_crawls", get_settings().crawling.max_concurrent_crawls) if job_config else get_settings().crawling.max_concurrent_crawls
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Setting up dispatcher with max_concurrent_crawls={max_concurrent}")

                rate_limiter = RateLimiter(base_delay=(1.0, 2.0), max_delay=30.0, max_retries=4)
                dispatcher = SemaphoreDispatcher(
                    semaphore_count=5,
                    max_session_permit=max_concurrent,
                    rate_limiter=rate_limiter,
                )

                # Use streaming for all crawls
                crawled_count = 0

                # Create queue for parallel processing
                extraction_queue = asyncio.Queue()
                processed_results = asyncio.Queue()

                # Start worker tasks for parallel LLM code extraction
                # Get the number of parallel LLM workers from config
                llm_parallel_limit = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                worker_count = llm_parallel_limit
                extraction_semaphore = asyncio.Semaphore(llm_parallel_limit)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Starting {worker_count} LLM extraction workers with semaphore limit {llm_parallel_limit}")

                workers = []
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Creating {worker_count} extraction workers")
                for i in range(worker_count):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Creating worker {i+1}")
                    worker = asyncio.create_task(
                        self._extraction_worker(
                            extraction_queue,
                            processed_results,
                            extraction_semaphore,
                            job_id,
                            depth,
                            progress_tracker,
                            job_config
                        )
                    )
                    workers.append(worker)

                # Track progress for WEB UI updates only
                crawl_progress = {
                    'crawled_count': 0,
                    'processed_count': 0,
                    'last_ws_count': 0,
                    'snippets_extracted': 0,
                    'base_snippet_count': job_config.get('base_snippet_count', 0) if job_config else 0
                }

                # Result collector task
                collector_task = asyncio.create_task(
                    self._collect_results(processed_results, results, crawl_progress, progress_tracker, job_id)
                )

                try:
                    # Create crawler run config
                    crawler_run_config = create_crawler_config(
                        max_depth=max_depth,
                        domain_restrictions=job_config.get("domain_restrictions") if job_config else None,
                        include_patterns=job_config.get("include_patterns") if job_config else None,
                        user_agent=user_agent,
                        max_pages=job_config.get("max_pages") if job_config else None,
                    )

                    # Check if streaming is supported
                    logger.info(f"Starting crawler.arun for URL: {url}")
                    result_container = await crawler.arun(
                        url, config=crawler_run_config, dispatcher=dispatcher
                    )
                    logger.info(f"Crawler.arun completed for URL: {url}")

                    # Handle streaming if the result supports it
                    if hasattr(result_container, '__aiter__'):
                        # Streaming mode
                        logger.info("Streaming mode detected, starting to process pages")
                        async for result in result_container:
                            crawled_count += 1
                            crawl_progress['crawled_count'] = crawled_count

                            # Check if job is cancelled periodically
                            if crawled_count % 5 == 0:
                                if await self._is_job_cancelled(job_id):
                                    logger.info(f"Crawl job {job_id} is cancelled - stopping crawl")
                                    raise asyncio.CancelledError("Job cancelled by user")

                            # Queue result for parallel LLM code extraction
                            logger.debug(f"Queueing page {crawled_count} for extraction: {result.url if hasattr(result, 'url') else 'unknown'}")
                            await extraction_queue.put(result)
                            logger.debug(f"Successfully queued page {crawled_count} for extraction")

                            # Send progress update for crawling
                            if progress_tracker and crawled_count % 3 == 0:  # Update every 3 pages
                                await progress_tracker.update_progress(
                                    job_id,
                                    processed_pages=crawl_progress['processed_count'],
                                    total_pages=crawled_count,
                                    documents_crawled=crawl_progress['processed_count'],
                                    send_notification=True
                                )
                    else:
                        # Non-streaming mode - handle as a list of results
                        results_list = []
                        if hasattr(result_container, 'results'):
                            results_list = result_container.results
                        elif isinstance(result_container, list):
                            results_list = result_container
                        else:
                            # Single result
                            results_list = [result_container]

                        for result in results_list:
                            crawled_count += 1
                            crawl_progress['crawled_count'] = crawled_count

                            # Check if job is cancelled periodically
                            if crawled_count % 5 == 0:
                                if await self._is_job_cancelled(job_id):
                                    logger.info(f"Crawl job {job_id} is cancelled - stopping crawl")
                                    raise asyncio.CancelledError("Job cancelled by user")

                            # Queue result for parallel LLM code extraction
                            logger.debug(f"Queueing page {crawled_count} for extraction: {result.url if hasattr(result, 'url') else 'unknown'}")
                            await extraction_queue.put(result)
                            logger.debug(f"Successfully queued page {crawled_count} for extraction")

                            # Send progress update for crawling
                            if progress_tracker and crawled_count % 3 == 0:  # Update every 3 pages
                                await progress_tracker.update_progress(
                                    job_id,
                                    processed_pages=crawl_progress['processed_count'],
                                    total_pages=crawled_count,
                                    documents_crawled=crawl_progress['processed_count'],
                                    send_notification=True
                                )

                    # Signal workers to stop
                    for _ in workers:
                        await extraction_queue.put(None)

                    # Wait for all workers to complete
                    await asyncio.gather(*workers)

                    # Signal collector to stop
                    await processed_results.put(None)
                    await collector_task

                finally:
                    # Cancel any remaining tasks
                    for worker in workers:
                        if not worker.done():
                            worker.cancel()
                    if not collector_task.done():
                        collector_task.cancel()

                skipped_count = crawl_progress.get('skipped_count', 0)
                new_extraction_count = crawl_progress['processed_count'] - skipped_count

                logger.info(f"Crawl completed. Total: {crawled_count}, new: {new_extraction_count}, skipped: {skipped_count}")

                if skipped_count > 0 and logger.isEnabledFor(logging.DEBUG):
                    efficiency_pct = (skipped_count / crawl_progress['processed_count']) * 100
                    logger.debug(f"LLM extraction efficiency: {efficiency_pct:.1f}% of pages skipped (unchanged content)")


                return results if results else None

        except asyncio.CancelledError as e:
            logger.info(f"Crawl cancelled for {url}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                import traceback
                logger.debug(f"Cancellation stack trace: {traceback.format_exc()}")
            raise
        except Exception as e:
            error_msg = str(e)
            
            if "Executable doesn't exist" in error_msg and "playwright" in error_msg.lower():
                logger.error("Playwright browsers are not installed. Please run: playwright install")
                logger.error("Or use the setup script: ./setup.sh")
                detailed_error = (
                    "Playwright browsers not installed. "
                    "Run 'playwright install' or './setup.sh' to install required browsers."
                )
                await record_failed_page(job_id, url, detailed_error)
                raise RuntimeError(detailed_error) from e
            
            logger.error(f"Error crawling {url}: {e}", exc_info=True)
            if "cancelled" not in error_msg.lower():
                await record_failed_page(job_id, url, error_msg)
            return None

    async def crawl_multiple_urls(
        self,
        urls: list[str],
        job_id: str,
        job_config: dict[str, Any] | None = None,
        progress_tracker: Any | None = None,
    ) -> list[CrawlResult]:
        """Crawl multiple URLs efficiently using arun_many.
        
        Args:
            urls: List of URLs to crawl
            job_id: Job ID for tracking
            job_config: Job configuration
            progress_tracker: Progress tracker instance
            
        Returns:
            List of CrawlResult objects
        """
        logger.info(f"Starting multi-URL crawl for {len(urls)} URLs with job_id: {job_id}")

        # Get API key for LLM extraction
        api_key = None
        if self.settings.code_extraction.llm_api_key:
            api_key = self.settings.code_extraction.llm_api_key.get_secret_value()

        if not api_key:
            logger.error("LLM extraction API key not found. Please set CODE_LLM_API_KEY in your .env file")
            raise ValueError("LLM extraction API key is required")

        # Get user agent from settings
        user_agent = self.settings.crawling.user_agent

        all_results = []

        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                # Configure rate limiter and dispatcher for multi-URL crawling
                max_concurrent = job_config.get("max_concurrent_crawls", get_settings().crawling.max_concurrent_crawls) if job_config else get_settings().crawling.max_concurrent_crawls

                rate_limiter = RateLimiter(base_delay=(1.0, 2.0), max_delay=30.0, max_retries=4)
                dispatcher = SemaphoreDispatcher(
                    semaphore_count=5,
                    max_session_permit=max_concurrent,
                    rate_limiter=rate_limiter,
                )

                # Create crawler config for single page crawls (max_depth=0)
                crawler_run_config = create_crawler_config(
                    max_depth=0,
                    domain_restrictions=job_config.get("domain_restrictions") if job_config else None,
                    include_patterns=job_config.get("include_patterns") if job_config else None,
                    user_agent=user_agent,
                    max_pages=job_config.get("max_pages") if job_config else None,
                )

                # Create queues for parallel processing
                extraction_queue = asyncio.Queue()
                processed_results = asyncio.Queue()

                # Start extraction workers
                llm_parallel_limit = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                extraction_semaphore = asyncio.Semaphore(llm_parallel_limit)

                workers = []
                for _i in range(llm_parallel_limit):
                    worker = asyncio.create_task(
                        self._extraction_worker(
                            extraction_queue,
                            processed_results,
                            extraction_semaphore,
                            job_id,
                            0,  # depth is 0 for single page crawls
                            progress_tracker,
                            job_config
                        )
                    )
                    workers.append(worker)

                # Track progress
                crawl_progress = {
                    'crawled_count': 0,
                    'processed_count': 0,
                    'last_ws_count': 0,
                    'snippets_extracted': 0,
                    'base_snippet_count': job_config.get('base_snippet_count', 0) if job_config else 0
                }

                # Result collector task
                collector_task = asyncio.create_task(
                    self._collect_results(processed_results, all_results, crawl_progress, progress_tracker, job_id)
                )

                try:
                    # Use arun_many for efficient multi-URL crawling
                    logger.info(f"Starting crawler.arun_many for {len(urls)} URLs")



                    # Enable streaming in the config
                    crawler_run_config.stream = True

                    # arun_many returns either an async generator (when streaming) or a container
                    logger.info("Calling arun_many with dispatcher...")
                    results = await crawler.arun_many(urls, config=crawler_run_config)
                    logger.info("arun_many completed successfully")

                    # Check if results is iterable
                    logger.info(f"Results type: {type(results)}")
                    logger.info(f"Results has __aiter__: {hasattr(results, '__aiter__')}")

                    # Since we enabled streaming, we can iterate directly
                    logger.info("Starting to iterate over results...")
                    async for result in results:
                        crawl_progress['crawled_count'] += 1

                        # Check if job is cancelled periodically
                        if crawl_progress['crawled_count'] % 5 == 0:
                            if await self._is_job_cancelled(job_id):
                                logger.info(f"Crawl job {job_id} is cancelled - stopping crawl")
                                raise asyncio.CancelledError("Job cancelled by user")

                        # Queue result for extraction
                        await extraction_queue.put(result)

                        # Send progress update
                        if progress_tracker and crawl_progress['crawled_count'] % 3 == 0:
                            await progress_tracker.update_progress(
                                job_id,
                                processed_pages=crawl_progress['processed_count'],
                                total_pages=crawl_progress['crawled_count'],
                                documents_crawled=crawl_progress['processed_count'],
                                send_notification=True
                            )

                    # Signal workers to stop
                    for _ in workers:
                        await extraction_queue.put(None)

                    # Wait for all workers to complete
                    await asyncio.gather(*workers)

                    # Signal collector to stop
                    await processed_results.put(None)
                    await collector_task

                finally:
                    # Cancel any remaining tasks
                    for worker in workers:
                        if not worker.done():
                            worker.cancel()
                    if not collector_task.done():
                        collector_task.cancel()

                logger.info(f"Multi-URL crawl completed. Processed {crawl_progress['processed_count']} pages, extracted {crawl_progress['snippets_extracted']} snippets")

                return all_results if all_results else []

        except asyncio.CancelledError as e:
            logger.info(f"Multi-URL crawl cancelled: {e}")
            raise
        except AttributeError as e:
            logger.error(f"AttributeError in multi-URL crawl: {e}", exc_info=True)
            logger.error(f"Error details - Dispatcher type: {type(dispatcher) if 'dispatcher' in locals() else 'Not available'}")
            logger.error(f"Available dispatcher methods: {[method for method in dir(dispatcher) if not method.startswith('_')]} if 'dispatcher' in locals() else 'Not available'")
            for url in urls:
                await record_failed_page(job_id, url, str(e))
            return []
        except Exception as e:
            error_msg = str(e)
            
            if "Executable doesn't exist" in error_msg and "playwright" in error_msg.lower():
                logger.error("Playwright browsers are not installed. Please run: playwright install")
                logger.error("Or use the setup script: ./setup.sh")
                detailed_error = (
                    "Playwright browsers not installed. "
                    "Run 'playwright install' or './setup.sh' to install required browsers."
                )
                for url in urls:
                    await record_failed_page(job_id, url, detailed_error)
                raise RuntimeError(detailed_error) from e
            
            logger.error(f"Error in multi-URL crawl: {e}", exc_info=True)
            for url in urls:
                await record_failed_page(job_id, url, error_msg)
            return []

    async def _is_job_cancelled(self, job_id: str) -> bool:
        """Check if job is cancelled."""
        with self.db_manager.session_scope() as session:
            from ..database.models import CrawlJob
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job:
                is_cancelled = bool(job.status == "cancelled")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Job {job_id} status: {job.status}, is_cancelled: {is_cancelled}")
                return is_cancelled
            else:
                logger.warning(f"Job {job_id} not found in database")
                return True  # If job not found, consider it cancelled to stop processing

    async def _extraction_worker(
        self,
        extraction_queue: asyncio.Queue,
        processed_results: asyncio.Queue,
        semaphore: asyncio.Semaphore,
        job_id: str,
        depth: int,
        progress_tracker: Any | None = None,
        job_config: dict[str, Any] | None = None
    ) -> None:
        """Worker that extracts code from markdown content."""
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Extraction worker started for job {job_id}")
        worker_id = id(asyncio.current_task())
        logger.info(f"Extraction worker {worker_id} started")
        while True:
            try:
                result = await extraction_queue.get()

                if result is None:  # Shutdown signal
                    break

                # Process the crawl result (semaphore used internally for LLM calls)
                logger.info(f"Worker {worker_id} processing: {result.url if hasattr(result, 'url') else 'unknown'}")
                processed_result = await self._process_crawl_result_with_html_extraction(
                    result, job_id, depth, llm_semaphore=semaphore, job_config=job_config, progress_tracker=progress_tracker
                )
                logger.info(f"Worker {worker_id} completed processing: {result.url if hasattr(result, 'url') else 'unknown'}")

                if processed_result:
                    await processed_results.put(processed_result)

            except Exception as e:
                logger.error(f"Error in extraction worker: {e}")

    async def _collect_results(
        self,
        processed_results: asyncio.Queue,
        results: list[CrawlResult],
        crawl_progress: dict[str, int],
        progress_tracker: Any | None,
        job_id: str
    ) -> None:
        """Collect processed results from workers and update progress."""
        while True:
            result = await processed_results.get()

            if result is None:
                break

            results.append(result)
            crawl_progress['processed_count'] += 1

            if result.metadata.get('existing_snippet_count'):
                crawl_progress['snippets_extracted'] += result.metadata.get('existing_snippet_count', 0)

            if result.metadata.get('content_unchanged'):
                crawl_progress['skipped_count'] = crawl_progress.get('skipped_count', 0) + 1

            if progress_tracker:
                should_update = crawl_progress['processed_count'] - crawl_progress['last_ws_count'] >= 3
                if should_update:
                    crawl_progress['last_ws_count'] = crawl_progress['processed_count']
                    await progress_tracker.update_progress(
                        job_id,
                        processed_pages=crawl_progress['processed_count'],
                        total_pages=crawl_progress['crawled_count'],
                        documents_crawled=crawl_progress['processed_count'],
                        send_notification=True
                    )

    async def _process_crawl_result_with_html_extraction(
        self,
        result: Any,
        job_id: str,
        depth: int,
        llm_semaphore: asyncio.Semaphore | None = None,
        job_config: dict[str, Any] | None = None,
        progress_tracker: Any | None = None
    ) -> CrawlResult | None:
        """Process a single crawl result with HTML extraction + LLM descriptions."""
        try:
            if not result.success:
                logger.error(f"Failed to crawl {result.url}: {result.error_message}")
                await record_failed_page(job_id, result.url, result.error_message)
                return None
        except AttributeError as e:
            logger.error(f"Result object missing expected attributes: {e}")
            logger.error(f"Result type: {type(result)}, Result: {result}")
            return None

        # Get depth from metadata if available
        page_depth = depth
        if hasattr(result, "metadata") and result.metadata and "depth" in result.metadata:
            page_depth = result.metadata["depth"]

        # Extract HTML content for HTML-based extraction
        html_content = getattr(result, 'html', None)
        if not html_content:
            logger.warning(f"No HTML content found in result for {result.url}")
            return None

        # Get raw markdown for content hash comparison (for change detection)
        markdown_for_hash = self._extract_markdown_content(result, for_hash=True)
        if not markdown_for_hash:
            logger.warning(f"No raw markdown content for content hash from {result.url}")
            return None

        # Also get markdown for actual content (may be fit_markdown)
        markdown_content = self._extract_markdown_content(result)
        if not markdown_content:
            markdown_content = markdown_for_hash  # Fall back to raw if no fit_markdown
            
        title = ""
        page_metadata = {}
        if hasattr(result, "metadata") and result.metadata:
            title = result.metadata.get("title", "")
            # Extract all metadata including Open Graph tags
            page_metadata = result.metadata.copy()

        # Calculate content hash from raw markdown for consistency
        content_hash = hashlib.md5(markdown_for_hash.encode("utf-8")).hexdigest()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Content hash for {result.url}: {content_hash[:8]}... (using raw_markdown)")

        # Check if we should ignore hash (for regeneration)
        ignore_hash = False
        if job_config and isinstance(job_config, dict):
            job_metadata = job_config.get('metadata', {})
            ignore_hash = job_metadata.get('ignore_hash', False)
            logger.info(f"DEBUG: job_metadata = {job_metadata}, ignore_hash = {ignore_hash}")
            if ignore_hash:
                logger.info(f"Ignoring content hash for {result.url} - forcing regeneration")

        # Check if content has changed (skip ONLY if ignore_hash is False)
        if not ignore_hash:
            with self.db_manager.session_scope() as session:
                from ..database import check_content_hash
                content_unchanged, existing_snippet_count = check_content_hash(
                    session, result.url, content_hash
                )

                if content_unchanged:
                    # Log at INFO level for retry jobs to track efficiency
                    is_retry_job = job_config and job_config.get('metadata', {}).get('retry_of_job')
                    if is_retry_job:
                        logger.info(f"[RETRY EFFICIENCY] Content unchanged for {result.url} (hash: {content_hash[:8]}...), skipping extraction. Using {existing_snippet_count} existing snippets.")
                    elif logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Content unchanged for {result.url}, skipping extraction. Using {existing_snippet_count} existing snippets.")

                    return CrawlResult(
                        url=result.url,
                        title=title,
                        content=markdown_content,
                        content_hash=content_hash,
                        code_blocks=[],
                        metadata={
                            "depth": page_depth,
                            "content_unchanged": True,
                            "existing_snippet_count": existing_snippet_count,
                            "skipped_extraction": True,
                            "is_retry": bool(is_retry_job),
                            **page_metadata  # Include all extracted metadata
                        }
                    )
        else:
            # When ignore_hash is True, we force extraction even if content hasn't changed
            logger.info(f"Force regeneration enabled for {result.url}, proceeding with extraction despite content hash")

        # Content changed or new - extract code blocks from HTML
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Content changed/new for {result.url}, performing HTML extraction")

        html_blocks = []
        try:
            # Use HTML extraction
            logger.info(f"Using HTML extraction for {result.url}")
            
            # Get batch size from job config (matches max_concurrent_crawls)
            batch_size = job_config.get("max_concurrent_crawls", 5) if job_config else 5
            
            # Extract code blocks from HTML content
            extracted_blocks = await self.html_extractor.extract_blocks(html_content, result.url, batch_size=batch_size)
            
            # Use ExtractedCodeBlock directly
            html_blocks.extend(extracted_blocks)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Found {len(html_blocks)} code blocks via HTML extraction for {result.url}")

        except Exception as e:
            logger.error(f"HTML extraction error for {result.url}: {e}", exc_info=True)

        if not html_blocks:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"No code blocks found for {result.url}")
            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content,
                content_hash=content_hash,
                code_blocks=[],
                metadata={
                    "depth": page_depth,
                    "extraction_method": "html",
                    "blocks_found": 0,
                    **page_metadata  # Include all extracted metadata
                }
            )

        # Check if LLM extraction is enabled
        settings = get_settings()
        enable_llm = settings.code_extraction.enable_llm_extraction
        
        # Override with job config if specified
        if job_config and isinstance(job_config, dict):
            metadata = job_config.get('metadata', {})
            # Allow job-level override
            if 'enable_llm_extraction' in metadata:
                enable_llm = metadata['enable_llm_extraction']

        processed_blocks = []
        
        if not enable_llm:
            # Non-LLM extraction: use page title and context
            logger.info(f"LLM extraction disabled, using fallback extraction for {len(html_blocks)} blocks from {result.url}")
            
            for i, block in enumerate(html_blocks, 1):
                # Use title from HTML extractor if available, otherwise generate from page title
                block_title = block.title if block.title else f"{title} - Code Block {i}" if title else f"Code Block {i}"
                
                # Use the description already extracted by HTML extractor first
                block_description = block.description if block.description else ""
                
                # Fallback to context description if available
                if not block_description and block.context and block.context.description:
                    # Use the context description
                    block_description = block.context.description.strip()
                
                # Only use generic description as last resort
                if not block_description:
                    block_description = f"Code snippet from {title if title else 'documentation'}"
                
                processed_blocks.append({
                    'code': block.code,
                    'language': block.language or 'text',
                    'title': block_title,
                    'description': block_description,
                    'source_url': block.source_url,
                    'metadata': {

                        'extraction_method': 'html_only'
                    }
                })
            
            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content,
                content_hash=content_hash,
                code_blocks=processed_blocks,
                metadata={
                    "depth": page_depth,
                    "extraction_method": "html_only",
                    "blocks_found": len(processed_blocks),
                    **page_metadata
                }
            )
        
        # LLM extraction enabled - proceed with original logic
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Generating LLM descriptions for {len(html_blocks)} code blocks from {result.url}")

        # Keep phase as crawling during LLM work (it's part of the crawl process)
        # No phase update needed here - we stay in 'crawling' phase

        try:
            # Use the provided semaphore or create one if not provided
            if llm_semaphore is None:
                llm_parallel_limit = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                llm_semaphore = asyncio.Semaphore(llm_parallel_limit)

            # Check for custom LLM configuration in job config
            custom_model = None
            custom_api_key = None
            custom_base_url = None

            if job_config and isinstance(job_config, dict):
                metadata = job_config.get('metadata', {})
                custom_model = metadata.get('llm_model')
                custom_api_key = metadata.get('llm_api_key')
                custom_base_url = metadata.get('llm_base_url')

                if logger.isEnabledFor(logging.DEBUG):
                    if custom_model:
                        logger.debug(f"Using custom LLM model: {custom_model}")
                    if custom_api_key:
                        logger.debug("Using custom LLM API key")
                    if custom_base_url:
                        logger.debug(f"Using custom LLM base URL: {custom_base_url}")

            # Initialize description generator with custom config if needed
            if custom_api_key or custom_base_url or not self.description_generator:
                self.description_generator = LLMDescriptionGenerator(
                    api_key=custom_api_key,
                    base_url=custom_base_url,
                    model=custom_model
                )

            blocks_with_descriptions = await self.description_generator.generate_titles_and_descriptions_batch(
                html_blocks, result.url, semaphore=llm_semaphore
            )

            # Convert to the format expected by result processor
            for block in blocks_with_descriptions:
                # Fallback: generate title from description if LLM didn't provide one
                if not block.title and block.description:
                    # Use first few words of description as title
                    words = block.description.split()[:5]
                    block.title = " ".join(words)
                    if len(block.description.split()) > 5:
                        block.title += "..."

                processed_blocks.append({
                    'code': block.code,
                    'language': block.language or 'text',
                    'title': block.title or 'Code Block',
                    'description': block.description or 'No description available',
                    'source_url': block.source_url,
                    'metadata': {

                        'extraction_method': 'html_llm'
                    }
                })


            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content,
                content_hash=content_hash,
                code_blocks=processed_blocks,
                metadata={
                    "depth": page_depth,
                    "extraction_method": "html_llm",
                    "blocks_found": len(processed_blocks),
                    **page_metadata  # Include all extracted metadata
                }
            )

        except Exception as e:
            logger.error(f"Error generating descriptions for {result.url}: {e}")
            # Fall back to blocks without descriptions
            fallback_blocks = []
            for block in html_blocks:
                fallback_blocks.append({
                    'code': block.code,
                    'language': block.language or 'text',
                    'title': 'Code Block',
                    'description': f"Code block in {block.language or 'unknown'} language",
                    'source_url': block.source_url,
                    'metadata': {

                        'extraction_method': 'html_only'
                    }
                })

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Falling back to {len(fallback_blocks)} code blocks without descriptions for {result.url}")

            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content,
                content_hash=content_hash,
                code_blocks=fallback_blocks,
                metadata={
                    "depth": page_depth,
                    "extraction_method": "html_only",
                    "blocks_found": len(fallback_blocks),
                    **page_metadata  # Include all extracted metadata
                }
            )

    def _extract_markdown_content(self, result: Any, for_hash: bool = False) -> str | None:
        """Extract markdown content from result.
        
        Args:
            result: Crawl result object
            for_hash: If True, always return raw_markdown for consistent hashing
        
        Returns:
            Markdown content string or None
        """
        if hasattr(result, "markdown") and result.markdown:
            if isinstance(result.markdown, dict):
                raw_markdown = result.markdown.get("raw_markdown", "")

                # For hash calculation, always use raw_markdown
                if for_hash:
                    return raw_markdown

                # For other uses, prefer fit_markdown
                fit_markdown = result.markdown.get("fit_markdown")
                if fit_markdown:
                    return fit_markdown
                else:
                    return raw_markdown
            elif isinstance(result.markdown, str):
                return result.markdown
        return None
