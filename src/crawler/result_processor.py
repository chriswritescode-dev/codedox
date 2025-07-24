"""Process crawl results and store in database."""

import logging
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from ..database import Document, CodeSnippet, get_db_manager
from ..config import get_settings

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Processes crawl results and stores them in the database."""

    def __init__(self):
        """Initialize result processor."""
        self.db_manager = get_db_manager()
        self.settings = get_settings()

    async def process_result_pipeline(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> Tuple[int, int]:
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

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content unchanged
                return int(existing_doc.id), 0

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            session.commit()

            doc_id = int(doc.id)

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

            # Process code blocks directly
            if result.code_blocks:
                snippet_count = await self._process_code_blocks(
                    session, doc, result.code_blocks, result.url
                )

            session.commit()

            return doc_id, snippet_count

    async def process_result(
        self, result: Any, job_id: str, depth: int  # CrawlResult
    ) -> Tuple[int, int]:
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

            if existing_doc and existing_doc.content_hash == result.content_hash:
                # Content unchanged - check if this was detected during crawl
                if hasattr(result, 'metadata') and result.metadata.get('content_unchanged'):
                    # Return with existing snippet count from crawl phase
                    existing_snippet_count = result.metadata.get('existing_snippet_count', 0)
                    return int(existing_doc.id), existing_snippet_count, None
                else:
                    # Legacy path - content unchanged but not detected during crawl
                    return int(existing_doc.id), 0, None

            # Create or update document
            doc = self._create_or_update_document(session, result, job_id, depth, existing_doc)
            session.commit()

            # Check for auto-detect name
            await self._check_auto_detect_name(session, job_id, result)

            # Process code blocks
            if result.code_blocks:
                snippet_count = await self._process_code_blocks(
                    session, doc, result.code_blocks, result.url
                )

            session.commit()
            return int(doc.id), snippet_count

    async def process_batch(
        self, results: List[Any], job_id: str, use_pipeline: bool = True  # List[CrawlResult]
    ) -> Tuple[int, int]:
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

        # Simple extraction logic
        if metadata and "title" in metadata:
            meta_title = metadata["title"]
            if meta_title and len(meta_title) <= 50:
                return meta_title.strip()

        # Clean common suffixes
        clean_title = title
        for suffix in [" Documentation", " Docs", " | Home", " - Official Site"]:
            if clean_title.endswith(suffix):
                clean_title = clean_title[:-len(suffix)]
                break
        
        # Handle pipe-separated titles
        if " | " in clean_title:
            parts = clean_title.split(" | ")
            # Usually the library name is the last part
            clean_title = parts[-1].strip()
        
        # Truncate long titles
        if len(clean_title) > 50:
            return clean_title[:50].rsplit(" ", 1)[0] + "..."
        return clean_title.strip()

    async def _process_code_blocks(
        self, session: Session, doc: Document, code_blocks: List[Any], source_url: str
    ) -> int:
        """Process code blocks and store directly.

        Args:
            session: Database session
            doc: Document instance
            code_blocks: List of code blocks
            source_url: Source URL

        Returns:
            Number of snippets created
        """
        snippet_count = 0
        created_snippets = []  # Track created snippets for relationship mapping
        
        logger.info(f"Processing {len(code_blocks)} code blocks for document {doc.url}")

        # Process blocks directly
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
                continue
                
            # Calculate hash for deduplication
            import hashlib
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
            
            # Build comprehensive metadata
            full_metadata = {
                'filename': filename,
                'purpose': purpose,
                'frameworks': metadata.get('frameworks', []),
                'prerequisites': metadata.get('prerequisites', []),
                'relationships': metadata.get('relationships', []),
                'extraction_model': metadata.get('extraction_model'),
                'extraction_timestamp': metadata.get('extraction_timestamp'),
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
                functions=metadata.get('dependencies', []),  # Store dependencies in functions field
                imports=[],  # Could extract from relationships
                keywords=metadata.get('keywords', []),
                snippet_type=snippet_type,
                source_url=source_url,
                metadata=full_metadata,
            )

            # Check for duplicate
            existing = session.query(CodeSnippet).filter_by(code_hash=snippet.code_hash).first()

            if not existing:
                session.add(snippet)
                session.flush()  # Flush to get the ID
                created_snippets.append((i, snippet))  # Track index and snippet
                snippet_count += 1
                logger.info(f"Added new snippet: {title} (language: {language})")
            else:
                # Update existing with new data
                self._update_snippet(existing, snippet)
                created_snippets.append((i, existing))  # Track existing snippet too
                logger.info(f"Updated existing snippet: {title}")
        
        # Commit snippets first before creating relationships
        session.commit()
        
        # Process relationships after all snippets are created and committed
        self._create_snippet_relationships(session, created_snippets, code_blocks)
        
        logger.info(f"Processed {snippet_count} new snippets for document {doc.id}")

        return snippet_count


    def _create_snippet_relationships(
        self, session: Session, created_snippets: List[Tuple[int, CodeSnippet]], code_blocks: List[Any]
    ) -> None:
        """Create relationships between snippets based on LLM extraction.
        
        Args:
            session: Database session
            created_snippets: List of (index, snippet) tuples
            code_blocks: Original code blocks with relationship data
        """
        from ..database.models import SnippetRelationship
        
        # Create a mapping of index to snippet
        index_to_snippet = {idx: snippet for idx, snippet in created_snippets}
        
        # Track relationships to avoid duplicates
        created_relationships = set()
        
        # Process each snippet's relationships
        for idx, snippet in created_snippets:
            if idx >= len(code_blocks):
                continue
                
            block = code_blocks[idx]
            
            # Get relationships from metadata
            relationships = []
            if isinstance(block, dict) and 'relationships' in block:
                relationships = block.get('relationships', [])
            elif isinstance(block, dict) and 'metadata' in block:
                relationships = block['metadata'].get('relationships', [])
            elif hasattr(block, 'metadata') and block.metadata:
                relationships = block.metadata.get('relationships', [])
            
            # Create relationship records
            for rel in relationships:
                target_idx = rel.get('related_index')
                if target_idx is not None and target_idx in index_to_snippet:
                    target_snippet = index_to_snippet[target_idx]
                    
                    # Validate that both snippets have valid IDs
                    if snippet.id is None or target_snippet.id is None:
                        logger.warning(f"Skipping relationship creation - snippet IDs are None: source={snippet.id}, target={target_snippet.id}")
                        continue
                    
                    relationship_type = rel.get('relationship_type', 'related')
                    
                    # Create a unique key for this relationship
                    relationship_key = (snippet.id, target_snippet.id, relationship_type)
                    
                    # Skip if we've already processed this relationship
                    if relationship_key in created_relationships:
                        logger.debug(f"Skipping duplicate relationship: {snippet.title} -> {target_snippet.title} ({relationship_type})")
                        continue
                    
                    # Check if relationship already exists in database
                    existing_rel = session.query(SnippetRelationship).filter_by(
                        source_snippet_id=snippet.id,
                        target_snippet_id=target_snippet.id,
                        relationship_type=relationship_type
                    ).first()
                    
                    if not existing_rel:
                        relationship = SnippetRelationship(
                            source_snippet_id=snippet.id,
                            target_snippet_id=target_snippet.id,
                            relationship_type=relationship_type,
                            description=rel.get('description', '')
                        )
                        session.add(relationship)
                        created_relationships.add(relationship_key)
                        logger.debug(f"Created relationship: {snippet.title} -> {target_snippet.title} ({relationship_type})")
                    else:
                        created_relationships.add(relationship_key)
                        logger.debug(f"Relationship already exists: {snippet.title} -> {target_snippet.title} ({relationship_type})")
        
        # Commit relationships separately to handle any remaining conflicts
        try:
            session.commit()
            logger.debug(f"Successfully committed {len(created_relationships)} relationships")
        except Exception as e:
            logger.error(f"Error committing relationships: {e}")
            session.rollback()
            # Try to create relationships one by one to identify which ones are causing issues
            for idx, snippet in created_snippets:
                if idx >= len(code_blocks):
                    continue
                    
                block = code_blocks[idx]
                relationships = []
                if isinstance(block, dict) and 'relationships' in block:
                    relationships = block.get('relationships', [])
                elif isinstance(block, dict) and 'metadata' in block:
                    relationships = block['metadata'].get('relationships', [])
                elif hasattr(block, 'metadata') and block.metadata:
                    relationships = block.metadata.get('relationships', [])
                
                for rel in relationships:
                    target_idx = rel.get('related_index')
                    if target_idx is not None and target_idx in index_to_snippet:
                        target_snippet = index_to_snippet[target_idx]
                        relationship_type = rel.get('relationship_type', 'related')
                        
                        try:
                            # Use raw SQL with ON CONFLICT DO NOTHING
                            session.execute(
                                """
                                INSERT INTO snippet_relationships 
                                (source_snippet_id, target_snippet_id, relationship_type, description, created_at)
                                VALUES (:source_id, :target_id, :rel_type, :description, NOW())
                                ON CONFLICT (source_snippet_id, target_snippet_id, relationship_type) DO NOTHING
                                """,
                                {
                                    'source_id': snippet.id,
                                    'target_id': target_snippet.id,
                                    'rel_type': relationship_type,
                                    'description': rel.get('description', '')
                                }
                            )
                            session.commit()
                        except Exception as inner_e:
                            logger.error(f"Failed to create individual relationship: {inner_e}")
                            session.rollback()

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



