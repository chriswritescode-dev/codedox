"""Process crawl results and store in database."""

import logging
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from ..database import Document, CodeSnippet, PageLink, get_db_manager
from ..parser import CodeExtractor
from ..language import LanguageDetector
from ..llm import MetadataEnricher
from .enrichment_pipeline import EnrichmentPipeline

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Processes crawl results and stores them in the database."""

    def __init__(
        self,
        code_extractor: CodeExtractor,
        language_detector: LanguageDetector,
        metadata_enricher: Optional[MetadataEnricher] = None,
        enrichment_pipeline: Optional[EnrichmentPipeline] = None,
    ):
        """Initialize result processor.

        Args:
            code_extractor: Code extractor instance
            language_detector: Language detector instance
            metadata_enricher: Optional metadata enricher
            enrichment_pipeline: Optional enrichment pipeline
        """
        self.code_extractor = code_extractor
        self.language_detector = language_detector
        self.metadata_enricher = metadata_enricher
        self.enrichment_pipeline = enrichment_pipeline
        self.db_manager = get_db_manager()

    async def process_result_pipeline(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> Tuple[int, int, Optional[asyncio.Task]]:
        """Process result using enrichment pipeline (non-blocking).

        Args:
            result: Crawl result
            job_id: Job ID
            depth: Crawl depth

        Returns:
            Tuple of (document_id, code_blocks_submitted, submission_task)
        """
        with self.db_manager.session_scope() as session:
            # Check if document exists
            existing_doc = session.query(Document).filter_by(url=result.url).first()

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content unchanged
                return int(existing_doc.id), 0, None

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            doc.enrichment_status = "processing"
            session.commit()

            doc_id = int(doc.id)

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

        # Submit to pipeline if available
        logger.debug(f"Pipeline check - exists: {self.enrichment_pipeline is not None}, code_blocks: {len(result.code_blocks) if result.code_blocks else 0}")
        
        if self.enrichment_pipeline and result.code_blocks:
            logger.info(
                f"Submitting {len(result.code_blocks)} code blocks from {result.url} to pipeline"
            )
            # Create task without blocking
            task = asyncio.create_task(
                self._submit_to_pipeline(doc_id, result.url, job_id, result.code_blocks)
            )

            # Add error handler
            def log_error(t: asyncio.Task[None]) -> None:
                if t.exception():
                    logger.error(f"Failed to submit enrichment task: {t.exception()}")

            task.add_done_callback(log_error)
            return doc_id, len(result.code_blocks), task
        else:
            if not self.enrichment_pipeline:
                logger.warning(f"No pipeline available to process {len(result.code_blocks) if result.code_blocks else 0} code blocks")
            elif not result.code_blocks:
                logger.debug("No code blocks to process")

        return doc_id, 0, None

    async def process_result(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> Tuple[int, int]:
        """Process result with immediate enrichment.

        Args:
            result: Crawl result
            job_id: Job ID
            depth: Crawl depth

        Returns:
            Tuple of (document_id, snippet_count)
        """
        snippet_count = 0

        with self.db_manager.session_scope() as session:
            # Check if document exists
            existing_doc = session.query(Document).filter_by(url=result.url).first()

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content unchanged
                return int(existing_doc.id), 0, None

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            doc.enrichment_status = "processing"
            session.commit()

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

            # Process code blocks
            if result.code_blocks:
                snippet_count = await self._process_code_blocks(
                    session, doc, result.code_blocks, result.url
                )

            # Mark document as enriched
            doc.enrichment_status = "completed" if not doc.enrichment_error else "failed"
            doc.enriched_at = datetime.utcnow()

            session.commit()
            return int(doc.id), snippet_count

    async def process_batch(
        self, results: List[Any], job_id: str, use_pipeline: bool = True  # List[CrawlResult]
    ) -> Tuple[int, int, List[Dict]]:
        """Process a batch of results.

        Args:
            results: List of crawl results
            job_id: Job ID
            use_pipeline: Whether to use enrichment pipeline

        Returns:
            Tuple of (total_documents, total_snippets, all_links)
        """
        total_documents = 0
        total_snippets = 0
        all_links = []

        # Process in smaller batches
        batch_size = 10
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            tasks = []

            for result in batch:
                if use_pipeline:
                    task = self.process_result_pipeline(
                        result, job_id, result.metadata.get("depth", 0)
                    )
                else:
                    task = self.process_result(result, job_id, result.metadata.get("depth", 0))
                tasks.append(task)

            # Wait for batch completion
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, br in enumerate(batch_results):
                if isinstance(br, Exception):
                    logger.error(f"Error processing result: {br}")
                else:
                    # Handle both 2-tuple (from process_result) and 3-tuple (from process_result_pipeline)
                    if len(br) == 3:
                        doc_id, snippet_count, _ = br  # Ignore the task in batch processing
                    else:
                        doc_id, snippet_count = br
                    total_documents += 1
                    total_snippets += snippet_count

                    # Extract links from this result
                    links = self._extract_links(batch[j], batch[j].metadata.get("depth", 0))
                    all_links.extend(links)

        return total_documents, total_snippets, all_links

    def _create_or_update_document(
        self,
        session: Session,
        result: Any,  # CrawlResult
        job_id: str,
        depth: int,
        existing_doc: Optional[Document] = None,
    ) -> Document:
        """Create or update document in database.

        Args:
            session: Database session
            result: Crawl result
            job_id: Job ID
            depth: Crawl depth
            existing_doc: Existing document if any

        Returns:
            Document instance
        """
        if existing_doc:
            # Delete old snippets
            session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()

            # Update existing
            doc = existing_doc
            doc.title = result.title
            doc.markdown_content = result.markdown_content
            doc.content_hash = result.content_hash
            doc.crawl_job_id = job_id
            doc.last_crawled = datetime.utcnow()
        else:
            # Create new
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
        return doc

    async def _check_auto_detect_name(
        self, session: Session, job_id: str, result: Any  # CrawlResult
    ) -> None:
        """Check if we need to auto-detect job name.

        Args:
            session: Database session
            job_id: Job ID
            result: Crawl result
        """
        from ..database import CrawlJob

        job = session.query(CrawlJob).filter_by(id=job_id).first()

        if job and job.name.startswith("[Auto-detecting"):
            # Extract name from first page
            detected_name = await self._extract_site_name(result.title, result.url, result.metadata)
            if detected_name:
                logger.info(f"Auto-detected site name: {detected_name}")
                job.name = detected_name
                session.commit()

    async def _extract_site_name(
        self, title: str, url: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Extract site name using LLM or fallback logic.

        Args:
            title: Page title
            url: Page URL
            metadata: Optional metadata

        Returns:
            Site name or None
        """
        if not title:
            return None

        # If no LLM available, use fallback
        if not self.metadata_enricher or not self.metadata_enricher.llm_client:
            if metadata and "title" in metadata:
                meta_title = metadata["title"]
                if meta_title and len(meta_title) <= 50:
                    return meta_title.strip()

            # Truncate long titles
            if len(title) > 50:
                return title[:50].rsplit(" ", 1)[0] + "..."
            return title.strip()

        # Use LLM to extract clean name
        try:
            prompt = f"""Extract the name of the documentation site, library, or framework from this page title.

Page Title: {title}
Page URL: {url}

Instructions:
- Return ONLY the clean name of the library, framework, or documentation site
- Remove any suffixes like "Documentation", "Docs", "Official Site", "Home", etc.
- Remove version numbers
- Use proper capitalization (e.g., "Next.js" not "nextjs")
- Keep the name concise (under 50 characters)

Examples:
- "Getting Started | Next.js" → "Next.js"
- "React Documentation" → "React"
- "Django 5.0 Documentation" → "Django"

Extracted name:"""

            response = await self.metadata_enricher.llm_client.generate(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1,
            )

            extracted_name = response.content.strip().strip("\"'")

            if extracted_name and len(extracted_name) <= 50:
                logger.info(f"LLM extracted site name: {extracted_name}")
                return extracted_name
        except Exception as e:
            logger.error(f"Failed to extract site name using LLM: {e}")

        # Fallback
        if metadata and "title" in metadata:
            return metadata["title"][:50].strip()
        return title[:50].strip()

    async def _process_code_blocks(
        self, session: Session, doc: Document, code_blocks: List[Any], source_url: str
    ) -> int:
        """Process code blocks with enrichment.

        Args:
            session: Database session
            doc: Document instance
            code_blocks: List of code blocks
            source_url: Source URL

        Returns:
            Number of snippets created
        """
        snippet_count = 0

        # Enrich blocks if enricher available
        enriched_blocks = []
        if self.metadata_enricher and code_blocks:
            try:
                logger.info(f"Enriching {len(code_blocks)} code blocks with LLM")
                enriched_results = await self.metadata_enricher.enrich_batch(code_blocks)
                enriched_blocks = enriched_results
            except Exception as e:
                logger.error(f"LLM enrichment failed: {e}")
                doc.enrichment_error = str(e)
                # Fallback to unenriched
                enriched_blocks = [self._create_mock_enriched(block) for block in code_blocks]
        else:
            enriched_blocks = [self._create_mock_enriched(block) for block in code_blocks]

        # Process enriched blocks
        for enriched_block in enriched_blocks:
            block = enriched_block.original

            # Use LLM-detected language if available
            final_language = enriched_block.detected_language or block.language

            # Extract functions/imports
            functions = []
            imports = []
            if hasattr(self, "settings") and self.settings.code_extraction.extract_functions:
                functions = self.language_detector.extract_functions(block.content, final_language)
            if hasattr(self, "settings") and self.settings.code_extraction.extract_imports:
                imports = self.language_detector.extract_imports(block.content, final_language)

            # Merge metadata
            merged_metadata = self._merge_metadata(block, enriched_block)

            # Create snippet
            snippet = self._create_snippet(
                doc,
                block,
                enriched_block,
                final_language,
                functions,
                imports,
                source_url,
                merged_metadata,
            )

            # Check for duplicate
            existing = session.query(CodeSnippet).filter_by(code_hash=block.hash).first()

            if not existing:
                session.add(snippet)
                snippet_count += 1
            elif merged_metadata.get("llm_enriched"):
                # Update existing with enriched data
                self._update_snippet(existing, snippet)

        return snippet_count

    def _create_snippet(
        self,
        doc: Document,
        block: Any,
        enriched_block: Any,
        language: str,
        functions: List[str],
        imports: List[str],
        source_url: str,
        metadata: Dict[str, Any],
    ) -> CodeSnippet:
        """Create a code snippet instance.

        Args:
            doc: Document instance
            block: Original code block
            enriched_block: Enriched code block
            language: Final language
            functions: Extracted functions
            imports: Extracted imports
            source_url: Source URL
            metadata: Merged metadata

        Returns:
            CodeSnippet instance
        """
        # Extract section info
        section_title = None
        section_content = None
        if hasattr(block, "extraction_metadata"):
            section_title = block.extraction_metadata.get("section_title")
            section_content = block.extraction_metadata.get("full_section_content")

        return CodeSnippet(
            document_id=doc.id,
            title=enriched_block.enriched_title or block.title,
            description=enriched_block.enriched_description or block.description,
            language=language,
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
            source_url=source_url,
            metadata=metadata,
        )

    def _update_snippet(self, existing: CodeSnippet, new: CodeSnippet) -> None:
        """Update existing snippet with new data.

        Args:
            existing: Existing snippet
            new: New snippet data
        """
        existing.title = new.title
        existing.description = new.description
        existing.language = new.language
        existing.context_before = new.context_before
        existing.context_after = new.context_after
        existing.section_title = new.section_title
        existing.section_content = new.section_content
        existing.functions = new.functions
        existing.imports = new.imports
        existing.metadata = new.metadata
        existing.updated_at = datetime.utcnow()
        logger.debug(f"Updated existing snippet: {new.title}")

    def _merge_metadata(self, block: Any, enriched_block: Any) -> Dict[str, Any]:
        """Merge metadata from block and enriched block.

        Args:
            block: Original block
            enriched_block: Enriched block

        Returns:
            Merged metadata
        """
        metadata = block.extraction_metadata.copy()

        if hasattr(enriched_block, "keywords") and enriched_block.keywords:
            metadata["keywords"] = enriched_block.keywords
        if hasattr(enriched_block, "frameworks") and enriched_block.frameworks:
            metadata["frameworks"] = enriched_block.frameworks
        if hasattr(enriched_block, "purpose"):
            metadata["purpose"] = enriched_block.purpose
        if hasattr(enriched_block, "dependencies") and enriched_block.dependencies:
            metadata["dependencies"] = enriched_block.dependencies

        metadata["llm_enriched"] = hasattr(enriched_block, "enriched_title")

        return metadata

    def _create_mock_enriched(self, block: Any) -> Any:
        """Create mock enriched block for fallback.

        Args:
            block: Original block

        Returns:
            Mock enriched block
        """
        from ..llm.enricher import EnrichedCodeBlock

        return EnrichedCodeBlock(original=block)

    async def _submit_to_pipeline(
        self, document_id: int, document_url: str, job_id: str, code_blocks: List[Any]
    ) -> None:
        """Submit document to enrichment pipeline.

        Args:
            document_id: Document ID
            document_url: Document URL
            job_id: Job ID
            code_blocks: Code blocks to enrich
        """
        try:
            logger.debug(f"_submit_to_pipeline called - pipeline exists: {self.enrichment_pipeline is not None}")
            logger.debug(f"Pipeline running: {self.enrichment_pipeline.is_running if self.enrichment_pipeline else 'N/A'}")
            
            if self.enrichment_pipeline:
                await self.enrichment_pipeline.add_document(
                    document_id=document_id,
                    document_url=document_url,
                    job_id=job_id,
                    code_blocks=code_blocks,
                )
                logger.info(f"Submitted {len(code_blocks)} blocks for doc {document_id}")
            else:
                logger.warning(f"No enrichment pipeline available for doc {document_id} with {len(code_blocks)} blocks")
        except Exception as e:
            logger.error(f"Failed to submit document {document_id} to pipeline: {e}")

    def _extract_links(self, result: Any, depth: int) -> List[Dict[str, Any]]:
        """Extract links from result.

        Args:
            result: Crawl result
            depth: Current depth

        Returns:
            List of link dictionaries
        """
        from urllib.parse import urljoin

        links = []
        for link_info in result.links:
            link_url = link_info.get("url", "")
            if link_url and not link_url.startswith(("#", "javascript:")):
                if not link_url.startswith(("http://", "https://")):
                    link_url = urljoin(result.url, link_url)

                links.append(
                    {
                        "source_url": result.url,
                        "target_url": link_url,
                        "link_text": link_info.get("text", ""),
                        "depth_level": depth + 1,
                    }
                )

        return links

    async def store_links_batch(self, job_id: str, links: List[Dict[str, Any]]) -> None:
        """Store a batch of links asynchronously.

        Args:
            job_id: Job ID
            links: List of link data
        """
        try:
            with self.db_manager.session_scope() as session:
                for link_data in links:
                    # Check if exists
                    existing = (
                        session.query(PageLink)
                        .filter_by(
                            source_url=link_data["source_url"],
                            target_url=link_data["target_url"],
                            crawl_job_id=job_id,
                        )
                        .first()
                    )

                    if not existing:
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
