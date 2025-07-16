"""Asynchronous enrichment pipeline for continuous LLM processing."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass
from datetime import datetime
from collections import deque

from ..llm.enricher import MetadataEnricher, EnrichedCodeBlock
from ..llm.client import LLMClient
from ..parser.code_extractor import CodeBlock
from ..database.models import Document, CodeSnippet
from ..database.connection import DatabaseManager
from ..language.detector import LanguageDetector
from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentTask:
    """Represents a code block enrichment task."""
    document_id: int
    document_url: str
    job_id: str
    code_block: CodeBlock
    task_id: str


@dataclass
class EnrichmentResult:
    """Result of an enrichment task."""
    task: EnrichmentTask
    enriched_block: EnrichedCodeBlock
    success: bool
    error: Optional[str] = None


class EnrichmentPipeline:
    """Manages asynchronous enrichment of code blocks across multiple documents."""

    def __init__(self, 
                 llm_client: Optional[LLMClient] = None,
                 max_queue_size: int = 5000,
                 storage_batch_size: int = 10):
        """Initialize enrichment pipeline.
        
        Args:
            llm_client: LLM client instance
            max_queue_size: Maximum number of tasks in queue
            storage_batch_size: Number of results to batch for storage
        """
        self.settings = get_settings()
        self.llm_client = llm_client
        self.max_queue_size = max_queue_size
        self.storage_batch_size = storage_batch_size

        # Queues for pipeline stages
        self.enrichment_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.storage_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)

        # Components
        self.enricher: Optional[MetadataEnricher] = None
        self.db_manager = DatabaseManager()
        self.language_detector = LanguageDetector()

        # State tracking
        self.active_tasks: Dict[str, EnrichmentTask] = {}
        self.completed_count = 0  # Track completed snippets
        self.completed_documents: Set[int] = set()  # Track completed documents
        self.document_snippet_counts: Dict[int, int] = {}  # Track snippets per document
        self.document_completed_snippets: Dict[int, int] = {}  # Track completed snippets per document
        self.error_count = 0
        self.is_running = False

        # Workers
        self.enrichment_workers: List[asyncio.Task] = []
        self.storage_worker: Optional[asyncio.Task] = None
        self.status_monitor: Optional[asyncio.Task] = None

    async def start(self, num_enrichment_workers: Optional[int] = None) -> None:
        """Start the pipeline workers.
        
        Args:
            num_enrichment_workers: Number of enrichment workers (defaults to max_concurrent_requests)
        """
        if self.is_running:
            logger.warning("Pipeline already running")
            return

        self.is_running = True

        # Initialize components
        if not self.llm_client:
            self.llm_client = LLMClient(debug=self.settings.debug)

        # Test LLM connection
        logger.info("Testing LLM connection...")
        connection_status = await self.llm_client.test_connection()
        if connection_status.get("status") != "connected":
            logger.error(f"Failed to connect to LLM: {connection_status}")
            logger.error(f"LLM endpoint: {self.settings.llm.endpoint}")
            logger.error("Pipeline cannot start without LLM connection")
            self.is_running = False
            raise RuntimeError(f"LLM connection failed: {connection_status}")

        logger.info(f"LLM connection successful: {connection_status.get('model', 'unknown')}")

        self.enricher = MetadataEnricher(
            llm_client=self.llm_client,
            skip_small_snippets=True,
            min_lines=2  # Lower minimum to match code extractor and enrich small snippets
        )

        # Determine number of workers
        if num_enrichment_workers is None:
            num_enrichment_workers = self.settings.llm.max_concurrent_requests

        logger.info(f"Starting enrichment pipeline with {num_enrichment_workers} workers")

        # Start enrichment workers
        for i in range(num_enrichment_workers):
            worker = asyncio.create_task(self._enrichment_worker(f"enricher-{i}"))
            self.enrichment_workers.append(worker)
            logger.info(f"Created enrichment worker task: enricher-{i}")
            # Add done callback to log when worker exits
            def make_callback(worker_id: str) -> Callable[[asyncio.Task], None]:
                def callback(task: asyncio.Task) -> None:
                    if task.cancelled():
                        logger.warning(f"Worker {worker_id} was cancelled")
                    elif task.exception():
                        logger.error(f"Worker {worker_id} crashed: {task.exception()}")
                    else:
                        logger.info(f"Worker {worker_id} completed normally")
                return callback
            worker.add_done_callback(make_callback(f"enricher-{i}"))

        # Start storage worker
        self.storage_worker = asyncio.create_task(self._storage_worker())
        logger.debug("Created storage worker task")

        # Give workers a moment to start
        await asyncio.sleep(0.1)

        # Verify workers are actually running
        active_workers = sum(1 for w in self.enrichment_workers if not w.done())
        logger.info(f"Active enrichment workers after startup: {active_workers}/{len(self.enrichment_workers)}")

        # Start status monitor
        self.status_monitor = asyncio.create_task(self._status_monitor())

        # Verify workers are scheduled
        logger.info(f"Pipeline started: {len(self.enrichment_workers)} enrichment workers, 1 storage worker")

    async def stop(self) -> None:
        """Stop the pipeline gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping enrichment pipeline...")
        logger.info(f"Current worker status before stop: {[not w.done() for w in self.enrichment_workers]}")
        self.is_running = False

        # Wait for queues to empty with timeout
        try:
            # Give queues 5 seconds to finish processing
            await asyncio.wait_for(self.enrichment_queue.join(), timeout=5.0)
            await asyncio.wait_for(self.storage_queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for queues to empty - forcing shutdown")
            # Log queue states for debugging
            logger.info(f"Enrichment queue size at shutdown: {self.enrichment_queue.qsize()}")
            logger.info(f"Storage queue size at shutdown: {self.storage_queue.qsize()}")

        # Cancel workers
        for worker in self.enrichment_workers:
            worker.cancel()
        if self.storage_worker:
            self.storage_worker.cancel()
        if self.status_monitor:
            self.status_monitor.cancel()

        # Wait for workers to finish
        all_workers = self.enrichment_workers + [self.storage_worker, self.status_monitor]
        await asyncio.gather(*[w for w in all_workers if w], return_exceptions=True)

        # Close LLM client
        if self.llm_client:
            await self.llm_client.close()

        logger.info(f"Pipeline stopped. Processed {self.completed_count} blocks from {len(self.completed_documents)} documents, {self.error_count} errors")

    async def add_document(self, document_id: int, document_url: str, job_id: str, code_blocks: List[CodeBlock]) -> None:
        """Add a document's code blocks to the enrichment queue.
        
        Args:
            document_id: Database document ID
            document_url: Document URL
            job_id: Crawl job ID
            code_blocks: List of code blocks to enrich
        """
        # Track document snippet count
        self.document_snippet_counts[document_id] = len(code_blocks)
        self.document_completed_snippets[document_id] = 0

        task_count = 0
        for block in code_blocks:
            task_id = f"{document_id}_{block.hash[:8]}"
            task = EnrichmentTask(
                document_id=document_id,
                document_url=document_url,
                job_id=job_id,
                code_block=block,
                task_id=task_id
            )
            # Add with timeout to prevent blocking forever if queue is full
            try:
                # First try non-blocking to check if queue is full
                if self.enrichment_queue.full():
                    queue_size = self.enrichment_queue.qsize()
                    logger.warning(f"Enrichment queue is full ({queue_size}/{self.max_queue_size}). Waiting for space...")
                    
                await asyncio.wait_for(self.enrichment_queue.put(task), timeout=5.0)
                task_count += 1
                logger.debug(f"Added task {task_id} to enrichment queue")
            except asyncio.TimeoutError:
                logger.error(f"Failed to add task {task_id} to enrichment queue - queue full after 5s timeout!")
                stats = self.get_stats()
                logger.error(f"Queue stats: {stats}")
                # Continue with remaining tasks instead of blocking

        # Log detailed information about queue state
        logger.info(f"Added {task_count} enrichment tasks for document {document_id} ({document_url})")
        logger.info(f"Enrichment queue size: {self.enrichment_queue.qsize()}/{self.max_queue_size}")
        logger.info(f"Storage queue size: {self.storage_queue.qsize()}/{self.max_queue_size}")

    async def _enrichment_worker(self, worker_id: str) -> None:
        """Worker that processes enrichment tasks."""
        logger.info(f"Enrichment worker {worker_id} starting...")
        await asyncio.sleep(0)  # Yield to ensure proper scheduling
        logger.info(f"Enrichment worker {worker_id} started and ready")
        tasks_processed = 0

        logger.debug(f"Worker {worker_id} entering main loop, is_running={self.is_running}")
        try:
            loop_iterations = 0
            logger.info(f"Worker {worker_id} about to start while loop - is_running={self.is_running}")
            while self.is_running:
                loop_iterations += 1
                if loop_iterations == 1:
                    logger.info(f"Worker {worker_id} - first iteration of main loop")
                logger.debug(f"Worker {worker_id} iteration {loop_iterations} started")
                try:
                    # Get task with timeout to allow checking is_running
                    queue_size = self.enrichment_queue.qsize()
                    if queue_size > 0:
                        logger.info(f"Worker {worker_id} attempting to get task from queue with {queue_size} items")

                    task = await asyncio.wait_for(self.enrichment_queue.get(), timeout=1.0)
                    logger.info(f"Worker {worker_id} successfully got task from queue")

                    # Track active task
                    self.active_tasks[task.task_id] = task
                    logger.info(f"Worker {worker_id} received task {task.task_id} from document {task.document_id}")
                    logger.debug(f"Task details: language={task.code_block.language}, lines={task.code_block.lines_of_code}")

                    try:
                        # Enrich the code block
                        if not self.enricher:
                            raise RuntimeError("Enricher not initialized")
                        enriched_block = await self.enricher.enrich_code_block(task.code_block)

                        # Create result
                        result = EnrichmentResult(
                            task=task,
                            enriched_block=enriched_block,
                            success=True
                        )

                        # Add to storage queue
                        await self.storage_queue.put(result)
                        tasks_processed += 1

                        if tasks_processed % 10 == 0:
                            logger.info(f"Worker {worker_id} has processed {tasks_processed} tasks")

                    except Exception as e:
                        logger.error(f"Worker {worker_id} error enriching block: {e}")
                        # Create error result
                        result = EnrichmentResult(
                            task=task,
                            enriched_block=EnrichedCodeBlock(original=task.code_block),
                            success=False,
                            error=str(e)
                        )
                        await self.storage_queue.put(result)
                        self.error_count += 1

                    finally:
                        # Remove from active tasks
                        self.active_tasks.pop(task.task_id, None)
                        # Mark task as done
                        self.enrichment_queue.task_done()

                except asyncio.TimeoutError:
                    # Normal timeout, continue loop
                    queue_size = self.enrichment_queue.qsize()
                    if queue_size > 0:
                        logger.warning(f"Worker {worker_id} timed out but queue has {queue_size} tasks")
                        # Try again immediately if queue has items
                        continue
                    else:
                        # Only log occasionally to avoid spam
                        if loop_iterations <= 3 or (tasks_processed == 0 and loop_iterations % 10 == 0):
                            logger.debug(f"Worker {worker_id} iteration {loop_iterations}: waiting for tasks (is_running={self.is_running})")
                    await asyncio.sleep(0)  # Yield to event loop
                    continue
                except asyncio.CancelledError:
                    # Worker cancelled, exit
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in enrichment worker {worker_id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Worker {worker_id} crashed outside main loop: {e}", exc_info=True)
        finally:
            logger.info(f"Enrichment worker {worker_id} exiting - is_running={self.is_running}, tasks_processed={tasks_processed}")

        logger.info(f"Enrichment worker {worker_id} stopped after processing {tasks_processed} tasks")

    async def _status_monitor(self) -> None:
        """Monitor pipeline status and log periodically."""
        logger.info("Pipeline status monitor started")
        last_log_time = asyncio.get_event_loop().time()

        while self.is_running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds

                current_time = asyncio.get_event_loop().time()
                if current_time - last_log_time >= 10:  # Log every 10 seconds
                    stats = self.get_stats()

                    # Check worker health
                    active_workers = sum(1 for w in self.enrichment_workers if not w.done())
                    dead_workers = len(self.enrichment_workers) - active_workers

                    # Log only when there's activity or issues
                    if stats['enrichment_queue_size'] > 0 or stats['active_tasks'] > 0 or dead_workers > 0:
                        logger.info(
                            f"Pipeline Status - "
                            f"Workers: {active_workers}/{len(self.enrichment_workers)}, "
                            f"Enrichment Queue: {stats['enrichment_queue_size']}, "
                            f"Storage Queue: {stats['storage_queue_size']}, "
                            f"Active: {stats['active_tasks']}, "
                            f"Completed: {stats['completed_count']}, "
                            f"Errors: {stats['error_count']}"
                        )

                    # Restart dead workers if needed
                    if dead_workers > 0 and self.is_running:
                        logger.warning(f"Found {dead_workers} dead workers, restarting them...")
                        await self._restart_dead_workers()

                    last_log_time = current_time

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status monitor: {e}")

        logger.info("Pipeline status monitor stopped")

    async def _restart_dead_workers(self) -> None:
        """Restart any workers that have died."""
        new_workers = []
        for i, worker in enumerate(self.enrichment_workers):
            if worker.done():
                # Log why worker died
                if worker.cancelled():
                    logger.warning(f"Worker enricher-{i} was cancelled")
                else:
                    exc = worker.exception()
                    if exc:
                        logger.error(f"Worker enricher-{i} died with exception: {exc}")
                    else:
                        logger.warning(f"Worker enricher-{i} completed unexpectedly")

                # Create new worker
                new_worker = asyncio.create_task(self._enrichment_worker(f"enricher-{i}"))
                new_workers.append(new_worker)
                logger.info(f"Restarted worker enricher-{i}")
            else:
                new_workers.append(worker)

        self.enrichment_workers = new_workers

    async def _storage_worker(self) -> None:
        """Worker that stores enriched results in batches."""
        logger.info("Storage worker starting...")
        await asyncio.sleep(0)  # Yield to ensure proper scheduling
        logger.info("Storage worker started and ready")

        batch: List[EnrichmentResult] = []

        while self.is_running or not self.storage_queue.empty():
            try:
                # Collect batch with timeout
                while len(batch) < self.storage_batch_size:
                    try:
                        result = await asyncio.wait_for(self.storage_queue.get(), timeout=1.0)
                        batch.append(result)
                    except asyncio.TimeoutError:
                        # Process partial batch if we have items
                        if batch:
                            break
                        else:
                            continue

                # Process batch if we have items
                if batch:
                    await self._store_batch(batch)

                    # Mark tasks as done
                    for _ in batch:
                        self.storage_queue.task_done()

                    # Update counts
                    self.completed_count += len(batch)

                    # Update document completion tracking
                    for result in batch:
                        doc_id = result.task.document_id
                        self.document_completed_snippets[doc_id] = self.document_completed_snippets.get(doc_id, 0) + 1

                        # Check if document is fully enriched OR all tasks have been processed (including skipped)
                        # A document is complete when we've processed all its snippets, even if some were skipped
                        expected_count = self.document_snippet_counts.get(doc_id, 0)
                        processed_count = self.document_completed_snippets.get(doc_id, 0)
                        
                        if expected_count > 0 and processed_count >= expected_count:
                            self.completed_documents.add(doc_id)

                    # Clear batch
                    batch = []

            except asyncio.CancelledError:
                # Process remaining batch before exiting
                if batch:
                    await self._store_batch(batch)
                break
            except Exception as e:
                logger.error(f"Error in storage worker: {e}")
                # Clear batch to avoid reprocessing
                batch = []

        logger.info("Storage worker stopped")

    async def _store_batch(self, batch: List[EnrichmentResult]) -> None:
        """Store a batch of enriched results."""
        logger.debug(f"Storing batch of {len(batch)} enriched results")

        with self.db_manager.session_scope() as session:
            for result in batch:
                if not result.success:
                    continue

                task = result.task
                enriched_block = result.enriched_block
                block = enriched_block.original

                # Determine final language
                final_language = enriched_block.detected_language or block.language

                # Extract functions and imports
                functions = []
                imports = []
                if self.settings.code_extraction.extract_functions:
                    functions = self.language_detector.extract_functions(
                        block.content, final_language
                    )
                if self.settings.code_extraction.extract_imports:
                    imports = self.language_detector.extract_imports(
                        block.content, final_language
                    )

                # Merge metadata
                merged_metadata = block.extraction_metadata.copy()
                if enriched_block.keywords:
                    merged_metadata["keywords"] = enriched_block.keywords
                if enriched_block.frameworks:
                    merged_metadata["frameworks"] = enriched_block.frameworks

                if enriched_block.purpose:
                    merged_metadata["purpose"] = enriched_block.purpose
                if enriched_block.dependencies:
                    merged_metadata["dependencies"] = enriched_block.dependencies
                merged_metadata["llm_enriched"] = True

                # Extract section information
                section_title = block.extraction_metadata.get("section_title")
                section_content = block.extraction_metadata.get("full_section_content")

                # Create snippet
                snippet = CodeSnippet(
                    document_id=task.document_id,
                    title=enriched_block.enriched_title or block.title,
                    description=enriched_block.enriched_description or block.description,
                    language=final_language,
                    code_content=block.content,
                    code_hash=block.hash,
                    line_start=block.line_start,
                    line_end=block.line_end,
                    context_before=block.context_before,
                    context_after=block.context_after,
                    section_title=section_title,
                    section_content=section_content,
                    functions=functions,
                    imports=imports,
                    source_url=task.document_url,
                    metadata=merged_metadata,
                )

                # Check for duplicate
                existing_snippet = session.query(CodeSnippet).filter_by(
                    code_hash=block.hash
                ).first()

                if not existing_snippet:
                    session.add(snippet)
                else:
                    # Update existing snippet
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

            # Commit batch
            session.commit()

        logger.debug(f"Stored batch of {len(batch)} snippets")

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "is_running": self.is_running,
            "enrichment_queue_size": self.enrichment_queue.qsize(),
            "storage_queue_size": self.storage_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "completed_count": self.completed_count,
            "completed_documents": len(self.completed_documents),
            "error_count": self.error_count,
            "workers": len(self.enrichment_workers),
        }
