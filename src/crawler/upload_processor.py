"""Upload processor for handling user-uploaded documentation files."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from ..config import get_settings
from ..database import CodeSnippet, Document, UploadJob, get_db_manager
from .config import create_browser_config
from .extraction_models import SimpleCodeBlock
from .html_code_extractor import HTMLCodeExtractor
from .llm_retry import LLMDescriptionGenerator
from .markdown_utils import remove_markdown_links
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class UploadConfig:
    """Configuration for an upload job."""

    name: str
    files: list[dict[str, Any]]  # List of {path, content, source_url}
    metadata: dict[str, Any] = field(default_factory=dict)
    version: str | None = None
    extract_code_only: bool = True
    use_llm: bool = True
    max_concurrent_files: int | None = None


@dataclass
class UploadResult:
    """Result from processing an uploaded file."""

    source_url: str
    title: str
    content_hash: str
    code_blocks: list[SimpleCodeBlock]
    content: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class UploadProcessor:
    """Processes uploaded documentation files."""

    def __init__(self):
        """Initialize the upload processor."""
        self.settings = settings
        self.db_manager = get_db_manager()
        self.html_extractor = HTMLCodeExtractor()
        self.result_processor = ResultProcessor()
        self.progress_tracker = ProgressTracker(self)

        # Initialize browser config for HTML processing
        self.browser_config = create_browser_config()

        # Initialize LLM generator if API key is available
        self.description_generator = None
        if self.settings.code_extraction.llm_api_key:
            self.description_generator = LLMDescriptionGenerator()

    async def process_upload(self, config: UploadConfig) -> str:
        """
        Process an upload job.

        Args:
            config: Upload configuration

        Returns:
            Job ID
        """
        # Create upload job
        job_id = self._create_upload_job(config)

        # Start async processing
        asyncio.create_task(self._execute_upload(job_id, config))

        return job_id

    def _create_upload_job(self, config: UploadConfig) -> str:
        """Create a new upload job in the database, reusing existing job if name/version match."""
        import uuid

        from ..database import UploadJob

        with self.db_manager.session_scope() as session:
            # Check for existing job with same name and version
            existing_job = (
                session.query(UploadJob).filter_by(name=config.name, version=config.version).first()
            )

            if existing_job:
                # Reuse existing job - reset it for new upload
                logger.info(
                    f"Reusing existing upload job '{config.name}' (v{config.version}): {existing_job.id}"
                )

                existing_job.file_count = len(config.files)
                existing_job.processed_files = 0
                existing_job.snippets_extracted = 0
                existing_job.status = "running"
                existing_job.error_message = None
                existing_job.started_at = datetime.utcnow()
                existing_job.completed_at = None
                existing_job.config = config.metadata
                session.commit()

                return str(existing_job.id)
            else:
                # Create new job
                job = UploadJob(
                    id=str(uuid.uuid4()),
                    name=config.name,
                    version=config.version,
                    file_count=len(config.files),
                    status="running",
                    config=config.metadata,
                )
                session.add(job)
                session.commit()

                return str(job.id)

    async def _execute_upload(self, job_id: str, config: UploadConfig) -> None:
        """Execute the upload job."""
        try:
            # Start tracking
            await self.progress_tracker.start_tracking(job_id)

            # Determine concurrent processing limit
            max_concurrent = (
                config.max_concurrent_files or self.settings.crawling.max_concurrent_crawls
            )
            semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(
                f"Processing {len(config.files)} files with max_concurrent={max_concurrent}"
            )

            # Thread-safe counters for progress tracking
            total_snippets = 0
            processed_files = 0
            skipped_files = 0
            progress_lock = asyncio.Lock()

            async def process_single_file(file_info: dict[str, Any]) -> tuple[int, int]:
                """Process a single file and return (doc_id, snippet_count)."""
                nonlocal total_snippets, processed_files, skipped_files

                async with semaphore:
                    try:
                        source_url = file_info["source_url"]

                        # Calculate content hash first to check for duplicates
                        content_hash = hashlib.md5(file_info["content"].encode()).hexdigest()

                        # Check if this file has already been processed
                        with self.db_manager.session_scope() as session:
                            from ..database import check_content_hash

                            content_unchanged, existing_snippet_count = check_content_hash(
                                session, source_url, content_hash
                            )

                            if content_unchanged:
                                logger.info(
                                    f"Content unchanged for {source_url} (hash: {content_hash[:8]}...), skipping processing. Using {existing_snippet_count} existing snippets."
                                )

                                # Update counters for skipped file
                                async with progress_lock:
                                    total_snippets += existing_snippet_count
                                    processed_files += 1
                                    skipped_files += 1

                                    # Update progress
                                    await self.progress_tracker.update_progress(
                                        job_id,
                                        processed_pages=processed_files,
                                        total_pages=len(config.files),
                                        snippets_extracted=total_snippets,
                                        documents_crawled=processed_files,
                                        send_notification=True,
                                    )

                                return 0, existing_snippet_count

                        # Content is new or changed, process it
                        result = await self._process_file(
                            file_info["content"],
                            source_url,
                            file_info.get("content_type", "markdown"),
                        )

                        if result.error:
                            logger.error(f"Failed to process {source_url}: {result.error}")
                            return 0, 0

                        # Generate LLM descriptions if enabled
                        if config.use_llm and self.description_generator and result.code_blocks:
                            try:
                                result.code_blocks = await self.description_generator.generate_titles_and_descriptions_batch(
                                    result.code_blocks, result.source_url, max_concurrent=5
                                )
                            except Exception as e:
                                logger.warning(
                                    f"LLM description generation failed for {source_url}: {e}"
                                )

                        # Store in database
                        doc_id, snippet_count = await self._store_result(result, job_id)

                        # Update counters thread-safely
                        async with progress_lock:
                            total_snippets += snippet_count
                            processed_files += 1

                            # Update progress
                            await self.progress_tracker.update_progress(
                                job_id,
                                processed_pages=processed_files,
                                total_pages=len(config.files),
                                snippets_extracted=total_snippets,
                                documents_crawled=processed_files,
                                send_notification=True,
                            )

                        return doc_id, snippet_count

                    except Exception as e:
                        logger.error(f"Failed to process file {file_info['source_url']}: {e}")
                        async with progress_lock:
                            processed_files += 1
                            # Update progress even on failure
                            await self.progress_tracker.update_progress(
                                job_id,
                                processed_pages=processed_files,
                                total_pages=len(config.files),
                                snippets_extracted=total_snippets,
                                documents_crawled=processed_files,
                                send_notification=True,
                            )
                        return 0, 0

            # Process all files concurrently
            tasks = [process_single_file(file_info) for file_info in config.files]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any exceptions that occurred during processing
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Exception processing file {config.files[i]['source_url']}: {result}"
                    )

            # Log efficiency if any files were skipped
            if skipped_files > 0:
                efficiency_pct = (
                    (skipped_files / processed_files) * 100 if processed_files > 0 else 0
                )
                logger.info(
                    f"[UPLOAD EFFICIENCY] Skipped {skipped_files}/{processed_files} files ({efficiency_pct:.1f}%) as unchanged. Total snippets: {total_snippets}"
                )

            # Complete job
            self._complete_job(job_id, success=True, snippets_extracted=total_snippets)
            await self.progress_tracker.send_completion(job_id, success=True)

        except Exception as e:
            logger.error(f"Upload job {job_id} failed: {e}")
            self._complete_job(job_id, success=False, error_message=str(e))
            await self.progress_tracker.send_completion(job_id, success=False, error=str(e))
        finally:
            await self.progress_tracker.stop_tracking(job_id)

    async def _process_file(self, content: str, source_url: str, content_type: str) -> UploadResult:
        """Process a single file and extract code blocks."""
        try:
            # Calculate content hash from original content
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Initialize metadata
            metadata = {"content_type": content_type}

            # Process based on content type
            if content_type == "html":
                # Process HTML through Crawl4AI for consistent extraction
                # Use the same approach as the page crawler

                # Create crawler config with markdown generation
                crawler_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    verbose=False,
                    markdown_generator=DefaultMarkdownGenerator(
                        content_source="raw_html", options={"ignore_links": False}
                    ),
                )

                # Process HTML through Crawl4AI using raw: prefix
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    # Use raw: prefix to process HTML content directly
                    raw_url = f"raw:{content}"
                    result = await crawler.arun(url=raw_url, config=crawler_config)

                    if not result.success:
                        error_msg = f"Crawl4AI processing failed for {source_url}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                    # Extract markdown content from result
                    if hasattr(result, "markdown"):
                        if hasattr(result.markdown, "raw_markdown"):
                            markdown_content = result.markdown.raw_markdown
                        elif hasattr(result.markdown, "markdown_v2"):
                            markdown_content = result.markdown.markdown_v2.raw_markdown
                        else:
                            markdown_content = str(result.markdown) if result.markdown else ""
                    else:
                        markdown_content = ""

                    # Get title from metadata or extract from content
                    title = None
                    if hasattr(result, "metadata") and result.metadata:
                        title = result.metadata.get("title", "")

                    if not title:
                        title = self._extract_title(markdown_content, source_url)

                    # Extract code blocks from the original HTML content
                    # (not the cleaned version from Crawl4AI which might lose language classes)
                    extracted_blocks = self.html_extractor.extract_code_blocks(content, source_url)

                # Convert to SimpleCodeBlock format
                code_blocks = []
                for block in extracted_blocks:
                    simple_block = SimpleCodeBlock(
                        code=block.code,
                        language=block.language,
                        title=block.title,
                        description=block.description,
                        context_before=block.context_before,
                        metadata={
                            "container_type": block.container_type,
                            "extraction_method": "html",
                        },
                    )
                    code_blocks.append(simple_block)

            else:
                # For markdown and other text formats
                markdown_content = content
                title = self._extract_title(content, source_url)
                code_blocks = self._extract_markdown_code_blocks(content, source_url)

            return UploadResult(
                source_url=source_url,
                title=title,
                content_hash=content_hash,
                code_blocks=code_blocks,
                content=markdown_content,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to process file {source_url}: {e}")
            return UploadResult(
                source_url=source_url,
                title="Unknown",
                content_hash="",
                code_blocks=[],
                content=None,
                error=str(e),
            )

    def update_job_progress(self, job_id: str, **kwargs) -> bool:
        """Update upload job progress (compatible with ProgressTracker)."""
        try:
            with self.db_manager.session_scope() as session:
                job = session.query(UploadJob).filter_by(id=job_id).first()
                if not job:
                    return False

                # Update fields if provided
                if "processed_pages" in kwargs:
                    job.processed_files = kwargs["processed_pages"]
                if "snippets_extracted" in kwargs:
                    job.snippets_extracted = kwargs["snippets_extracted"]

                job.updated_at = datetime.utcnow()
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
            return False

    def _extract_title(self, content: str, source_url: str) -> str:
        """Extract title from content or use filename."""
        from src.api.routes.upload_utils import TitleExtractor

        return TitleExtractor.resolve(None, content, source_url)

    def _extract_markdown_code_blocks(self, content: str, source_url: str = None) -> list[SimpleCodeBlock]:
        """Extract code blocks from markdown content.

        Args:
            content: Markdown content
            source_url: Optional source URL for the content

        Returns:
            List of SimpleCodeBlock objects
        """
        from src.api.routes.upload_utils import MarkdownCodeExtractor

        return MarkdownCodeExtractor.extract_blocks(content, source_url=source_url)

    async def _store_result(self, result: UploadResult, job_id: str) -> tuple[int, int]:
        """Store upload result in database."""
        snippet_count = 0

        with self.db_manager.session_scope() as session:
            # Check if document already exists
            existing_doc = session.query(Document).filter_by(url=result.source_url).first()

            if existing_doc and existing_doc.content_hash == result.content_hash:
                return int(existing_doc.id), 0

            # Create or update document
            if existing_doc:
                # Delete old snippets
                session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()

                # Update existing
                doc = existing_doc
                doc.title = result.title
                doc.content_hash = result.content_hash
                doc.markdown_content = remove_markdown_links(result.content)
                doc.upload_job_id = job_id
                doc.last_crawled = datetime.utcnow()
            else:
                # Create new document linked to upload job
                doc = Document(
                    url=result.source_url,
                    title=result.title,
                    content_hash=result.content_hash,
                    markdown_content=remove_markdown_links(result.content),
                    upload_job_id=job_id,  # Link to upload job instead of crawl job
                    source_type="upload",  # Mark as upload source
                    crawl_depth=0,
                    meta_data=result.metadata,
                )
                session.add(doc)

            session.flush()  # Get doc.id

            # Process code blocks
            if result.code_blocks:
                # Convert SimpleCodeBlock to format expected by result processor
                code_blocks_data = []
                for block in result.code_blocks:
                    block_dict = {
                        "code": block.code,
                        "language": block.language,
                        "title": block.title or f"Code Block in {block.language or 'Unknown'}",
                        "description": block.description or f"Code block from {result.title}",
                        "metadata": block.metadata or {},
                        "filename": None,
                    }
                    code_blocks_data.append(block_dict)

                # Use result processor to store snippets
                snippet_count = await self.result_processor._process_code_blocks(
                    session, doc, code_blocks_data, result.source_url
                )

            session.commit()
            return int(doc.id), snippet_count

    def _complete_job(
        self,
        job_id: str,
        success: bool,
        error_message: str | None = None,
        snippets_extracted: int = 0,
    ) -> None:
        """Mark upload job as completed."""
        from ..database import UploadJob

        with self.db_manager.session_scope() as session:
            job = session.query(UploadJob).filter_by(id=job_id).first()
            if job:
                job.status = "completed" if success else "failed"
                job.completed_at = datetime.utcnow()
                job.error_message = error_message
                job.snippets_extracted = snippets_extracted
                session.commit()

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get upload job status."""
        from ..database import UploadJob

        with self.db_manager.session_scope() as session:
            job = session.query(UploadJob).filter_by(id=job_id).first()
            if job:
                return job.to_dict()
        return None

    def update_job_status(self, job_id: str, **kwargs) -> None:
        """Update upload job status."""
        from ..database import UploadJob

        with self.db_manager.session_scope() as session:
            job = session.query(UploadJob).filter_by(id=job_id).first()
            if job:
                for key, value in kwargs.items():
                    setattr(job, key, value)
                job.updated_at = datetime.utcnow()
                session.commit()
