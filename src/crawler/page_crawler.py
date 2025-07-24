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
from .llm_retry import LLMRetryExtractor

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
    markdown_content: Optional[str] = None


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
        self.llm_extractor = LLMRetryExtractor()

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
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
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
                for i in range(worker_count):
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

        except asyncio.CancelledError:
            logger.info(f"Crawl cancelled for {url}")
            raise
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            if "cancelled" not in str(e).lower():
                await self._record_failed_page(job_id, url, str(e))
            return None

    async def _is_job_cancelled(self, job_id: str) -> bool:
        """Check if job is cancelled."""
        with self.db_manager.session_scope() as session:
            from ..database.models import CrawlJob
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            return job and job.status == "cancelled"
    
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
        while True:
            try:
                result = await extraction_queue.get()
                if result is None:  # Shutdown signal
                    break
                
                async with semaphore:
                    # Process the crawl result
                    processed_result = await self._process_crawl_result_with_llm(
                        result, job_id, depth
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

    async def _process_crawl_result_with_llm(
        self, 
        result: Any, 
        job_id: str, 
        depth: int
    ) -> Optional[CrawlResult]:
        """Process a single crawl result with LLM extraction."""
        if not result.success:
            logger.error(f"Failed to crawl {result.url}: {result.error_message}")
            await self._record_failed_page(job_id, result.url, result.error_message)
            return None
            
        # Get depth from metadata if available
        page_depth = depth
        if hasattr(result, "metadata") and result.metadata and "depth" in result.metadata:
            page_depth = result.metadata["depth"]

        # Extract markdown content
        markdown_content = self._extract_markdown_content(result)
        if not markdown_content:
            logger.warning(f"No markdown content extracted from {result.url}")
            return None
        
        # Extract title
        title = ""
        if hasattr(result, "metadata") and result.metadata:
            title = result.metadata.get("title", "")
        
        # Calculate content hash
        content_hash = hashlib.md5(markdown_content.encode("utf-8")).hexdigest()
        
        # Check if content has changed
        with self.db_manager.session_scope() as session:
            from ..database import check_content_hash
            content_unchanged, existing_snippet_count = check_content_hash(
                session, result.url, content_hash
            )
            
            if content_unchanged:
                logger.info(f"Content unchanged for {result.url}, skipping LLM extraction. "
                           f"Using {existing_snippet_count} existing snippets.")
                
                # Create result without LLM extraction
                return CrawlResult(
                    url=result.url,
                    title=title,
                    content=markdown_content,
                    content_hash=content_hash,
                    code_blocks=[],  # Empty since we're reusing existing
                    metadata={
                        "depth": page_depth,
                        "content_unchanged": True,
                        "existing_snippet_count": existing_snippet_count,
                        "skipped_llm_extraction": True
                    }
                )
        
        # Content changed or new - proceed with LLM extraction
        logger.info(f"Content changed/new for {result.url}, performing LLM extraction")
        
        # Use LLM to extract code blocks
        extraction_result = await self.llm_extractor.extract_with_retry(
            markdown_content=markdown_content,
            url=result.url,
            title=title
        )
        
        if not extraction_result:
            logger.error(f"LLM extraction failed for {result.url}")
            await self._record_failed_page(job_id, result.url, "LLM extraction failed")
            # Mark job as failed if this is a critical error
            # The job manager will handle this through health monitoring
            return None
        
        # Convert extraction result to code blocks format
        code_blocks = self._convert_extraction_to_blocks(extraction_result)
        
        # Create CrawlResult with extracted code blocks
        metadata = {
            "depth": page_depth,
            "status_code": 200,
            "success": True,
            "llm_page_metadata": extraction_result.page_metadata.model_dump(),
            "key_concepts": extraction_result.key_concepts,
            "external_links": extraction_result.external_links,
            "extraction_method": "llm",
            "extraction_model": extraction_result.extraction_model,
            "extraction_timestamp": extraction_result.extraction_timestamp,
        }
        
        crawl_result = CrawlResult(
            url=result.url,
            title=title,
            content=markdown_content,
            content_hash=content_hash,
            code_blocks=code_blocks,
            metadata=metadata,
            markdown_content=markdown_content,
        )
        
        logger.info(f"Successfully extracted {len(code_blocks)} code blocks from {result.url}")
        return crawl_result


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
                    code_blocks = self._process_llm_extraction(result.extracted_content, metadata)
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

            # Add metadata
            if hasattr(result, "metadata") and result.metadata:
                metadata["crawl4ai_metadata"] = result.metadata
            metadata["extraction_method"] = "llm"

            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content or "",
                content_hash=content_hash,
                code_blocks=code_blocks,
                metadata=metadata,
                markdown_content=markdown_content,
            )

        except Exception as e:
            logger.error(f"Error converting result: {e}")
            return None

    def _process_llm_extraction(self, extracted_content: Any, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process LLM extracted content into code blocks."""
        import json
        from .extraction_models import LLMExtractionResult

        # Parse extracted content
        if isinstance(extracted_content, str):
            extracted_data: Dict[str, Any] = json.loads(extracted_content)
        else:
            extracted_data: Dict[str, Any] = extracted_content

        # Handle error responses
        if isinstance(extracted_data, list) and len(extracted_data) > 0:
            first_item = extracted_data[0]
            if isinstance(first_item, dict) and first_item.get("error") == True:
                error_msg = first_item.get("content", "Unknown extraction error")
                raise ValueError(f"LLM extraction failed: {error_msg}")

        # Handle different response formats
        if isinstance(extracted_data, list) and len(extracted_data) == 1:
            extracted_data = extracted_data[0]

        # Handle legacy format
        if isinstance(extracted_data, dict) and "blocks" in extracted_data and "code_blocks" not in extracted_data:
            logger.warning("LLM returned 'blocks' instead of 'code_blocks', transforming...")
            blocks = extracted_data.pop("blocks")
            extracted_data["code_blocks"] = [
                {**block, "code": block.pop("content")} if "content" in block and "code" not in block else block
                for block in blocks
            ]

        # Ensure required fields
        if "extraction_timestamp" not in extracted_data:
            extracted_data["extraction_timestamp"] = datetime.now().isoformat()
        if "extraction_model" not in extracted_data:
            extracted_data["extraction_model"] = self.settings.code_extraction.llm_extraction_model
        
        # Ensure page_metadata exists with required fields
        if "page_metadata" not in extracted_data:
            extracted_data["page_metadata"] = {
                "main_topic": "Unknown",
                "page_type": "unknown",
                "technologies": []
            }

        # Validate with Pydantic
        extraction_result = LLMExtractionResult(
            code_blocks=extracted_data.get("code_blocks", []),
            page_metadata=extracted_data["page_metadata"],
            key_concepts=extracted_data.get("key_concepts", []),
            external_links=extracted_data.get("external_links", []),
            extraction_timestamp=extracted_data.get("extraction_timestamp"),
            extraction_model=extracted_data.get("extraction_model")
        )

        logger.info(f"LLM extraction result: {len(extraction_result.code_blocks)} code blocks found")

        # Convert to our format
        code_blocks = []
        for block in extraction_result.code_blocks:
            code_blocks.append({
                'code': block.code,
                'language': block.language,
                'title': block.title,
                'filename': block.filename,
                'description': block.description,
                'extraction_method': 'llm',
                'metadata': {
                    'purpose': block.purpose,
                    'frameworks': block.frameworks,
                    'keywords': block.keywords,
                    'dependencies': block.dependencies,
                    'section': block.section,
                    'prerequisites': block.prerequisites,
                    'relationships': [r.model_dump() for r in block.relationships],
                    'extraction_model': extraction_result.extraction_model,
                    'extraction_timestamp': extraction_result.extraction_timestamp,
                },
            })

        # Add page metadata
        metadata["llm_page_metadata"] = extraction_result.page_metadata.model_dump()
        metadata["key_concepts"] = extraction_result.key_concepts
        metadata["external_links"] = extraction_result.external_links

        return code_blocks

    def _convert_extraction_to_blocks(self, extraction_result) -> List[Dict[str, Any]]:
        """Convert LLMExtractionResult to code blocks format."""
        code_blocks = []
        for block in extraction_result.code_blocks:
            code_blocks.append({
                'code': block.code,
                'language': block.language,
                'title': block.title,
                'filename': block.filename,
                'description': block.description,
                'extraction_method': 'llm',
                'metadata': {
                    'purpose': block.purpose,
                    'frameworks': block.frameworks,
                    'keywords': block.keywords,
                    'dependencies': block.dependencies,
                    'section': block.section,
                    'prerequisites': block.prerequisites,
                    'relationships': [r.model_dump() for r in block.relationships],
                    'extraction_model': extraction_result.extraction_model,
                    'extraction_timestamp': extraction_result.extraction_timestamp,
                },
            })
        return code_blocks

    def _extract_markdown_content(self, result: Any) -> Optional[str]:
        """Extract markdown content from result."""
        if hasattr(result, "markdown") and result.markdown:
            if isinstance(result.markdown, dict):
                return result.markdown.get("fit_markdown", "")
            elif isinstance(result.markdown, str):
                return result.markdown
        return None

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
