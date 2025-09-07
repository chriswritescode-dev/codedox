"""Process crawl results and store in database."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import CodeSnippet, Document, get_db_manager
from .markdown_utils import remove_markdown_links

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Processes crawl results and stores them in the database."""

    def __init__(self):
        """Initialize result processor."""
        self.db_manager = get_db_manager()
        self.settings = get_settings()

    def cleanup(self):
        """Cleanup resources."""
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.cleanup()
        return False

    async def process_result_pipeline(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> tuple[int, int]:
        """Process result and store directly in database.

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

            # Check if we should ignore hash (for regeneration)
            ignore_hash = False
            if hasattr(result, 'metadata') and result.metadata:
                # Check if job has ignore_hash flag
                from ..database.models import CrawlJob
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job and job.config and isinstance(job.config, dict):
                    job_metadata = job.config.get('metadata', {})
                    ignore_hash = job_metadata.get('ignore_hash', False)

            if existing_doc and existing_doc.content_hash == result.content_hash and not ignore_hash:
                # Content unchanged and not ignoring hash - count existing snippets
                existing_snippet_count = session.query(CodeSnippet).filter_by(document_id=existing_doc.id).count()

                # Check if this is a retry job for better logging
                is_retry_job = False
                if hasattr(result, 'metadata') and result.metadata:
                    is_retry_job = result.metadata.get('is_retry', False)

                if is_retry_job:
                    logger.info(f"[RETRY EFFICIENCY] Content unchanged for {result.url}, returning {existing_snippet_count} existing snippets (avoiding redundant LLM calls)")
                else:
                    logger.debug(f"Content unchanged for {result.url}, returning {existing_snippet_count} existing snippets")
                return int(existing_doc.id), existing_snippet_count

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            session.commit()

            doc_id = int(doc.id)

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

            # Process code blocks directly
            if result.code_blocks:
                try:
                    # Delete old snippets only if we're about to create new ones
                    # This happens AFTER document update but BEFORE creating new snippets
                    if existing_doc:
                        session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()
                        logger.info(f"Deleted old snippets for document {existing_doc.id}")

                    snippet_count = await self._process_code_blocks(
                        session, doc, result.code_blocks, result.url
                    )
                except Exception as e:
                    # Roll back snippet deletion if processing fails
                    logger.error(f"Failed to process code blocks for {result.url}: {e}")
                    session.rollback()
                    # Re-count existing snippets
                    if existing_doc:
                        snippet_count = session.query(CodeSnippet).filter_by(document_id=existing_doc.id).count()
                        logger.info(f"Preserved {snippet_count} existing snippets after processing error")
                    else:
                        snippet_count = 0
                    # Still update the document metadata even if snippet processing failed
                    session.add(doc)
                    session.commit()

            session.commit()

            # Remove from failed_pages if this URL was previously failed
            from ..database import FailedPage
            session.query(FailedPage).filter_by(
                crawl_job_id=job_id,
                url=result.url
            ).delete()
            session.commit()

            return doc_id, snippet_count

    async def process_result(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> tuple[int, int]:
        """Process result with immediate extraction.

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

            # Check if we should ignore hash (for regeneration)
            ignore_hash = False
            from ..database.models import CrawlJob
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job and job.config and isinstance(job.config, dict):
                job_metadata = job.config.get('metadata', {})
                ignore_hash = job_metadata.get('ignore_hash', False)

            if existing_doc and existing_doc.content_hash == result.content_hash and not ignore_hash:
                # Content unchanged - always return existing snippet count
                existing_snippet_count = session.query(CodeSnippet).filter_by(document_id=existing_doc.id).count()

                # Check if this is a retry job for better logging
                is_retry_job = False
                if hasattr(result, 'metadata') and result.metadata:
                    is_retry_job = result.metadata.get('is_retry', False)

                if is_retry_job:
                    logger.info(f"[RETRY EFFICIENCY] Content unchanged for {result.url}, returning {existing_snippet_count} existing snippets (avoiding redundant LLM calls)")
                else:
                    logger.debug(f"Content unchanged for {result.url}, returning {existing_snippet_count} existing snippets")
                return int(existing_doc.id), existing_snippet_count

            # Log when ignoring hash
            if ignore_hash and existing_doc and existing_doc.content_hash == result.content_hash:
                logger.info(f"Ignoring content hash for {result.url} - forcing regeneration")

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            session.commit()

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

            # Process code blocks
            if result.code_blocks:
                try:
                    # Delete old snippets only if we're about to create new ones
                    # This happens AFTER document update but BEFORE creating new snippets
                    if existing_doc:
                        session.query(CodeSnippet).filter_by(document_id=existing_doc.id).delete()
                        logger.info(f"Deleted old snippets for document {existing_doc.id}")

                    snippet_count = await self._process_code_blocks(
                        session, doc, result.code_blocks, result.url
                    )
                except Exception as e:
                    # Roll back snippet deletion if processing fails
                    logger.error(f"Failed to process code blocks for {result.url}: {e}")
                    session.rollback()
                    # Re-count existing snippets
                    if existing_doc:
                        snippet_count = session.query(CodeSnippet).filter_by(document_id=existing_doc.id).count()
                        logger.info(f"Preserved {snippet_count} existing snippets after processing error")
                    else:
                        snippet_count = 0
                    # Still update the document metadata even if snippet processing failed
                    session.add(doc)
                    session.commit()

            session.commit()

            # Remove from failed_pages if this URL was previously failed
            from ..database import FailedPage
            session.query(FailedPage).filter_by(
                crawl_job_id=job_id,
                url=result.url
            ).delete()
            session.commit()

            return int(doc.id), snippet_count

    async def process_batch(
        self, results: list[Any], job_id: str, use_pipeline: bool = True  # List[CrawlResult]
    ) -> tuple[int, int]:
        """Process a batch of results.

        Args:
            results: List of crawl results
            job_id: Job ID
            use_pipeline: Whether to use pipeline processing

        Returns:
            Tuple of (total_documents, total_snippets)
        """
        total_documents = 0
        total_snippets = 0

        # Process in smaller batches
        batch_size = 10
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            tasks = []

            for result in batch:
                if use_pipeline:
                    coro = self.process_result_pipeline(
                        result, job_id, result.metadata.get("depth", 0)
                    )
                else:
                    coro = self.process_result(result, job_id, result.metadata.get("depth", 0))
                task = asyncio.create_task(coro)
                tasks.append(task)

            # Wait for batch completion with timeout
            logger.debug(f"Waiting for {len(tasks)} tasks to complete in batch {i // batch_size + 1}")
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=120  # 2 minutes for the entire batch
                )
            except asyncio.TimeoutError:
                logger.error(f"Batch {i // batch_size + 1} timed out after 120s with {len(tasks)} tasks")
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                continue  # Skip this batch

            for br in batch_results:
                if isinstance(br, Exception):
                    logger.error(f"Error processing result: {br}")
                else:
                    doc_id, snippet_count = br
                    total_documents += 1
                    total_snippets += snippet_count

        return total_documents, total_snippets

    def _create_or_update_document(
        self,
        session: Session,
        result: Any,  # CrawlResult
        job_id: str,
        depth: int,
        existing_doc: Document | None = None,
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
            # NOTE: Old snippets will be deleted later, after successful extraction
            # This prevents data loss if extraction fails

            # Update existing
            doc = existing_doc
            doc.title = result.title
            doc.content_hash = result.content_hash
            doc.markdown_content = remove_markdown_links(result.content)
            doc.crawl_job_id = job_id
            doc.last_crawled = datetime.utcnow()
        else:
            # Create new
            doc = Document(
                url=result.url,
                title=result.title,
                content_hash=result.content_hash,
                markdown_content=remove_markdown_links(result.content),
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
            # Check if name was already detected (stored in config)
            if job.config.get('name_detected'):
                logger.debug(f"Name already detected for job {job_id}, skipping")
                return

            # Extract name from first page
            detected_name = await self._extract_site_name(result.title, result.url, result.metadata, result.content)
            if detected_name:
                logger.info(f"Auto-detected site name: {detected_name}")
                job.name = detected_name
                # Mark as detected to avoid future updates
                job.config['name_detected'] = True
                session.commit()

    async def _extract_site_name(
        self, title: str, url: str, metadata: dict[str, Any] | None = None,
        content: str | None = None
    ) -> str | None:
        """Extract site name using LLM or fallback logic.

        Args:
            title: Page title
            url: Page URL
            metadata: Optional metadata
            content: Optional page content for LLM analysis

        Returns:
            Site name or None
        """
        if not title and not metadata:
            return None

        # First try Open Graph metadata
        if metadata:
            # Check for og:site_name first
            og_site_name = metadata.get('og:site_name')
            if og_site_name and len(og_site_name) <= 50:
                logger.info(f"Using og:site_name: {og_site_name}")
                return og_site_name.strip()

            # Check for application-name meta tag
            app_name = metadata.get('application-name')
            if app_name and len(app_name) <= 50:
                logger.info(f"Using application-name: {app_name}")
                return app_name.strip()

            # Check for twitter:site
            twitter_site = metadata.get('twitter:site')
            if twitter_site and len(twitter_site) <= 50:
                # Remove @ if present
                if twitter_site.startswith('@'):
                    twitter_site = twitter_site[1:]
                logger.info(f"Using twitter:site: {twitter_site}")
                return twitter_site.strip()

        # Try LLM extraction if available
        if self.settings.code_extraction.llm_api_key and (title or content):
            try:
                from .llm_retry import LLMDescriptionGenerator
                llm_generator = LLMDescriptionGenerator()

                if llm_generator.client:
                    # Create a focused prompt for name extraction
                    prompt = f"""Extract the library/framework name from this documentation page.

Page Title: {title or 'N/A'}
URL: {url}
Metadata: {str(metadata)[:500] if metadata else 'N/A'}

Respond with ONLY the library/framework name (e.g., "React", "Next.js", "Django", ".NET").
Do not include words like "Documentation", "Docs", "Guide", etc.
If you cannot determine the name, respond with "UNKNOWN"."""

                    response = await llm_generator.client.chat.completions.create(
                        model=self.settings.code_extraction.llm_extraction_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=50
                    )

                    extracted_name = response.choices[0].message.content.strip()
                    if extracted_name and extracted_name != "UNKNOWN" and len(extracted_name) <= 50:
                        logger.info(f"LLM extracted name: {extracted_name}")
                        return extracted_name
            except Exception as e:
                logger.warning(f"LLM name extraction failed: {e}")

        # Fallback to simple extraction logic
        if title:
            clean_title = title

            # Clean common suffixes
            suffixes_to_remove = [
                " Documentation", " Docs", " | Home", " - Official Site",
                " - Home", " Reference", " API Reference", " Developer Guide",
                " · GitBook", " | MDN", " - MDN Web Docs"
            ]
            for suffix in suffixes_to_remove:
                if clean_title.endswith(suffix):
                    clean_title = clean_title[:-len(suffix)]
                    break

            # Handle pipe-separated titles
            if " | " in clean_title:
                parts = clean_title.split(" | ")
                # Try different strategies
                # 1. If first part is short and looks like a library name
                if len(parts[0]) <= 30 and not any(word in parts[0].lower() for word in ['documentation', 'docs', 'guide']):
                    clean_title = parts[0].strip()
                # 2. Otherwise use the last part
                else:
                    clean_title = parts[-1].strip()

            # Handle dash-separated titles
            elif " - " in clean_title:
                parts = clean_title.split(" - ")
                # Similar logic
                if len(parts[0]) <= 30 and not any(word in parts[0].lower() for word in ['documentation', 'docs', 'guide']):
                    clean_title = parts[0].strip()

            # Remove version numbers at the end
            import re
            clean_title = re.sub(r'\s+v?\d+(\.\d+)*$', '', clean_title)

            # Truncate long titles
            if len(clean_title) > 50:
                return clean_title[:50].rsplit(" ", 1)[0] + "..."

            return clean_title.strip()

        return None


# Improved _process_code_blocks method with better deduplication tracking

    async def _process_code_blocks(
        self, session: Session, doc: Document, code_blocks: list[Any], source_url: str
    ) -> int:
        """Process code blocks and store directly.

        Args:
            session: Database session
            doc: Document instance
            code_blocks: List of code blocks
            source_url: Source URL

        Returns:
            Number of NEW unique snippets created (not including duplicates)
        """
        new_snippet_count = 0
        duplicate_count = 0
        updated_count = 0
        skipped_count = 0

        logger.info(f"Processing {len(code_blocks)} code blocks for document {doc.url}")

        # First, extract all block data and prepare for concurrent formatting
        blocks_to_format = []

        for i, block in enumerate(code_blocks):
            # Debug log the block structure
            logger.debug(f"Processing block {i}: type={type(block)}, has_dict_methods={hasattr(block, 'get')}")

            # Handle both dict (from LLM) and object (from default) formats
            if isinstance(block, dict):
                content = block.get('code', '')
                language = block.get('language', 'text')
                title = block.get('title', '')
                description = block.get('description', '')
                metadata = block.get('metadata', {})
                filename = block.get('filename')
            else:
                # Handle object format - check what attributes it has
                logger.debug(f"Block is object type, checking attributes: {dir(block)}")
                content = getattr(block, 'code', '')
                language = getattr(block, 'language', 'text')
                title = getattr(block, 'title', '')
                description = getattr(block, 'description', '')
                metadata = getattr(block, 'metadata', {})
                filename = getattr(block, 'filename', None)

            # Skip empty code blocks
            if not content:
                logger.warning(f"Skipping empty code block {i} with title: {title}")
                skipped_count += 1
                continue

            # Add to blocks to format
            blocks_to_format.append({
                'index': i,
                'content': content,
                'language': language,
                'title': title,
                'description': description,
                'metadata': metadata,
                'filename': filename
            })

        # No formatting - use original content
        processed_blocks = blocks_to_format

        # Now process all formatted blocks
        import hashlib

        for block_data in processed_blocks:
            content = block_data['content']
            title = block_data['title']
            description = block_data['description']
            language = block_data['language']
            metadata = block_data['metadata']
            filename = block_data['filename']

            # Calculate hash for deduplication
            code_hash = hashlib.md5(content.encode()).hexdigest()

            # Map purpose to snippet_type
            purpose = metadata.get('purpose', 'code')
            snippet_type_map = {
                'example': 'example',
                'configuration': 'config',
                'api_reference': 'code',
                'tutorial': 'example',
                'utility': 'function',
                'test': 'code'
            }
            snippet_type = snippet_type_map.get(purpose, 'code')

            # Build simplified metadata
            full_metadata = {
                'filename': filename,
                'extraction_method': metadata.get('extraction_method'),
            }

            # Create snippet with all LLM data
            snippet = CodeSnippet(
                document_id=doc.id,
                title=title,
                description=description,
                language=language,
                code_content=content,
                code_hash=code_hash,
                line_start=None,
                line_end=None,
                context_before=None,
                context_after=None,
                section_title=metadata.get('section'),
                section_content=None,
                functions=[],
                imports=[],
                keywords=[],
                snippet_type=snippet_type,
                source_url=source_url,
                metadata=full_metadata,
            )

            # Check for duplicate across entire database
            existing = session.query(CodeSnippet).filter_by(code_hash=snippet.code_hash).first()

            if not existing:
                session.add(snippet)
                session.flush()  # Flush to get the ID
                new_snippet_count += 1
                logger.debug(f"Added unique snippet: {title} (language: {language})")
            else:
                # Check if it's from the same document or different
                if existing.document_id == doc.id:
                    # Same document - this shouldn't happen normally
                    duplicate_count += 1
                    logger.debug(f"Found duplicate in same document: {title}")
                else:
                    # Different document - update metadata
                    self._update_snippet(existing, snippet)
                    updated_count += 1
                    session.query(Document).filter_by(id=existing.document_id).first()
                    logger.debug(f"Updated existing snippet: {title}")

        # Commit snippets
        session.commit()

        # Log comprehensive statistics
        len(processed_blocks)
        logger.debug(f"Processed {len(code_blocks)} blocks for document {doc.id}: {new_snippet_count} new, {updated_count} updated, {duplicate_count} duplicates")

        return new_snippet_count


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



