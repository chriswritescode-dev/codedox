"""Manage web crawling with Crawl4AI integration."""

import asyncio
import logging
import hashlib
import time
from typing import List, Optional, Dict, Any, Set, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

# Crawl4AI imports
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    BrowserConfig,
    DefaultMarkdownGenerator,
    RateLimiter,
    SemaphoreDispatcher,
    CacheMode,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, URLPatternFilter

from ..config import get_settings
from ..database import CrawlJob, Document, PageLink, FailedPage, get_db_manager
from ..parser import CodeExtractor
from ..language import LanguageDetector
from ..llm import MetadataEnricher, LLMClient, LLMError
from .enrichment_pipeline import EnrichmentPipeline

try:
    from ..api.websocket import notify_crawl_update
except ImportError:

    async def notify_crawl_update(job_id: str, status: str, data: Dict[str, Any]) -> None:
        pass


logger = logging.getLogger(__name__)
settings = get_settings()

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 5
# WebSocket update interval (send updates every N pages)
WS_UPDATE_INTERVAL = 3


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
    respect_robots_txt: bool = False
    content_types: List[str] = field(default_factory=lambda: ["text/markdown", "text/plain"])
    min_content_length: int = 100
    extract_code_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    """Result from crawling a single page."""

    url: str
    title: str
    content: str
    content_hash: str
    links: List[Dict[str, str]]
    code_blocks: List[Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    markdown_content: Optional[str] = None


class CrawlManager:
    """Manages crawling operations with Crawl4AI."""

    def __init__(self) -> None:
        """Initialize the crawl manager."""
        self.settings = settings
        # Use base code extractor
        self.code_extractor = CodeExtractor(
            context_chars=2000,  # Standard context size
            min_code_lines=settings.code_extraction.min_code_lines,
            use_tree_sitter=getattr(settings.code_extraction, "use_tree_sitter_validation", True),
            min_quality_score=getattr(settings.code_extraction, "min_ast_quality_score", 0.7),
        )
        self.language_detector = LanguageDetector()
        self.db_manager = get_db_manager()

        # Browser configuration for Crawl4AI
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=settings.debug,
            viewport={"width": 1200, "height": 800},
            user_agent=settings.crawling.user_agent,
        )

        # Initialize LLM enricher if configured
        self.metadata_enricher: Optional[MetadataEnricher] = None
        self._llm_client: Optional[LLMClient] = None
        self.enrichment_pipeline: Optional[EnrichmentPipeline] = None
        if settings.llm.endpoint:
            self._llm_endpoint = settings.llm.endpoint
            logger.info(
                f"LLM enrichment will be initialized on first use with endpoint: {settings.llm.endpoint}"
            )
        else:
            logger.info("LLM enrichment disabled (no endpoint configured)")

    async def _ensure_llm_enricher(self) -> None:
        """Initialize LLM enricher if not already done."""
        if self.metadata_enricher is None and hasattr(self, "_llm_endpoint"):
            try:
                if not self._llm_client:
                    self._llm_client = LLMClient(debug=self.settings.debug)

                # Test connection to LLM
                test_result = await self._llm_client.test_connection()

                if test_result.get("status") == "connected":
                    self.metadata_enricher = MetadataEnricher(
                        llm_client=self._llm_client, skip_small_snippets=True, min_lines=2
                    )
                    logger.info(
                        f"LLM metadata enricher initialized with {test_result['provider']} at {test_result['endpoint']}"
                    )
                else:
                    logger.warning(
                        f"LLM connection test failed: {test_result.get('error', 'Unknown error')}"
                    )
                    self.metadata_enricher = None  # Mark as failed
            except Exception as e:
                logger.warning(f"Failed to initialize LLM enricher: {e}")
                self.metadata_enricher = None  # Mark as failed

    async def _ensure_enrichment_pipeline(self) -> None:
        """Initialize enrichment pipeline if not already done."""
        # Check if pipeline exists but is not running
        if self.enrichment_pipeline and not self.enrichment_pipeline.is_running:
            logger.warning("Enrichment pipeline exists but is not running. Restarting...")
            await self.enrichment_pipeline.stop()
            self.enrichment_pipeline = None

        if self.enrichment_pipeline is None and hasattr(self, "_llm_endpoint"):
            try:
                if not self._llm_client:
                    self._llm_client = LLMClient(debug=self.settings.debug)

                # Create and start pipeline
                self.enrichment_pipeline = EnrichmentPipeline(llm_client=self._llm_client)
                await self.enrichment_pipeline.start()

                # Verify pipeline is actually running
                stats = self.enrichment_pipeline.get_stats()
                logger.info(f"Enrichment pipeline started successfully - Stats: {stats}")

                if not self.enrichment_pipeline.is_running:
                    raise RuntimeError("Pipeline failed to start properly")

            except Exception as e:
                logger.error(f"Failed to start enrichment pipeline: {e}")
                self.enrichment_pipeline = None

    async def _wait_for_enrichment_completion(self, job_id: str, total_snippets: int) -> None:
        """Wait for enrichment pipeline to complete all tasks.

        Args:
            job_id: Job ID
            total_snippets: Total number of snippets extracted during crawl
        """
        if not self.enrichment_pipeline:
            return

        last_update_time = time.time()
        last_completed_count = 0
        stall_counter = 0
        max_stall_checks = 12  # 2 minutes of no progress

        while True:
            # Get current pipeline stats
            stats = self.enrichment_pipeline.get_stats()
            enrichment_queue = stats["enrichment_queue_size"]
            storage_queue = stats["storage_queue_size"]
            active_tasks = stats["active_tasks"]
            completed_count = stats["completed_count"]
            completed_documents = stats.get("completed_documents", 0)
            error_count = stats["error_count"]

            # Log progress
            logger.info(
                f"Enrichment progress - "
                f"Queue: {enrichment_queue}, "
                f"Storage: {storage_queue}, "
                f"Active: {active_tasks}, "
                f"Completed: {completed_count}/{total_snippets}, "
                f"Errors: {error_count}"
            )

            # Check if enrichment is complete
            # Primary condition: all queues empty and no active tasks
            if enrichment_queue == 0 and storage_queue == 0 and active_tasks == 0:
                logger.info(
                    f"Enrichment completed! Processed {completed_count} items with {error_count} errors"
                )
                break

            # Fallback condition: all workers have finished naturally
            # This handles the case where workers complete but stats aren't immediately updated
            if self.enrichment_pipeline:
                all_workers_done = all(
                    worker.done() for worker in self.enrichment_pipeline.enrichment_workers
                )
                storage_worker_done = (
                    not self.enrichment_pipeline.storage_worker
                    or self.enrichment_pipeline.storage_worker.done()
                )

                if all_workers_done and storage_worker_done:
                    logger.info(
                        f"All enrichment workers completed naturally. Final stats: completed={completed_count}, errors={error_count}"
                    )
                    break

            # Check for stalled progress
            if completed_count == last_completed_count:
                stall_counter += 1
                if stall_counter >= max_stall_checks:
                    logger.warning(
                        f"Enrichment appears stalled after {max_stall_checks} checks. Proceeding..."
                    )
                    break
            else:
                stall_counter = 0
                last_completed_count = completed_count

            # Send WebSocket update every 10 seconds
            current_time = time.time()
            if current_time - last_update_time >= 10:
                await self._update_heartbeat(
                    job_id, phase="enriching", documents_enriched=completed_documents
                )

                # Calculate enrichment progress based on actual documents to be enriched
                # Get actual count from database for more accurate progress
                with self.db_manager.session_scope() as session:
                    total_documents_to_enrich = (
                        session.query(Document).filter(Document.crawl_job_id == job_id).count()
                    )

                enrichment_progress = round(
                    (
                        (completed_count / total_documents_to_enrich * 100)
                        if total_documents_to_enrich > 0
                        else 0
                    ),
                    1,
                )

                await notify_crawl_update(
                    job_id,
                    "running",
                    {
                        "crawl_phase": "enriching",
                        "enrichment_queue": enrichment_queue,
                        "documents_enriched": completed_documents,
                        "total_documents": total_documents_to_enrich,
                        "snippets_extracted": total_snippets,
                        "enrichment_progress": enrichment_progress,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                last_update_time = current_time

            # Wait before next check
            await asyncio.sleep(10)

    async def _update_heartbeat(
        self,
        job_id: str,
        phase: Optional[str] = None,
        documents_crawled: Optional[int] = None,
        documents_enriched: Optional[int] = None,
    ) -> None:
        """Update job heartbeat and progress.

        Args:
            job_id: Job ID
            phase: Current phase ('crawling', 'enriching', 'finalizing')
            documents_crawled: Number of documents crawled
            documents_enriched: Number of documents enriched
        """
        job_data = {}
        try:
            with self.db_manager.session_scope() as session:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job is not None:
                    # Refresh the object to ensure it's bound to current session
                    session.refresh(job)
                    job.last_heartbeat = datetime.utcnow()
                    if phase:
                        job.crawl_phase = phase
                        logger.debug(f"Job {job_id} phase updated to: {phase}")
                    if documents_crawled is not None:
                        job.documents_crawled = documents_crawled
                    if documents_enriched is not None:
                        job.documents_enriched = documents_enriched

                    # Prepare data for WebSocket update
                    job_data = {
                        "urls_crawled": job.processed_pages,
                        "total_pages": job.total_pages,
                        "snippets_extracted": job.snippets_extracted,
                        "crawl_phase": job.crawl_phase,
                        "documents_crawled": job.documents_crawled,
                        "documents_enriched": job.documents_enriched,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                session.commit()
        except Exception as e:
            logger.error(f"Error updating job {job_id} heartbeat: {e}")

        # Send WebSocket notification
        if job_data:
            await notify_crawl_update(job_id, "running", job_data)

    async def _heartbeat_task(self, job_id: str) -> None:
        """Background task to update heartbeat periodically.

        Args:
            job_id: Job ID
        """
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                with self.db_manager.session_scope() as session:
                    job = session.query(CrawlJob).filter_by(id=job_id).first()
                    if job is not None and job.status == "running":
                        await self._update_heartbeat(job_id)
                    else:
                        # Job no longer running, stop heartbeat
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")

    async def start_crawl(self, config: CrawlConfig, user_id: Optional[str] = None) -> str:
        """Start a new crawl job or reuse existing one for the same domain.

        Args:
            config: Crawl configuration
            user_id: User identifier

        Returns:
            Job ID
        """
        from .domain_utils import get_primary_domain

        # Extract primary domain from start URLs
        domain = get_primary_domain(config.start_urls)
        if not domain:
            raise ValueError("No valid domain found in start URLs")

        with self.db_manager.session_scope() as session:
            # Check for existing crawl job with same domain
            existing_job = session.query(CrawlJob).filter_by(domain=domain).first()

            if existing_job is not None:
                # Reuse existing job - update it with new configuration
                logger.info(f"Reusing existing crawl job for domain '{domain}': {existing_job.id}")

                # Update job configuration and reset status fields
                existing_job.name = config.name
                existing_job.start_urls = config.start_urls
                existing_job.max_depth = config.max_depth
                existing_job.domain_restrictions = config.domain_restrictions
                existing_job.status = "running"
                existing_job.started_at = datetime.utcnow()
                existing_job.created_by = user_id
                existing_job.last_heartbeat = datetime.utcnow()
                existing_job.crawl_phase = "crawling"
                existing_job.error_message = None
                existing_job.retry_count = 0
                # Reset completion times for re-crawl
                existing_job.completed_at = None
                existing_job.crawl_completed_at = None
                existing_job.enrichment_started_at = None
                existing_job.enrichment_completed_at = None
                existing_job.documents_crawled = 0
                existing_job.documents_enriched = 0
                existing_job.config = {
                    "include_patterns": config.include_patterns,
                    "exclude_patterns": config.exclude_patterns,
                    "max_pages": config.max_pages,
                    "metadata": config.metadata,
                }

                session.commit()
                job_id = str(existing_job.id)
            else:
                # Create new job
                job = CrawlJob(
                    name=config.name,
                    domain=domain,
                    start_urls=config.start_urls,
                    max_depth=config.max_depth,
                    domain_restrictions=config.domain_restrictions,
                    status="running",
                    started_at=datetime.utcnow(),
                    created_by=user_id,
                    last_heartbeat=datetime.utcnow(),
                    crawl_phase="crawling",
                    config={
                        "include_patterns": config.include_patterns,
                        "exclude_patterns": config.exclude_patterns,
                        "max_pages": config.max_pages,
                        "metadata": config.metadata,
                    },
                )
                session.add(job)
                session.commit()
                job_id = str(job.id)

        # Start async crawl
        asyncio.create_task(self._crawl_job(job_id, config, use_pipeline=True))

        return job_id

    async def _crawl_job(self, job_id: str, config: CrawlConfig, use_pipeline: bool = True) -> None:
        """Execute the crawl job asynchronously."""
        heartbeat_task = None
        try:
            # Start enrichment pipeline once at the beginning if using pipeline
            if use_pipeline:
                await self._ensure_enrichment_pipeline()
                if self.enrichment_pipeline:
                    logger.info("Enrichment pipeline ready for crawl job")
                else:
                    logger.warning(
                        "Failed to start enrichment pipeline, continuing without enrichment"
                    )
                    use_pipeline = False

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_task(job_id))

            # Send initial notification
            await notify_crawl_update(
                job_id,
                "running",
                {
                    "urls_crawled": 0,
                    "total_pages": 1,  # Will be updated as we discover more pages
                    "snippets_extracted": 0,
                    "crawl_phase": "crawling",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            visited_urls: Set[str] = set()
            processed_count = 0
            total_snippets = 0
            last_ws_update_count = 0  # Track when we last sent a WebSocket update

            # For deep crawls, we let Crawl4AI handle the crawling
            # For single page crawls, we process URLs one by one
            if config.max_depth > 0:
                # Deep crawl - process all start URLs with BFSDeepCrawlStrategy
                for start_url in config.start_urls:
                    if processed_count >= config.max_pages:
                        break

                    with self.db_manager.session_scope() as session:
                        job = session.query(CrawlJob).filter_by(id=job_id).first()
                        if job is not None:
                            if job.config is None:
                                job.config = {}
                            job.config["crawl_start_time"] = datetime.now(timezone.utc).isoformat()
                            session.commit()

                    try:
                        # Crawl4AI will handle the deep crawling
                        logger.info(f"🌐 Sending deep crawl request to Crawl4AI...")
                        results = await self._crawl_page(start_url, job_id, 0, config.max_depth)

                        if results:
                            logger.info(f"✅ Deep crawl completed! Received {len(results)} pages")

                            # Update crawl completion time and phase
                            await self._update_heartbeat(
                                job_id, phase="enriching", documents_crawled=len(results)
                            )
                            with self.db_manager.session_scope() as session:
                                job = session.query(CrawlJob).filter_by(id=job_id).first()
                                if job is not None:
                                    job.crawl_completed_at = datetime.utcnow()
                                    job.enrichment_started_at = datetime.utcnow()
                                    session.commit()

                            # Log crawl statistics
                            crawl_time = None
                            with self.db_manager.session_scope() as session:
                                job = session.query(CrawlJob).filter_by(id=job_id).first()
                                if (
                                    job is not None
                                    and job.config
                                    and "crawl_start_time" in job.config
                                ):
                                    start_time = datetime.fromisoformat(
                                        str(job.config["crawl_start_time"])
                                    )
                                    crawl_time = (datetime.utcnow() - start_time).total_seconds()
                                    logger.info(f"⏱️  Actual crawl time: {crawl_time:.1f} seconds")

                            # Process results concurrently in batches
                            batch_size = 10  # Process 10 documents at a time
                            for i in range(0, len(results), batch_size):
                                batch = results[i : i + batch_size]
                                batch_tasks = []

                                for idx, result in enumerate(batch):
                                    # Mark URL as visited regardless of success/failure
                                    result_url = getattr(result, "url", start_url)
                                    visited_urls.add(result_url)

                                    # Count all pages as processed (both successful and failed)
                                    processed_count += 1
                                    if processed_count > config.max_pages:
                                        break

                                    if not hasattr(result, "error") or not result.error:
                                        logger.debug(
                                            f"Processing result {i+idx+1}/{len(results)}: {result_url}"
                                        )

                                        # Get the actual depth of this page from metadata
                                        page_depth = result.metadata.get("depth", 0)

                                        # Create task for concurrent processing
                                        task = self._process_single_result(
                                            result,
                                            job_id,
                                            page_depth,
                                            i + idx,
                                            use_pipeline,
                                            result_url,
                                        )
                                        batch_tasks.append(task)

                                # Wait for batch to complete
                                if batch_tasks:
                                    batch_results = await asyncio.gather(
                                        *batch_tasks, return_exceptions=True
                                    )

                                    # Process results
                                    for result in batch_results:
                                        if isinstance(result, Exception):
                                            logger.error(f"Error processing document: {result}")
                                        else:
                                            # Type assertion - we know result is the expected tuple
                                            doc_id, snippet_count, links = result  # type: ignore[misc]
                                            total_snippets += int(snippet_count)  # type: ignore[has-type]

                                            # Track successful documents
                                            with self.db_manager.session_scope() as session:
                                                job = (
                                                    session.query(CrawlJob)
                                                    .filter_by(id=job_id)
                                                    .first()
                                                )
                                                if job is not None:
                                                    job.documents_crawled = (
                                                        job.documents_crawled or 0
                                                    ) + 1

                                # Update enrichment progress after each batch
                                await self._update_heartbeat(
                                    job_id, documents_enriched=processed_count
                                )

                            # Update job progress after processing results
                            with self.db_manager.session_scope() as session:
                                job = session.query(CrawlJob).filter_by(id=job_id).first()
                                if job is not None:
                                    job.processed_pages = processed_count
                                    job.total_pages = len(visited_urls)
                                    job.snippets_extracted = total_snippets

                            # Send WebSocket notification only every WS_UPDATE_INTERVAL pages
                            if processed_count - last_ws_update_count >= WS_UPDATE_INTERVAL:
                                await notify_crawl_update(
                                    job_id,
                                    "running",
                                    {
                                        "processed_pages": processed_count,
                                        "total_pages": len(visited_urls),
                                        "snippets_extracted": total_snippets,
                                        "current_url": start_url,  # Current URL being processed
                                        "crawl_phase": job.crawl_phase if job else "crawling",
                                        "timestamp": datetime.utcnow().isoformat(),
                                        # Calculate progress percentages
                                        "crawl_progress": min(
                                            100,
                                            round(
                                                (processed_count / len(visited_urls) * 100)
                                                if len(visited_urls) > 0
                                                else 0
                                            ),
                                        ),
                                    },
                                )
                                last_ws_update_count = processed_count

                    except Exception as e:
                        logger.error(f"Error crawling {start_url}: {e}")
                        continue

            else:
                # Single page crawls - process each URL individually
                url_queue: List[Tuple[str, int]] = [(url, 0) for url in config.start_urls]

                while url_queue and processed_count < config.max_pages:
                    current_url, depth = url_queue.pop(0)

                    if current_url in visited_urls:
                        continue

                    visited_urls.add(current_url)
                    logger.info(f"Crawling single page: {current_url}")

                    try:
                        results = await self._crawl_page(current_url, job_id, depth, 0)
                        
                        logger.debug(f"Single page crawl returned {len(results) if results else 0} results")

                        if results:
                            for result in results:
                                if not hasattr(result, "error") or not result.error:
                                    processed_count += 1

                                    # Store document and extract code
                                    if use_pipeline:
                                        doc_id, snippet_count = await self._process_result_pipeline(
                                            result, job_id, depth
                                        )
                                    else:
                                        doc_id, snippet_count = await self._process_result(
                                            result, job_id, depth
                                        )
                                    total_snippets += snippet_count
                        else:
                            logger.warning(f"No results returned for single page: {current_url}")

                        # Update job progress
                        with self.db_manager.session_scope() as session:
                            job = session.query(CrawlJob).filter_by(id=job_id).first()
                            if job is not None:
                                job.processed_pages = processed_count
                                job.total_pages = len(visited_urls)
                                job.snippets_extracted = total_snippets
                                job.documents_crawled = (
                                    processed_count  # For single page crawls, processed = documents
                                )

                        # Send WebSocket notification only every WS_UPDATE_INTERVAL pages
                        if processed_count - last_ws_update_count >= WS_UPDATE_INTERVAL:
                            await notify_crawl_update(
                                job_id,
                                "running",
                                {
                                    "processed_pages": processed_count,
                                    "total_pages": len(visited_urls),
                                    "snippets_extracted": total_snippets,
                                    "current_url": current_url,
                                    "crawl_phase": "crawling",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    # Calculate progress percentages
                                    "crawl_progress": min(
                                        100,
                                        round(
                                            (processed_count / len(visited_urls) * 100)
                                            if len(visited_urls) > 0
                                            else 0
                                        ),
                                    ),
                                },
                            )
                            last_ws_update_count = processed_count

                    except Exception as e:
                        logger.error(f"Error crawling {current_url}: {e}")
                        continue

            # After all crawling is done, wait for pipeline to process all tasks
            if use_pipeline and self.enrichment_pipeline:
                logger.info(
                    "Crawl phase complete. Waiting for enrichment pipeline to process all tasks..."
                )

            # Monitor pipeline progress
            last_enrichment_update = 0
            check_count = 0
            while True:
                # Yield to allow other tasks to run
                await asyncio.sleep(0)

                stats = self.enrichment_pipeline.get_stats()
                enrichment_queue_size = stats.get("enrichment_queue_size", 0)
                storage_queue_size = stats.get("storage_queue_size", 0)
                active_tasks = stats.get("active_tasks", 0)
                completed = stats.get("completed_count", 0)
                completed_documents = stats.get("completed_documents", 0)
                errors = stats.get("error_count", 0)

                check_count += 1
                if check_count % 5 == 1:  # Log every 5 checks (10 seconds)
                    logger.info(
                        f"Pipeline status: Enrichment queue: {enrichment_queue_size}, "
                        f"Storage queue: {storage_queue_size}, Active: {active_tasks}, "
                        f"Completed: {completed}, Errors: {errors}"
                    )

                # Check if all queues are empty and no active tasks
                if enrichment_queue_size == 0 and storage_queue_size == 0 and active_tasks == 0:
                    # Double check - sometimes there's a race condition
                    await asyncio.sleep(1)
                    final_stats = self.enrichment_pipeline.get_stats()
                    if (
                        final_stats.get("enrichment_queue_size", 0) == 0
                        and final_stats.get("storage_queue_size", 0) == 0
                        and final_stats.get("active_tasks", 0) == 0
                    ):
                        logger.info(
                            f"All enrichment tasks completed! Total processed: {completed}"
                        )
                        break

                # Update job progress
                await self._update_heartbeat(job_id, documents_enriched=completed_documents)

                # Send WebSocket update periodically
                if completed > last_enrichment_update:
                    await notify_crawl_update(
                        job_id,
                        "running",
                        {
                            "processed_pages": processed_count,
                            "total_pages": len(visited_urls),
                            "snippets_extracted": total_snippets,
                            "documents_enriched": completed_documents,
                            "enrichment_queue_size": enrichment_queue_size,
                            "crawl_phase": "enriching",
                            "timestamp": datetime.utcnow().isoformat(),
                            # Calculate progress percentages
                            "crawl_progress": min(
                                100,
                                round(
                                    (processed_count / len(visited_urls) * 100)
                                    if len(visited_urls) > 0
                                    else 0
                                ),
                            ),
                            "enrichment_progress": min(
                                100,
                                round(
                                    (completed_documents / processed_count * 100)
                                    if processed_count > 0
                                    else 0
                                ),
                            ),
                        },
                    )
                    last_enrichment_update = completed_documents

                # Wait before checking again
                await asyncio.sleep(2)

            # Send a final crawl update if we haven't sent one recently
            if processed_count > last_ws_update_count:
                await notify_crawl_update(
                    job_id,
                    "running",
                    {
                        "processed_pages": processed_count,
                        "total_pages": len(visited_urls),
                        "snippets_extracted": total_snippets,
                        "crawl_phase": "enriching" if use_pipeline else "finalizing",
                        "timestamp": datetime.utcnow().isoformat(),
                        # Calculate progress percentages
                        "crawl_progress": min(
                            100,
                            round(
                                (processed_count / len(visited_urls) * 100)
                                if len(visited_urls) > 0
                                else 0
                            ),
                        ),
                    },
                )

            # Update phase based on whether we're using pipeline
            if use_pipeline:
                await self._update_heartbeat(job_id, phase="enriching")

                # Wait for enrichment to complete
                logger.info("Crawl phase completed, waiting for enrichment to finish...")
                await self._wait_for_enrichment_completion(job_id, total_snippets)

                # Stop pipeline after enrichment is done
                if self.enrichment_pipeline:
                    logger.info("All enrichment completed, stopping pipeline...")

                    # Get final stats before stopping
                    stats = self.enrichment_pipeline.get_stats()
                    logger.info(f"Pipeline final stats before stop: {stats}")

                    try:
                        await self.enrichment_pipeline.stop()
                    except Exception as e:
                        logger.error(f"Error stopping enrichment pipeline: {e}")

                    # Update job with final counts
                    with self.db_manager.session_scope() as session:
                        job = session.query(CrawlJob).filter_by(id=job_id).first()
                        if job is not None:
                            job.documents_enriched = stats.get("completed_documents", 0)
                            job.status = "completed"
                            job.completed_at = datetime.utcnow()
                            job.enrichment_completed_at = datetime.utcnow()
                            job.crawl_phase = None
                            # Also update the final snippet count
                            job.snippets_extracted = total_snippets
                            job.processed_pages = processed_count
                            job.total_pages = len(visited_urls)
                            session.commit()
                            logger.info(
                                f"Job {job_id} marked as completed with {stats.get('completed_documents', 0)} documents enriched"
                            )

                    # Send completion notification
                    await notify_crawl_update(
                        job_id,
                        "completed",
                        {
                            "processed_pages": processed_count,
                            "total_pages": len(visited_urls),
                            "snippets_extracted": total_snippets,
                            "documents_enriched": stats.get("completed_documents", 0),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
            else:
                await self._update_heartbeat(job_id, phase="finalizing")

            # If not using pipeline, mark job as completed now
            if not use_pipeline:
                with self.db_manager.session_scope() as session:
                    job = session.query(CrawlJob).filter_by(id=job_id).first()
                    if job is not None:
                        job.status = "completed"
                        job.completed_at = datetime.utcnow()
                        job.crawl_completed_at = datetime.utcnow()
                        job.enrichment_completed_at = datetime.utcnow()
                        job.total_pages = len(visited_urls)
                        job.processed_pages = processed_count
                        job.snippets_extracted = total_snippets
                        job.crawl_phase = None  # Clear phase when completed

                # Send completion notification
                await notify_crawl_update(
                    job_id,
                    "completed",
                    {
                        "processed_pages": processed_count,
                        "total_pages": len(visited_urls),
                        "snippets_extracted": total_snippets,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            with self.db_manager.session_scope() as session:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job is not None:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    # Track which phase failed
                    if job.crawl_phase:
                        job.error_message = f"Failed during {job.crawl_phase} phase: {str(e)}"

            # Send failure notification
            await notify_crawl_update(
                job_id, "failed", {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
            )
        finally:
            # Clean up heartbeat task
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            # Note: Pipeline shutdown has been moved to after enrichment completion
            # This ensures all enrichment tasks are processed before stopping

    async def _crawl_page(
        self, url: str, job_id: str, depth: int, max_depth: int = 0
    ) -> Optional[List[CrawlResult]]:
        """Crawl a page (or site) using Crawl4AI library.

        Args:
            url: URL to crawl
            job_id: Job ID for tracking
            depth: Current crawl depth
            max_depth: Maximum depth for deep crawling (0 for single page)

        Returns:
            List of CrawlResult objects or None if failed
        """
        results = []

        # Get job configuration
        job_config = None
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None:
                job_config = {
                    "domain_restrictions": job.domain_restrictions,
                    "include_patterns": (
                        job.config.get("include_patterns", []) if job.config else []
                    ),
                    "exclude_patterns": (
                        job.config.get("exclude_patterns", []) if job.config else []
                    ),
                }

        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                if max_depth > 0:
                    # Deep crawling with BFSDeepCrawlStrategy
                    logger.info(f"Starting deep crawl from {url} with max_depth={max_depth}")

                    # Create filters based on job configuration
                    filters = []
                    if job_config and job_config["domain_restrictions"]:
                        filters.append(
                            DomainFilter(allowed_domains=job_config["domain_restrictions"])
                        )

                    if job_config and job_config["include_patterns"]:
                        # Add include pattern filters
                        filters.append(
                            URLPatternFilter(
                                patterns=job_config["include_patterns"],
                                use_glob=True,
                                reverse=False,  # Match patterns
                            )
                        )

                    if job_config and job_config["exclude_patterns"]:
                        # Add exclude pattern filters
                        filters.append(
                            URLPatternFilter(
                                patterns=job_config["exclude_patterns"],
                                use_glob=True,
                                reverse=True,  # Exclude patterns
                            )
                        )

                    # Always create a FilterChain, even if empty
                    filter_chain = FilterChain(filters)

                    # Configure BFS deep crawling strategy
                    strategy = BFSDeepCrawlStrategy(
                        max_depth=max_depth, include_external=False, filter_chain=filter_chain
                    )

                    # Configure Rate Limiter
                    rate_limiter = RateLimiter(base_delay=(1.0, 2.0), max_delay=30.0, max_retries=4)

                    # Configure Dispatcher
                    dispatcher = SemaphoreDispatcher(
                        max_session_permit=20,
                        rate_limiter=rate_limiter,
                    )

                    # Configure crawler
                    config = CrawlerRunConfig(
                        deep_crawl_strategy=strategy,
                        excluded_tags=["nav", "footer", "header", "aside", "button", "form"],
                        markdown_generator=DefaultMarkdownGenerator(
                            options={
                                "ignore_links": True,
                                "escape_html": False,
                                "ignore_images": True,
                            },
                            content_source="raw_html",
                        ),
                        wait_until="domcontentloaded",
                        page_timeout=30000,
                        exclude_external_links=True,
                        cache_mode=CacheMode.BYPASS,
                        stream=True,
                    )

                    # Track crawled pages
                    crawled_count = 0
                    total_snippets = 0
                    last_ws_update_count = 0

                    # Crawl with streaming - arun returns an async generator when stream=True
                    crawl_results = await crawler.arun(url, config=config, dispatcher=dispatcher)
                    async for result in crawl_results:
                        crawled_count += 1

                        if result.success:
                            # Get depth from result metadata if available, otherwise use 0
                            page_depth = 0
                            if (
                                hasattr(result, "metadata")
                                and result.metadata
                                and "depth" in result.metadata
                            ):
                                page_depth = result.metadata["depth"]

                            # Create CrawlResult from the library result
                            crawl_result = self._convert_library_result(result, page_depth)
                            if crawl_result:
                                results.append(crawl_result)
                                total_snippets += len(crawl_result.code_blocks)
                                logger.info(
                                    f"Crawled page {crawled_count}: {result.url} (depth: {page_depth})"
                                )
                        else:
                            logger.warning(f"Failed to crawl {result.url}: {result.error_message}")
                            # Record the failed page for potential retry
                            await self._record_failed_page(job_id, result.url, result.error_message)

                        # Update job progress and send WebSocket updates
                        if crawled_count % 3 == 0 or crawled_count == 1:
                            with self.db_manager.session_scope() as session:
                                job = session.query(CrawlJob).filter_by(id=job_id).first()
                                if job is not None:
                                    job.processed_pages = crawled_count
                                    job.total_pages = crawled_count
                                    job.snippets_extracted = total_snippets
                                    job.crawl_phase = "crawling"
                                    job.last_heartbeat = datetime.utcnow()

                            # Send WebSocket notification
                            await notify_crawl_update(
                                job_id,
                                "running",
                                {
                                    "urls_crawled": crawled_count,
                                    "total_pages": crawled_count,
                                    "snippets_extracted": total_snippets,
                                    "current_url": result.url if result else None,
                                    "crawl_phase": "crawling",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                            last_ws_update_count = crawled_count

                else:
                    # Single page crawl
                    logger.info(f"Crawling single page: {url}")

                    # Configure for single page
                    config = CrawlerRunConfig(
                        excluded_tags=["nav", "footer", "header", "aside", "button", "form"],
                        markdown_generator=DefaultMarkdownGenerator(
                            options={
                                "ignore_links": True,
                                "escape_html": False,
                                "ignore_images": True,
                            },
                            content_source="raw_html",
                        ),
                        wait_until="domcontentloaded",
                        page_timeout=60000,
                        cache_mode=CacheMode.BYPASS,
                    )

                    # Crawl single page - arun returns a container for single page
                    result_container = await crawler.arun(url, config=config)
                    # For single page, we get a container, not an iterator
                    if hasattr(result_container, "results"):
                        for result in result_container.results:
                            if result.success:
                                crawl_result = self._convert_library_result(result, depth)
                                if crawl_result:
                                    results.append(crawl_result)
                                    logger.info(f"Successfully crawled: {url}")
                            else:
                                logger.error(f"Failed to crawl {url}: {result.error_message}")
                                # Record the failed page for potential retry
                                await self._record_failed_page(job_id, url, result.error_message)
                    else:
                        # Handle single result
                        result = result_container
                        if result.success:
                            crawl_result = self._convert_library_result(result, depth)
                            if crawl_result:
                                results.append(crawl_result)
                                logger.info(f"Successfully crawled: {url}")
                        else:
                            logger.error(f"Failed to crawl {url}: {result.error_message}")
                            # Record the failed page for potential retry
                            await self._record_failed_page(job_id, url, result.error_message)

                return results if results else None

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    def _convert_library_result(self, result: Any, depth: int) -> Optional[CrawlResult]:
        """Convert Crawl4AI library result to our CrawlResult format."""
        try:
            logger.debug(f"Crawl4AI result attributes: {dir(result)}")

            metadata = {
                "depth": depth,
                "status_code": 200 if result.success else 0,
                "success": result.success,
            }

            logger.info(f"=== Processing Crawl4AI result for URL: {result.url} ===")

            # Extract title
            title = ""
            if hasattr(result, "metadata") and result.metadata:
                title = result.metadata.get("title", "")

            # Extract links
            links = []
            if hasattr(result, "links") and result.links:
                for link in result.links.get("internal", []):
                    links.append(
                        {
                            "url": link.get("href", ""),
                            "text": link.get("text", ""),
                            "title": link.get("title", ""),
                        }
                    )

            # Extract markdown content
            markdown_content = None
            if hasattr(result, "markdown") and result.markdown:
                if isinstance(result.markdown, dict):
                    markdown_content = result.markdown.get("raw_markdown", "")
                    if not markdown_content:
                        markdown_content = result.markdown.get("fit_markdown", "")
                elif isinstance(result.markdown, str):
                    markdown_content = result.markdown
                else:
                    markdown_content = ""

                if markdown_content:
                    logger.info(f"Extracted markdown content length: {len(markdown_content)}")
                else:
                    logger.warning("No markdown content found in result")
            else:
                logger.warning("No markdown attribute in Crawl4AI result")
                return None

            # Extract code blocks from markdown content
            logger.info("Extracting code blocks from markdown content...")

            code_blocks = self.code_extractor.extract_from_content(
                markdown_content, result.url, "markdown", markdown_content
            )
            logger.info(f"Extracted {len(code_blocks)} code blocks")

            # Log details of each code block
            for i, block in enumerate(code_blocks):
                logger.debug(
                    f"Block {i+1}: Language={block.language}, Lines={block.lines_of_code}, Hash={block.hash[:8]}..."
                )
                logger.debug(f"  Title: {block.title}")
                logger.debug(f"  First line: {block.content.split(chr(10))[0][:80]}...")

            # Calculate content hash based on markdown content
            content_hash = hashlib.md5((markdown_content or "").encode("utf-8")).hexdigest()

            # Add Crawl4AI metadata if available
            if hasattr(result, "metadata") and result.metadata:
                metadata["crawl4ai_metadata"] = result.metadata

            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content or "",  # Use markdown content, ensure not None
                content_hash=content_hash,
                links=links,
                code_blocks=code_blocks,
                metadata=metadata,
                markdown_content=markdown_content,
            )

        except Exception as e:
            logger.error(f"Error converting library result: {e}")
            return None

    def _has_crawl_content(self, data: Dict[str, Any]) -> bool:
        """Check if the data contains crawlable content."""
        # Check for markdown content
        if "markdown" in data:
            return True
        return False

    def _create_crawl_result(self, data: Dict[str, Any], url: str, depth: int) -> CrawlResult:
        """Create a CrawlResult from the response data."""
        # Use the URL from response if available
        result_url = data.get("url", url)

        # Extract markdown content
        content = ""
        title = ""

        # Get markdown content
        if "markdown" in data:
            if isinstance(data["markdown"], dict):
                # Use raw_markdown for the most complete content
                content = data["markdown"].get("raw_markdown", "")
                if not content:
                    # Fallback to fit_markdown if raw_markdown is empty
                    content = data["markdown"].get("fit_markdown", "")
            elif isinstance(data["markdown"], str):
                content = data["markdown"]

        # Extract title from metadata
        if "metadata" in data:
            title = data["metadata"].get("title", "")

        # Fallback title extraction from content if needed
        if not title and content:
            # Try to extract from first line if it's a markdown header
            lines = content.split("\n", 2)
            if lines and lines[0].startswith("#"):
                title = lines[0].lstrip("#").strip()

        # Extract links from response
        links = []
        if "links" in data and isinstance(data["links"], dict):
            # Add internal links
            for link in data["links"].get("internal", []):
                links.append(
                    {
                        "url": link.get("href", ""),
                        "text": link.get("text", ""),
                        "title": link.get("title", ""),
                    }
                )
            # Add external links if not excluded
            if not getattr(self.settings.crawling, "exclude_external_links", True):
                for link in data["links"].get("external", []):
                    links.append(
                        {
                            "url": link.get("href", ""),
                            "text": link.get("text", ""),
                            "title": link.get("title", ""),
                        }
                    )

        # Extract code blocks from content
        code_blocks = self.code_extractor.extract_from_content(
            content, result_url, "markdown", content
        )

        # Calculate content hash
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        # Extract markdown content for context (already extracted above as 'content' variable)
        markdown_content = content if content else None

        return CrawlResult(
            url=result_url,
            title=title or data.get("metadata", {}).get("title", ""),
            content=content,
            content_hash=content_hash,
            links=links,
            code_blocks=code_blocks,
            metadata={
                "depth": depth,
                "crawl4ai_metadata": data.get("metadata", {}),
                "status_code": data.get("status_code", 200),
                "success": data.get("success", True),
            },
            markdown_content=markdown_content,
        )

    async def _process_result_pipeline(
        self, result: CrawlResult, job_id: str, depth: int
    ) -> Tuple[int, int]:
        """Process crawl result using the enrichment pipeline (non-blocking).

        Args:
            result: Crawl result to process
            job_id: Job ID
            depth: Crawl depth

        Returns:
            Tuple of (document_id, code_blocks_submitted)
        """
        from ..database.models import CodeSnippet

        with self.db_manager.session_scope() as session:
            # Check if document already exists
            existing_doc = session.query(Document).filter_by(url=result.url).first()

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content hasn't changed
                return int(existing_doc.id), 0

            # Create or update document
            if existing_doc is not None:
                # Delete old code snippets before updating document
                session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()

                doc = existing_doc
                doc.title = result.title
                doc.markdown_content = result.markdown_content
                doc.content_hash = result.content_hash
                doc.crawl_job_id = job_id
                doc.last_crawled = datetime.utcnow()
            else:
                doc = Document(
                    url=result.url,
                    title=result.title,
                    markdown_content=result.markdown_content,
                    content_hash=result.content_hash,
                    crawl_job_id=job_id,
                    crawl_depth=depth,
                    metadata=result.metadata,
                )
                session.add(doc)

            session.flush()  # Get doc.id
            doc.enrichment_status = "processing"
            session.commit()

            doc_id = int(doc.id)

            # Check if we need to auto-detect the name
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None and job.name.startswith("[Auto-detecting"):
                # Extract name from the first page
                detected_name = await self._extract_site_name(result.title, result.url, result.metadata)
                if detected_name:
                    logger.info(f"Auto-detected site name: {detected_name}")
                    job.name = detected_name
                    session.commit()

        # Submit code blocks to pipeline (non-blocking)
        if self.enrichment_pipeline and result.code_blocks:
            logger.info(
                f"Submitting {len(result.code_blocks)} code blocks from {result.url} to enrichment pipeline"
            )
            # Create task to add document without blocking the crawl
            task = asyncio.create_task(
                self._submit_to_enrichment_pipeline(
                    document_id=doc_id,
                    document_url=result.url,
                    job_id=job_id,
                    code_blocks=result.code_blocks,
                )
            )

            # Add error handler to log any issues
            def log_error(t: asyncio.Task[None]) -> None:
                if t.exception():
                    logger.error(f"Failed to submit enrichment task: {t.exception()}")

            task.add_done_callback(log_error)
            return doc_id, len(result.code_blocks)
        elif result.code_blocks:
            logger.warning(
                f"No enrichment pipeline available to process {len(result.code_blocks)} code blocks from {result.url}"
            )
            return doc_id, len(result.code_blocks)

        return doc_id, 0

    async def _process_single_result(
        self,
        result: CrawlResult,
        job_id: str,
        depth: int,
        idx: int,
        use_pipeline: bool,
        result_url: str,
    ) -> Tuple[int, int, List]:
        """Process a single crawl result asynchronously.

        Returns:
            Tuple of (document_id, snippet_count, links)
        """
        doc_id = 0
        snippet_count = 0
        links = []

        try:
            # Store document and extract code
            if use_pipeline:
                doc_id, snippet_count = await self._process_result_pipeline(result, job_id, depth)
            else:
                doc_id, snippet_count = await self._process_result(result, job_id, depth)

            # Extract links
            for link_info in result.links:
                link_url = link_info.get("url", "")
                if link_url and not link_url.startswith(("#", "javascript:")):
                    if not link_url.startswith(("http://", "https://")):
                        link_url = urljoin(result_url, link_url)

                    links.append(
                        {
                            "source_url": result_url,
                            "target_url": link_url,
                            "link_text": link_info.get("text", ""),
                            "depth_level": depth + 1,
                        }
                    )

            # Store links in batch later to avoid blocking
            if links:
                asyncio.create_task(self._store_links_batch(job_id, links))

        except Exception as e:
            logger.error(f"Error processing result {idx}: {e}")
            raise

        return doc_id, snippet_count, links

    async def _store_links_batch(self, job_id: str, links: List[Dict]) -> None:
        """Store a batch of links asynchronously."""
        try:
            with self.db_manager.session_scope() as session:
                for link_data in links:
                    # Check if link already exists
                    existing_link = (
                        session.query(PageLink)
                        .filter_by(
                            source_url=link_data["source_url"],
                            target_url=link_data["target_url"],
                            crawl_job_id=job_id,
                        )
                        .first()
                    )

                    if not existing_link:
                        page_link = PageLink(
                            source_url=link_data["source_url"],
                            target_url=link_data["target_url"],
                            link_text=link_data["link_text"],
                            crawl_job_id=job_id,
                            depth_level=link_data["depth_level"],
                        )
                        session.add(page_link)

                session.commit()
        except Exception as e:
            logger.error(f"Failed to store links batch: {e}")

    async def _submit_to_enrichment_pipeline(
        self, document_id: int, document_url: str, job_id: str, code_blocks: List
    ) -> None:
        """Submit document to enrichment pipeline with error handling."""
        try:
            logger.info(
                f"Actually submitting {len(code_blocks)} blocks to pipeline for doc {document_id}"
            )
            if self.enrichment_pipeline:
                await self.enrichment_pipeline.add_document(
                    document_id=document_id,
                    document_url=document_url,
                    job_id=job_id,
                    code_blocks=code_blocks,
                )
                logger.info(
                    f"Successfully submitted {len(code_blocks)} blocks for doc {document_id}"
                )
        except Exception as e:
            logger.error(f"Failed to submit document {document_id} to enrichment pipeline: {e}")

    async def _process_result(
        self, result: CrawlResult, job_id: str, depth: int
    ) -> Tuple[int, int]:
        """Process crawl result and store in database.

        Args:
            result: Crawl result to process
            job_id: Job ID
            depth: Crawl depth

        Returns:
            Tuple of (document_id, snippet_count)
        """
        snippet_count = 0
        from ..database.models import CodeSnippet

        with self.db_manager.session_scope() as session:
            # Check if document already exists
            existing_doc = session.query(Document).filter_by(url=result.url).first()

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content hasn't changed
                return int(existing_doc.id), 0

            # Create or update document
            if existing_doc is not None:
                # Delete old code snippets before updating document
                session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()

                doc = existing_doc
                doc.title = result.title
                doc.markdown_content = result.markdown_content
                doc.content_hash = result.content_hash
                doc.crawl_job_id = job_id  # Update to current crawl job
                doc.last_crawled = datetime.utcnow()
            else:
                doc = Document(
                    url=result.url,
                    title=result.title,
                    markdown_content=result.markdown_content,
                    content_hash=result.content_hash,
                    crawl_job_id=job_id,
                    crawl_depth=depth,
                    metadata=result.metadata,
                )
                session.add(doc)

            session.flush()  # Get doc.id

            # Check if we need to auto-detect the name
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None and job.name.startswith("[Auto-detecting"):
                # Extract name from the first page
                detected_name = await self._extract_site_name(result.title, result.url, result.metadata)
                if detected_name:
                    logger.info(f"Auto-detected site name: {detected_name}")
                    job.name = detected_name
                    session.commit()

            # Mark document as being processed for enrichment
            doc.enrichment_status = "processing"
            session.commit()

            # Process code blocks
            # First collect all blocks for potential batch enrichment
            blocks_to_process = []
            for block in result.code_blocks:
                # Don't use tree-sitter - let LLM detect language with full context
                blocks_to_process.append(block)

            # Ensure LLM enricher is initialized
            await self._ensure_llm_enricher()

            # Enrich blocks with LLM if available
            enriched_blocks = []
            if self.metadata_enricher is not None and blocks_to_process:
                try:
                    logger.info(f"Enriching {len(blocks_to_process)} code blocks with LLM")
                    enriched_results = await self.metadata_enricher.enrich_batch(blocks_to_process)

                    # Map enriched results back
                    for enriched in enriched_results:
                        enriched_blocks.append(enriched)

                except Exception as e:
                    logger.error(f"LLM enrichment failed: {e}")
                    # Update document with enrichment error
                    doc.enrichment_error = str(e)
                    # Fall back to original blocks
                    enriched_blocks = [
                        self._create_mock_enriched(block) for block in blocks_to_process
                    ]
            else:
                # No enricher available, use original blocks
                enriched_blocks = [self._create_mock_enriched(block) for block in blocks_to_process]

            # Process enriched blocks
            for enriched_block in enriched_blocks:
                block = enriched_block.original

                # Always prefer LLM-detected language as it has full context
                final_language = enriched_block.detected_language or block.language
                if (
                    enriched_block.detected_language
                    and enriched_block.detected_language != block.language
                ):
                    logger.info(
                        f"Using LLM-detected language: {final_language} (was: {block.language})"
                    )

                # Extract functions and imports
                functions = []
                imports = []
                if self.settings.code_extraction.extract_functions:
                    functions = self.language_detector.extract_functions(
                        block.content, final_language
                    )
                if self.settings.code_extraction.extract_imports:
                    imports = self.language_detector.extract_imports(block.content, final_language)

                # Merge metadata
                merged_metadata = block.extraction_metadata.copy()
                if hasattr(enriched_block, "keywords") and enriched_block.keywords:
                    merged_metadata["keywords"] = enriched_block.keywords
                if hasattr(enriched_block, "frameworks") and enriched_block.frameworks:
                    merged_metadata["frameworks"] = enriched_block.frameworks

                if hasattr(enriched_block, "purpose"):
                    merged_metadata["purpose"] = enriched_block.purpose
                if hasattr(enriched_block, "dependencies") and enriched_block.dependencies:
                    merged_metadata["dependencies"] = enriched_block.dependencies
                merged_metadata["llm_enriched"] = hasattr(enriched_block, "enriched_title")

                # Debug log before storing
                logger.debug(
                    f"Storing code snippet - Language: {final_language}, Length: {len(block.content)}"
                )
                preview = block.content[:100].replace("\n", "\\n").replace("\t", "\\t")
                logger.debug(f"Code to store preview: {preview}...")

                # Extract section information from metadata
                section_title = None
                section_content = None
                if hasattr(block, "extraction_metadata"):
                    section_title = block.extraction_metadata.get("section_title")
                    section_content = block.extraction_metadata.get("full_section_content")

                # Create snippet with enhanced context
                snippet = CodeSnippet(
                    document_id=doc.id,
                    title=enriched_block.enriched_title or block.title,
                    description=enriched_block.enriched_description or block.description,
                    language=final_language,
                    code_content=block.content,
                    code_hash=block.hash,
                    line_start=block.line_start,
                    line_end=block.line_end,
                    context_before=block.context_before,  # Store full context
                    context_after=block.context_after,  # Store full context
                    section_title=section_title,
                    section_content=section_content,
                    functions=functions,
                    imports=imports,
                    source_url=result.url,
                    metadata=merged_metadata,
                )

                # Check for duplicate
                existing_snippet = (
                    session.query(CodeSnippet).filter_by(code_hash=block.hash).first()
                )

                if not existing_snippet:
                    session.add(snippet)
                    snippet_count += 1
                else:
                    # Update existing snippet with new metadata if enriched
                    if merged_metadata.get("llm_enriched"):
                        existing_snippet.title = snippet.title
                        existing_snippet.description = snippet.description
                        existing_snippet.language = snippet.language
                        existing_snippet.context_before = snippet.context_before
                        existing_snippet.context_after = snippet.context_after
                        existing_snippet.section_title = snippet.section_title
                        existing_snippet.section_content = snippet.section_content
                        existing_snippet.functions = snippet.functions
                        existing_snippet.imports = snippet.imports
                        existing_snippet.metadata = snippet.metadata
                        existing_snippet.updated_at = datetime.utcnow()
                        logger.debug(
                            f"Updated existing snippet with enriched metadata: {snippet.title}"
                        )

            # Mark document as enriched
            doc.enrichment_status = "completed" if not doc.enrichment_error else "failed"
            doc.enriched_at = datetime.utcnow()

            session.commit()
            return int(doc.id), snippet_count

    async def _extract_site_name(self, title: str, url: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Extract a clean site name from the page title using LLM.

        Args:
            title: Page title
            url: Page URL
            metadata: Optional metadata from crawl result

        Returns:
            Cleaned site name or None
        """
        if not title:
            return None

        # Initialize LLM client if needed
        await self._ensure_llm_enricher()
        
        if not self._llm_client:
            # Fallback to metadata title if LLM not available
            logger.warning("LLM not available for site name extraction, using metadata title fallback")
            if metadata and "title" in metadata:
                meta_title = metadata["title"]
                if meta_title and len(meta_title) <= 50:
                    return meta_title.strip()
            # Otherwise use the page title
            if len(title) > 50:
                return title[:50].rsplit(" ", 1)[0] + "..."
            return title.strip()
        
        try:
            # Create prompt for LLM
            prompt = f"""Extract the name of the documentation site, library, or framework from this page title.

Page Title: {title}
Page URL: {url}

Instructions:
- Return ONLY the clean name of the library, framework, or documentation site
- Remove any suffixes like "Documentation", "Docs", "Official Site", "Home", etc.
- Remove version numbers
- Use proper capitalization (e.g., "Next.js" not "nextjs")
- Keep the name concise (under 50 characters)
- If unsure, extract the most likely site/framework name from the title

Examples:
- "Getting Started | Next.js" → "Next.js"
- "React Documentation" → "React"
- "Django 5.0 Documentation" → "Django"
- "API Reference | Stripe Docs" → "Stripe"

Extracted name:"""
            
            # Call LLM with a short timeout since this is a simple task
            response = await self._llm_client.generate(
                prompt=prompt,
                max_tokens=50,  # We only need a short name
                temperature=0.1,  # Low temperature for consistency
            )
            
            # Clean up the response
            extracted_name = response.content.strip()
            # Remove quotes if present
            extracted_name = extracted_name.strip('"\'')
            
            # Validate the response
            if extracted_name and len(extracted_name) <= 50:
                logger.info(f"LLM extracted site name: {extracted_name} from title: {title}")
                return extracted_name
            else:
                logger.warning(f"LLM returned invalid name: {extracted_name}, using fallback")
                # Fallback to metadata title
                if metadata and "title" in metadata:
                    meta_title = metadata["title"]
                    if meta_title and len(meta_title) <= 50:
                        return meta_title.strip()
                # Otherwise use the page title
                if len(title) > 50:
                    return title[:50].rsplit(" ", 1)[0] + "..."
                return title.strip()
                
        except Exception as e:
            logger.error(f"Failed to extract site name using LLM: {e}")
            # Fallback to metadata title
            if metadata and "title" in metadata:
                meta_title = metadata["title"]
                if meta_title and len(meta_title) <= 50:
                    return meta_title.strip()
            # Otherwise use the page title
            if len(title) > 50:
                return title[:50].rsplit(" ", 1)[0] + "..."
            return title.strip()

    def _create_mock_enriched(self, block: Any) -> Any:
        """Create a mock enriched block for fallback."""
        from ..llm.enricher import EnrichedCodeBlock

        return EnrichedCodeBlock(original=block)

    async def _record_failed_page(self, job_id: str, url: str, error_message: str) -> None:
        """Record a page that failed to be crawled after all retries.

        Args:
            job_id: Crawl job ID
            url: URL that failed
            error_message: Error message from the crawler
        """
        try:
            with self.db_manager.session_scope() as session:
                # Handle both string and UUID for job_id
                from uuid import UUID

                if isinstance(job_id, str):
                    try:
                        job_uuid = UUID(job_id)
                    except ValueError:
                        logger.error(f"Invalid job ID format: {job_id}")
                        return
                else:
                    job_uuid = job_id

                # Check if this URL already exists for this job
                existing = (
                    session.query(FailedPage).filter_by(crawl_job_id=job_uuid, url=url).first()
                )

                if existing is None:
                    failed_page = FailedPage(
                        crawl_job_id=job_uuid,
                        url=url,
                        error_message=error_message,
                        failed_at=datetime.utcnow(),
                    )
                    session.add(failed_page)
                    session.commit()
                    logger.info(f"Recorded failed page: {url} for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to record failed page {url}: {e}")

    def _is_allowed_domain(self, url: str, domain_restrictions: List[str]) -> bool:
        """Check if URL matches domain restrictions."""
        if not domain_restrictions:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for restriction in domain_restrictions:
            restriction = restriction.lower()
            if restriction.startswith("*."):
                # Wildcard subdomain
                if domain.endswith(restriction[2:]) or domain == restriction[2:]:
                    return True
            elif domain == restriction or domain.endswith(f".{restriction}"):
                return True

        return False

    def _matches_patterns(
        self, url: str, include_patterns: List[str], exclude_patterns: List[str]
    ) -> bool:
        """Check if URL matches include/exclude patterns."""
        # Check exclude patterns first
        for pattern in exclude_patterns:
            if pattern in url:
                return False

        # If no include patterns, include everything not excluded
        if not include_patterns:
            return True

        # Check include patterns
        for pattern in include_patterns:
            if pattern in url:
                return True

        return False

    async def pause_job(self, job_id: str) -> bool:
        """Pause a running crawl job."""
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None and job.status == "running":
                job.status = "paused"
                return True
        return False

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused crawl job."""
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None and job.status == "paused":
                job.status = "running"
                # TODO: Implement actual resume logic
                return True
        return False

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a crawl job."""
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None and job.status in ["running", "paused"]:
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                return True
        return False

    async def resume_failed_job(self, job_id: str) -> bool:
        """Resume a failed or stalled job.

        Args:
            job_id: Job ID to resume

        Returns:
            True if job was resumed, False otherwise
        """
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()

            if not job:
                logger.error(f"Job {job_id} not found")
                return False

            if job.status not in ["failed", "running"]:
                logger.error(f"Job {job_id} is in {job.status} state, cannot resume")
                return False

            # Check if job is actually stalled (no heartbeat for 5+ minutes)
            if job.status == "running" and job.last_heartbeat:
                time_since_heartbeat = (datetime.utcnow() - job.last_heartbeat).total_seconds()
                if time_since_heartbeat < 300:  # 5 minutes
                    logger.info(
                        f"Job {job_id} is still active (heartbeat {time_since_heartbeat}s ago)"
                    )
                    return False

            # Determine where to resume from
            if not job.crawl_completed_at:
                # Crawl phase incomplete - restart from beginning
                logger.info(f"Resuming job {job_id} from crawl phase")
                job.status = "running"
                job.crawl_phase = "crawling"
                job.last_heartbeat = datetime.utcnow()
                job.error_message = None
                job.retry_count = (job.retry_count or 0) + 1
                session.commit()

                # Restart the crawl job
                config = self._reconstruct_config(job)
                asyncio.create_task(self._crawl_job(str(job.id), config))

            else:
                # Crawl completed but enrichment failed - resume enrichment
                logger.info(f"Resuming job {job_id} from enrichment phase")
                job.status = "running"
                job.crawl_phase = "enriching"
                job.last_heartbeat = datetime.utcnow()
                job.error_message = None
                job.retry_count = (job.retry_count or 0) + 1
                session.commit()

                # Resume enrichment for unenriched documents
                asyncio.create_task(self._resume_enrichment(str(job.id)))

            return True

    async def restart_enrichment(self, job_id: str) -> bool:
        """Restart only the enrichment process for a job.

        This resets enrichment status for all documents and restarts enrichment
        without re-crawling the pages.

        Args:
            job_id: Job ID to restart enrichment for

        Returns:
            True if enrichment restart was successful, False otherwise
        """
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()

            if not job:
                logger.error(f"Job {job_id} not found")
                return False

            if job.status not in ["completed", "failed"]:
                logger.error(
                    f"Job {job_id} is in {job.status} state, can only restart enrichment for completed or failed jobs"
                )
                return False

            # Reset enrichment status while preserving crawl data
            logger.info(f"Restarting enrichment for job {job_id}")

            # Reset job enrichment fields
            job.status = "running"
            job.crawl_phase = "enriching"
            job.last_heartbeat = datetime.utcnow()
            job.error_message = None
            job.enrichment_started_at = datetime.utcnow()
            job.enrichment_completed_at = None
            job.documents_enriched = 0
            job.retry_count = (job.retry_count or 0) + 1

            # Reset document enrichment status
            documents = session.query(Document).filter(Document.crawl_job_id == job_id).all()
            for doc in documents:
                doc.enrichment_status = "pending"

            session.commit()

            logger.info(f"Reset enrichment status for {len(documents)} documents")

        # Start enrichment process
        try:
            await self._resume_enrichment(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to restart enrichment for job {job_id}: {e}")
            with self.db_manager.session_scope() as session:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job is not None:
                    job.status = "failed"
                    job.error_message = f"Enrichment restart failed: {str(e)}"
                    job.completed_at = datetime.utcnow()
                    session.commit()
            return False

    def _reconstruct_config(self, job: CrawlJob) -> CrawlConfig:
        """Reconstruct CrawlConfig from job data."""
        return CrawlConfig(
            name=str(job.name),
            start_urls=list(job.start_urls),
            max_depth=int(job.max_depth),
            domain_restrictions=list(job.domain_restrictions) if job.domain_restrictions else [],
            include_patterns=job.config.get("include_patterns", []) if job.config else [],
            exclude_patterns=job.config.get("exclude_patterns", []) if job.config else [],
            max_pages=job.config.get("max_pages", 100) if job.config else 100,
            metadata=job.config.get("metadata", {}) if job.config else {},
        )

    async def _resume_enrichment(self, job_id: str) -> None:
        """Resume enrichment for unenriched documents.

        Args:
            job_id: Job ID
        """
        heartbeat_task = None
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_task(job_id))

            await self._update_heartbeat(job_id, phase="enriching")

            total_enriched = 0
            total_snippets = 0

            with self.db_manager.session_scope() as session:
                # Find all documents that need enrichment
                documents = (
                    session.query(Document)
                    .filter(
                        Document.crawl_job_id == job_id,
                        Document.enrichment_status.in_(["pending", "failed", "processing"]),
                    )
                    .all()
                )

                logger.info(f"Found {len(documents)} documents to enrich for job {job_id}")

                for idx, doc in enumerate(documents):
                    try:
                        # Re-process the document for enrichment
                        from ..parser.code_extractor import CodeBlock

                        # Extract code blocks from the document
                        code_blocks = self.code_extractor.extract_from_content(
                            doc.processed_content or doc.raw_content or "",
                            str(doc.url),
                            "markdown",
                            doc.processed_content or doc.raw_content or "",
                        )

                        if code_blocks:
                            # Create a proper CrawlResult for processing
                            crawl_result = CrawlResult(
                                url=str(doc.url),
                                title=str(doc.title) if doc.title else "",
                                content=str(doc.processed_content) if doc.processed_content else "",
                                content_hash=str(doc.content_hash),
                                links=[],
                                code_blocks=code_blocks,
                                metadata=dict(doc.metadata) if doc.metadata else {},
                                markdown_content=(
                                    str(doc.markdown_content) if doc.markdown_content else None
                                ),
                            )

                            # Process the document
                            doc_id, snippet_count = await self._process_result(
                                crawl_result, job_id, int(doc.crawl_depth)
                            )
                            total_snippets += snippet_count
                            total_enriched += 1

                            # Update progress
                            if idx % 5 == 0 or idx == 0:  # Update more frequently
                                await self._update_heartbeat(
                                    job_id, documents_enriched=total_enriched
                                )

                    except Exception as e:
                        logger.error(f"Error enriching document {doc.url}: {e}")
                        doc.enrichment_status = "failed"
                        doc.enrichment_error = str(e)
                        session.commit()

            # Complete the job
            await self._update_heartbeat(job_id, phase="finalizing")

            with self.db_manager.session_scope() as session:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job is not None:
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    job.enrichment_completed_at = datetime.utcnow()
                    job.documents_enriched = total_enriched
                    job.snippets_extracted = job.snippets_extracted + total_snippets
                    job.crawl_phase = None
                    session.commit()

            logger.info(f"Successfully resumed and completed job {job_id}")

        except Exception as e:
            logger.error(f"Resume enrichment failed for job {job_id}: {e}")
            with self.db_manager.session_scope() as session:
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job is not None:
                    job.status = "failed"
                    job.error_message = f"Resume enrichment failed: {str(e)}"
                    job.completed_at = datetime.utcnow()
                    session.commit()
        finally:
            # Clean up heartbeat task
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a crawl job."""
        with self.db_manager.session_scope() as session:
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job is not None:
                return job.to_dict()
        return None

    async def retry_failed_pages(self, job_id: str, user_id: Optional[str] = None) -> Optional[str]:
        """Create a new crawl job to retry failed pages from a previous job.

        Args:
            job_id: Original job ID with failed pages
            user_id: User identifier

        Returns:
            New job ID if created, None if no failed pages
        """
        with self.db_manager.session_scope() as session:
            # Get original job (handle both string and UUID)
            from uuid import UUID

            if isinstance(job_id, str):
                try:
                    job_uuid = UUID(job_id)
                except ValueError:
                    logger.error(f"Invalid job ID format: {job_id}")
                    return None
            else:
                job_uuid = job_id

            original_job = session.query(CrawlJob).filter_by(id=job_uuid).first()
            if not original_job:
                logger.error(f"Job {job_id} not found")
                return None

            # Get failed pages for this job
            failed_pages = session.query(FailedPage).filter_by(crawl_job_id=job_uuid).all()

            if not failed_pages:
                logger.info(f"No failed pages found for job {job_id}")
                return None

            # Extract failed URLs
            failed_urls = [str(fp.url) for fp in failed_pages]
            logger.info(f"Found {len(failed_urls)} failed pages to retry for job {job_id}")

            # Create new crawl config with failed URLs
            config = CrawlConfig(
                name=f"{str(original_job.name)} - Retry Failed Pages",
                start_urls=failed_urls,
                max_depth=0,  # Don't crawl deeper, just retry the specific pages
                domain_restrictions=(
                    list(original_job.domain_restrictions)
                    if original_job.domain_restrictions
                    else []
                ),
                max_pages=len(failed_urls),
                metadata={"retry_of_job": str(job_id), "original_job_name": original_job.name},
            )

            # Start new crawl job
            new_job_id = await self.start_crawl(config, user_id)
            logger.info(
                f"Created retry job {new_job_id} for {len(failed_urls)} failed pages from job {job_id}"
            )

            return new_job_id
