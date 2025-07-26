"""Page crawling implementation using Crawl4AI."""

import asyncio
import logging
import hashlib
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from crawl4ai import (
    AsyncWebCrawler,
    RateLimiter,
    SemaphoreDispatcher,
)
from .llm_retry import LLMDescriptionGenerator
from .html_code_extractor import HTMLCodeExtractor
from .extraction_models import SimpleCodeBlock

from .config import create_crawler_config, BrowserConfig
from ..database import FailedPage, get_db_manager
from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result from crawling a single page."""

    url: str
    title: str
    content: str
    content_hash: str
    code_blocks: List[Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PageCrawler:
    """Handles page crawling operations."""

    def __init__(self, browser_config: BrowserConfig):
        """Initialize page crawler.

        Args:
            browser_config: Browser configuration
        """
        self.browser_config = browser_config
        self.db_manager = get_db_manager()
        self.settings = get_settings()
        self.description_generator = LLMDescriptionGenerator()
        self.html_extractor = HTMLCodeExtractor()

    async def crawl_page(
        self,
        url: str,
        job_id: str,
        depth: int,
        max_depth: int = 0,
        job_config: Optional[Dict[str, Any]] = None,
        progress_tracker: Optional[Any] = None,
    ) -> Optional[List[CrawlResult]]:
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
        print(f"DEBUG: crawl_page called with url={url}, max_depth={max_depth}")
        logger.info(f"Starting crawl for URL: {url}, job_id: {job_id}, max_depth: {max_depth}")

        # Get API key for LLM extraction
        api_key = None
        if self.settings.code_extraction.llm_api_key:
            api_key = self.settings.code_extraction.llm_api_key.get_secret_value()

        if not api_key:
            logger.error("LLM extraction API key not found. Please set CODE_LLM_API_KEY in your .env file")
            raise ValueError("LLM extraction API key is required")

        # Create unified configuration
        crawler_run_config = create_crawler_config(
            max_depth=max_depth,
            api_key=api_key,
            domain_restrictions=job_config.get("domain_restrictions") if job_config else None,
            include_patterns=job_config.get("include_patterns") if job_config else None,
            exclude_patterns=job_config.get("exclude_patterns") if job_config else None,
        )

        print(f"Config: {crawler_run_config}")
        # Debug: Let's see what's in the config
        print(
            f"Config deep_crawl_strategy: {getattr(crawler_run_config, 'deep_crawl_strategy', 'Not set')}"
        )
        print(
            f"Config extraction_strategy: {getattr(crawler_run_config, 'extraction_strategy', 'Not set')}"
        )

        try:
            # Check job status before starting
            if await self._is_job_cancelled(job_id):
                logger.info(f"Job {job_id} is already cancelled before starting crawl")
                raise asyncio.CancelledError("Job cancelled before crawl started")
            
            logger.info(f"Creating AsyncWebCrawler with config: {self.browser_config}")
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                logger.info("AsyncWebCrawler created successfully")
                results = []

                # Configure rate limiter and dispatcher
                max_concurrent = job_config.get("max_concurrent_crawls", 20) if job_config else 20
                logger.info(f"Setting up dispatcher with max_concurrent_crawls={max_concurrent}")

                rate_limiter = RateLimiter(base_delay=(1.0, 2.0), max_delay=30.0, max_retries=4)
                dispatcher = SemaphoreDispatcher(
                    semaphore_count=5,
                    max_session_permit=max_concurrent,
                    rate_limiter=rate_limiter,
                )

                # Use streaming for all crawls
                crawled_count = 0
                crawl_start_time = asyncio.get_event_loop().time()

                # Create queue for parallel processing
                extraction_queue = asyncio.Queue()
                processed_results = asyncio.Queue()
                
                # Start worker tasks for parallel LLM code extraction
                # Get the number of parallel LLM workers from config
                llm_parallel_limit = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                # Use LLM parallel limit directly for extraction workers
                worker_count = llm_parallel_limit
                extraction_semaphore = asyncio.Semaphore(llm_parallel_limit)
                logger.info(f"Starting {worker_count} LLM extraction workers with semaphore limit {llm_parallel_limit}")
                
                workers = []
                logger.info(f"Creating {worker_count} extraction workers")
                for i in range(worker_count):
                    logger.debug(f"Creating worker {i+1}")
                    worker = asyncio.create_task(
                        self._extraction_worker(
                            extraction_queue, 
                            processed_results, 
                            extraction_semaphore,
                            job_id,
                            depth,
                            progress_tracker
                        )
                    )
                    workers.append(worker)
                logger.info(f"All {worker_count} workers created")
                
                # Track progress
                crawl_progress = {
                    'crawled_count': 0,
                    'processed_count': 0,
                    'snippet_count': 0,
                    'last_ws_count': 0
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
                        exclude_patterns=job_config.get("exclude_patterns") if job_config else None,
                    )
                    
                    # Check if streaming is supported
                    result_container = await crawler.arun(
                        url, config=crawler_run_config, dispatcher=dispatcher
                    )
                    
                    # Handle streaming if the result supports it
                    if hasattr(result_container, '__aiter__'):
                        # Streaming mode
                        async for result in result_container:
                            crawled_count += 1
                            crawl_progress['crawled_count'] = crawled_count

                            # Check if job is cancelled periodically
                            if crawled_count % 5 == 0:
                                if await self._is_job_cancelled(job_id):
                                    logger.info(f"Crawl job {job_id} is cancelled - stopping crawl")
                                    raise asyncio.CancelledError("Job cancelled by user")

                            # Queue result for parallel LLM code extraction
                            await extraction_queue.put(result)
                            
                            # Send progress update for crawling
                            if progress_tracker and crawled_count % 3 == 0:  # Update every 3 pages
                                await progress_tracker.update_progress(
                                    job_id,
                                    processed_pages=crawl_progress['processed_count'],
                                    total_pages=crawled_count,
                                    snippets_extracted=crawl_progress['snippet_count'],
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
                            await extraction_queue.put(result)
                            
                            # Send progress update for crawling
                            if progress_tracker and crawled_count % 3 == 0:  # Update every 3 pages
                                await progress_tracker.update_progress(
                                    job_id,
                                    processed_pages=crawl_progress['processed_count'],
                                    total_pages=crawled_count,
                                    snippets_extracted=crawl_progress['snippet_count'],
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

                total_elapsed = asyncio.get_event_loop().time() - crawl_start_time
                skipped_count = crawl_progress.get('skipped_count', 0)
                new_extraction_count = crawl_progress['processed_count'] - skipped_count
                
                logger.info(f"Crawl completed. Total pages: {crawled_count}, "
                           f"New extractions: {new_extraction_count}, "
                           f"Skipped (unchanged): {skipped_count}, "
                           f"Total time: {total_elapsed:.2f}s")
                
                if skipped_count > 0:
                    efficiency_pct = (skipped_count / crawl_progress['processed_count']) * 100
                    logger.info(f"LLM extraction efficiency: {efficiency_pct:.1f}% of pages skipped (unchanged content)")

                return results if results else None

        except asyncio.CancelledError as e:
            logger.info(f"Crawl cancelled for {url}: {e}")
            # Let's see the full stack trace for debugging
            import traceback
            logger.info(f"Cancellation stack trace: {traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}", exc_info=True)
            if "cancelled" not in str(e).lower():
                await self._record_failed_page(job_id, url, str(e))
            return None

    async def _is_job_cancelled(self, job_id: str) -> bool:
        """Check if job is cancelled."""
        with self.db_manager.session_scope() as session:
            from ..database.models import CrawlJob
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job:
                is_cancelled = bool(job.status == "cancelled")
                logger.info(f"Job {job_id} status: {job.status}, is_cancelled: {is_cancelled}")
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
        progress_tracker: Optional[Any] = None
    ) -> None:
        """Worker that extracts code from markdown content."""
        logger.info(f"Extraction worker started for job {job_id}")
        while True:
            try:
                result = await extraction_queue.get()
                if result is None:  # Shutdown signal
                    break
                
                # Process the crawl result (semaphore used internally for LLM calls)
                processed_result = await self._process_crawl_result_with_html_extraction(
                    result, job_id, depth, llm_semaphore=semaphore
                )
                
                if processed_result:
                    await processed_results.put(processed_result)
                        
            except Exception as e:
                logger.error(f"Error in extraction worker: {e}")
    
    async def _collect_results(
        self,
        processed_results: asyncio.Queue,
        results: List[CrawlResult],
        crawl_progress: Dict[str, int],
        progress_tracker: Optional[Any],
        job_id: str
    ) -> None:
        """Collect processed results from workers and update progress."""
        while True:
            result = await processed_results.get()
            if result is None:  # Shutdown signal
                break
            
            results.append(result)
            crawl_progress['processed_count'] += 1
            
            # Count snippets
            if result.code_blocks:
                crawl_progress['snippet_count'] += len(result.code_blocks)
            elif result.metadata.get('content_unchanged'):
                # Count existing snippets from unchanged content
                existing_count = result.metadata.get('existing_snippet_count', 0)
                crawl_progress['snippet_count'] += existing_count
                # Track skipped pages
                crawl_progress['skipped_count'] = crawl_progress.get('skipped_count', 0) + 1
            
            # Send progress update
            if progress_tracker:
                should_update = crawl_progress['processed_count'] - crawl_progress['last_ws_count'] >= 3
                if should_update:
                    crawl_progress['last_ws_count'] = crawl_progress['processed_count']
                    await progress_tracker.update_progress(
                        job_id,
                        processed_pages=crawl_progress['processed_count'],
                        total_pages=crawl_progress['crawled_count'],
                        snippets_extracted=crawl_progress['snippet_count'],
                        documents_crawled=crawl_progress['processed_count'],
                        send_notification=True
                    )

    async def _process_crawl_result_with_html_extraction(
        self, 
        result: Any, 
        job_id: str, 
        depth: int,
        llm_semaphore: Optional[asyncio.Semaphore] = None
    ) -> Optional[CrawlResult]:
        """Process a single crawl result with HTML extraction + LLM descriptions."""
        try:
            if not result.success:
                logger.error(f"Failed to crawl {result.url}: {result.error_message}")
                await self._record_failed_page(job_id, result.url, result.error_message)
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
        
        # Also get markdown for content hash comparison (for change detection)
        markdown_content = self._extract_markdown_content(result)
        if not markdown_content:
            logger.warning(f"No markdown content for content hash from {result.url}")
            return None
        
        # Extract title and metadata
        title = ""
        page_metadata = {}
        if hasattr(result, "metadata") and result.metadata:
            title = result.metadata.get("title", "")
            # Extract all metadata including Open Graph tags
            page_metadata = result.metadata.copy()
        
        # Calculate content hash
        content_hash = hashlib.md5(markdown_content.encode("utf-8")).hexdigest()
        
        # Check if content has changed
        with self.db_manager.session_scope() as session:
            from ..database import check_content_hash
            content_unchanged, existing_snippet_count = check_content_hash(
                session, result.url, content_hash
            )
            
            if content_unchanged:
                logger.info(f"Content unchanged for {result.url}, skipping extraction. "
                           f"Using {existing_snippet_count} existing snippets.")
                
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
                        **page_metadata  # Include all extracted metadata
                    }
                )
        
        # Content changed or new - extract code blocks from HTML
        logger.info(f"Content changed/new for {result.url}, performing HTML extraction")
        
        html_blocks = []
        try:
            logger.info(f"HTML content found, extracting code blocks for {result.url}")
            extracted_blocks = await self.html_extractor.extract_code_blocks_async(
                html_content, 
                result.url
            )
                
            # Convert to SimpleCodeBlock format
            for block in extracted_blocks:
                simple_block = SimpleCodeBlock(
                    code=block.code,
                    language=block.language,
                    container_type=block.container_type,
                    context_before=block.context_before,
                    context_after=block.context_after,
                    source_url=result.url
                )
                html_blocks.append(simple_block)
                
            logger.info(f"Found {len(html_blocks)} code blocks via HTML extraction for {result.url}")
            
            # Save debug output
            self._save_html_extraction_debug(result.url, extracted_blocks, job_id)
                
        except Exception as e:
            logger.error(f"HTML extraction error for {result.url}: {e}", exc_info=True)
        
        if not html_blocks:
            logger.info(f"No code blocks found for {result.url}")
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
        
        # Generate LLM descriptions for code blocks
        logger.info(f"Generating descriptions for {len(html_blocks)} code blocks from {result.url}")
        try:
            # Use the provided semaphore or create one if not provided
            if llm_semaphore is None:
                llm_parallel_limit = int(os.getenv('CODE_LLM_NUM_PARALLEL', '5'))
                llm_semaphore = asyncio.Semaphore(llm_parallel_limit)
            
            blocks_with_descriptions = await self.description_generator.generate_titles_and_descriptions_batch(
                html_blocks, result.url, semaphore=llm_semaphore
            )
            
            # Convert to the format expected by result processor
            processed_blocks = []
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
                        'container_type': block.container_type,
                        'extraction_method': 'html_llm'
                    }
                })
            
            logger.info(f"Successfully processed {len(processed_blocks)} code blocks for {result.url}")
            
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
                        'container_type': block.container_type,
                        'extraction_method': 'html_only'
                    }
                })
            
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


    async def _process_crawl_result(
        self, 
        result: Any, 
        results: List[CrawlResult], 
        job_id: str, 
        depth: int
    ) -> None:
        """Process a single crawl result (legacy method for non-streaming)."""
        if result.success:
            # Get depth from metadata if available
            page_depth = depth
            if hasattr(result, "metadata") and result.metadata and "depth" in result.metadata:
                page_depth = result.metadata["depth"]

            crawl_result = self._convert_library_result(result, page_depth)
            if crawl_result:
                # Check if LLM extraction failed
                if crawl_result.metadata.get("llm_extraction_failed"):
                    error_msg = crawl_result.metadata.get("llm_extraction_error", "LLM extraction failed")
                    logger.warning(f"LLM extraction failed for {result.url}: {error_msg}")
                    await self._record_failed_page(job_id, result.url, error_msg)
                else:
                    results.append(crawl_result)
                    logger.info(f"Successfully crawled: {result.url} (depth: {page_depth})")
        else:
            logger.error(f"Failed to crawl {result.url}: {result.error_message}")
            await self._record_failed_page(job_id, result.url, result.error_message)

    def _convert_library_result(self, result: Any, depth: int) -> Optional[CrawlResult]:
        """Convert Crawl4AI result to our format.

        Args:
            result: Crawl4AI result
            depth: Page depth

        Returns:
            CrawlResult or None
        """
        try:
            logger.debug(f"Converting result for URL: {result.url}")

            metadata = {
                "depth": depth,
                "status_code": 200 if result.success else 0,
                "success": result.success,
            }

            # Extract title
            title = ""
            if hasattr(result, "metadata") and result.metadata:
                title = result.metadata.get("title", "")

            # Process LLM extracted content
            code_blocks = []
            if hasattr(result, "extracted_content") and result.extracted_content:
                try:
                    # Legacy method - this path should not be used anymore
                    logger.warning(f"Legacy extraction path used for {result.url} - this should be updated")
                    code_blocks = []
                except Exception as e:
                    logger.error(f"Error processing LLM extracted content: {e}")
                    metadata["llm_extraction_failed"] = True
                    metadata["llm_extraction_error"] = str(e)
            else:
                logger.warning(f"No extracted_content for {result.url}")
                if hasattr(result, "error_message") and result.error_message:
                    metadata["llm_extraction_failed"] = True
                    metadata["llm_extraction_error"] = result.error_message

            # Extract markdown content
            markdown_content = self._extract_markdown_content(result)
            if not markdown_content and not code_blocks and not metadata.get("llm_extraction_failed"):
                logger.warning(f"No content extracted from {result.url}")
                return None

            # Calculate content hash
            content_hash = hashlib.md5((markdown_content or "").encode("utf-8")).hexdigest()

            # Add all metadata from result
            if hasattr(result, "metadata") and result.metadata:
                # Include all metadata fields directly
                metadata.update(result.metadata)
                # Also keep a reference to the original
                metadata["crawl4ai_metadata"] = result.metadata
            metadata["extraction_method"] = "llm"

            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content or "",
                content_hash=content_hash,
                code_blocks=code_blocks,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error converting result: {e}")
            return None


    def _extract_markdown_content(self, result: Any) -> Optional[str]:
        """Extract markdown content from result."""
        if hasattr(result, "markdown") and result.markdown:
            if isinstance(result.markdown, dict):
                # Prefer fit_markdown, fall back to raw_markdown
                fit_markdown = result.markdown.get("fit_markdown")
                raw_markdown = result.markdown.get("raw_markdown", "")
                
                if fit_markdown:
                    logger.debug(f"Using fit_markdown for {result.url}")
                    logger.debug(f"Fit markdown length: {len(fit_markdown)} chars")
                    logger.debug(f"Raw markdown length: {len(raw_markdown)} chars (for comparison)")
                    logger.debug(f"Reduction: {((len(raw_markdown) - len(fit_markdown)) / len(raw_markdown) * 100):.1f}%")
                    return fit_markdown
                else:
                    logger.debug(f"No fit_markdown found for {result.url}, using raw_markdown")
                    return raw_markdown
            elif isinstance(result.markdown, str):
                logger.debug(f"Markdown is string type for {result.url}, length: {len(result.markdown)} chars")
                return result.markdown
        logger.debug(f"No markdown content found for {result.url}")
        return None

    def _save_html_extraction_debug(self, url: str, html_blocks: List[Any], job_id: str) -> None:
        """Save HTML extraction results to JSON file for analysis."""
        import json
        from pathlib import Path
        from urllib.parse import urlparse
        
        # Create debug output directory in logs
        debug_dir = Path("logs/html_extraction_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Create job-specific subdirectory
        job_dir = debug_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # Create filename from URL
        parsed_url = urlparse(url)
        filename = f"{parsed_url.netloc}_{parsed_url.path.replace('/', '_')}.json"
        filename = filename.replace("__", "_").strip("_")
        if not filename or filename == ".json":
            filename = "index.json"
        
        # Convert ExtractedCodeBlock objects to dict
        blocks_data = []
        for block in html_blocks:
            blocks_data.append({
                "code": block.code,
                "language": block.language,
                "container_hierarchy": block.container_hierarchy,
                "context_before": block.context_before,
                "context_after": block.context_after,
                "container_type": block.container_type,
                "title": block.title,
                "description": block.description,
                "code_length": len(block.code),
                "has_context": bool(block.context_before or block.context_after)
            })
        
        # Create output data with JSON-serializable stats
        stats_serializable = self.html_extractor.stats.copy()
        stats_serializable['languages_found'] = list(stats_serializable['languages_found'])
        
        output_data = {
            "url": url,
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_blocks": len(html_blocks),
            "blocks": blocks_data,
            "stats": stats_serializable
        }
        
        # Save to file
        output_path = job_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved HTML extraction debug to: {output_path}")

    async def _record_failed_page(self, job_id: str, url: str, error_message: str) -> None:
        """Record a failed page.

        Args:
            job_id: Job ID
            url: Failed URL
            error_message: Error message
        """
        try:
            from uuid import UUID
            from ..database.models import CrawlJob

            # Handle job_id format
            try:
                job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
            except ValueError:
                logger.error(f"Invalid job ID format: {job_id}")
                return

            with self.db_manager.session_scope() as session:
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
                    logger.info(f"Recorded failed page: {url}")
        except Exception as e:
            logger.error(f"Failed to record failed page {url}: {e}")
