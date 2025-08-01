"""Upload processor for handling user-uploaded documentation files."""

import asyncio
import logging
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import os

from ..config import get_settings
from ..database import Document, CodeSnippet, UploadJob, get_db_manager
from .markdown_code_extractor import MarkdownCodeExtractor
from .html_code_extractor import HTMLCodeExtractor
from .llm_retry import LLMDescriptionGenerator
from .result_processor import ResultProcessor
from .progress_tracker import ProgressTracker
from .extraction_models import SimpleCodeBlock

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class UploadConfig:
    """Configuration for an upload job."""
    name: str
    files: List[Dict[str, Any]]  # List of {path, content, source_url}
    metadata: Dict[str, Any] = field(default_factory=dict)
    extract_code_only: bool = True
    use_llm: bool = True


@dataclass
class UploadResult:
    """Result from processing an uploaded file."""
    source_url: str
    title: str
    content_hash: str
    code_blocks: List[SimpleCodeBlock]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UploadProcessor:
    """Processes uploaded documentation files."""
    
    def __init__(self):
        """Initialize the upload processor."""
        self.settings = settings
        self.db_manager = get_db_manager()
        self.markdown_extractor = MarkdownCodeExtractor()
        self.html_extractor = HTMLCodeExtractor()
        self.result_processor = ResultProcessor()
        self.progress_tracker = ProgressTracker(self)
        
        # Initialize LLM generator if API key is available
        self.description_generator = None
        if self.settings.code_extraction.llm_api_key:
            self.description_generator = LLMDescriptionGenerator()
    
    async def process_upload(self, config: UploadConfig, user_id: Optional[str] = None) -> str:
        """
        Process an upload job.
        
        Args:
            config: Upload configuration
            user_id: User identifier
            
        Returns:
            Job ID
        """
        # Create upload job
        job_id = self._create_upload_job(config, user_id)
        
        # Start async processing
        asyncio.create_task(self._execute_upload(job_id, config))
        
        return job_id
    
    def _create_upload_job(self, config: UploadConfig, user_id: Optional[str] = None) -> str:
        """Create a new upload job in the database."""
        from ..database import UploadJob
        import uuid
        
        with self.db_manager.session_scope() as session:
            job = UploadJob(
                id=str(uuid.uuid4()),
                name=config.name,
                file_count=len(config.files),
                status='running',
                config=config.metadata,
                created_by=user_id
            )
            session.add(job)
            session.commit()
            
            return job.id
    
    async def _execute_upload(self, job_id: str, config: UploadConfig) -> None:
        """Execute the upload job."""
        try:
            # Start tracking
            await self.progress_tracker.start_tracking(job_id)
            
            total_snippets = 0
            processed_files = 0
            
            # Process each file
            for file_info in config.files:
                # Extract code blocks
                result = await self._process_file(
                    file_info['content'],
                    file_info['source_url'],
                    file_info.get('content_type', 'markdown')
                )
                
                if result.error:
                    logger.error(f"Failed to process {file_info['source_url']}: {result.error}")
                    continue
                
                # Generate LLM descriptions if enabled
                if config.use_llm and self.description_generator and result.code_blocks:
                    try:
                        result.code_blocks = await self.description_generator.generate_titles_and_descriptions_batch(
                            result.code_blocks,
                            result.source_url,
                            max_concurrent=5
                        )
                    except Exception as e:
                        logger.warning(f"LLM description generation failed: {e}")
                
                # Store in database
                doc_id, snippet_count = await self._store_result(result, job_id)
                
                total_snippets += snippet_count
                processed_files += 1
                
                # Update progress
                await self.progress_tracker.update_progress(
                    job_id,
                    processed_pages=processed_files,
                    total_pages=len(config.files),
                    snippets_extracted=total_snippets,
                    documents_crawled=processed_files,
                    send_notification=True
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
            # Calculate content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Extract title from content or URL
            title = self._extract_title(content, source_url)
            
            # Extract code blocks based on content type
            if content_type == 'html':
                # Convert HTML to BeautifulSoup and extract
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                extracted_blocks = self.html_extractor.extract_code_blocks(soup, source_url)
                
                # Convert to SimpleCodeBlock format
                code_blocks = []
                for block in extracted_blocks:
                    simple_block = SimpleCodeBlock(
                        code=block.code,
                        language=block.language,
                        title=block.title,
                        description=block.description,
                        context_before=block.context_before,
                        context_after=block.context_after,
                        metadata={
                            'container_type': block.container_type,
                            'extraction_method': 'html'
                        }
                    )
                    code_blocks.append(simple_block)
            else:
                # Default to markdown extraction
                code_blocks = self.markdown_extractor.extract_code_blocks(content, source_url)
            
            return UploadResult(
                source_url=source_url,
                title=title,
                content_hash=content_hash,
                code_blocks=code_blocks,
                metadata={'content_type': content_type}
            )
            
        except Exception as e:
            logger.error(f"Failed to process file {source_url}: {e}")
            return UploadResult(
                source_url=source_url,
                title="Unknown",
                content_hash="",
                code_blocks=[],
                error=str(e)
            )
    
    def update_job_progress(self, job_id: str, **kwargs) -> bool:
        """Update upload job progress (compatible with ProgressTracker)."""
        try:
            with self.db_manager.session_scope() as session:
                job = session.query(UploadJob).filter_by(id=job_id).first()
                if not job:
                    return False
                
                # Update fields if provided
                if 'processed_pages' in kwargs:
                    job.processed_files = kwargs['processed_pages']
                if 'snippets_extracted' in kwargs:
                    job.snippets_extracted = kwargs['snippets_extracted']
                
                job.updated_at = datetime.utcnow()
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
            return False
    
    def _extract_title(self, content: str, source_url: str) -> str:
        """Extract title from content or use filename."""
        # Try to extract from first heading
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            if line.startswith('# '):
                return line[2:].strip()
        
        # Use filename from source URL
        if source_url.startswith('file://'):
            filename = os.path.basename(source_url[7:])
            return filename
        
        return "Untitled Document"
    
    async def _store_result(self, result: UploadResult, job_id: str) -> Tuple[int, int]:
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
                doc.upload_job_id = job_id
                doc.last_crawled = datetime.utcnow()
            else:
                # Create new document linked to upload job
                doc = Document(
                    url=result.source_url,
                    title=result.title,
                    content_hash=result.content_hash,
                    upload_job_id=job_id,  # Link to upload job instead of crawl job
                    source_type='upload',  # Mark as upload source
                    crawl_depth=0,
                    meta_data=result.metadata
                )
                session.add(doc)
            
            session.flush()  # Get doc.id
            
            # Process code blocks
            if result.code_blocks:
                # Convert SimpleCodeBlock to format expected by result processor
                from dataclasses import asdict
                code_blocks_data = []
                for block in result.code_blocks:
                    block_dict = {
                        'code': block.code,
                        'language': block.language,
                        'title': block.title or f"Code Block in {block.language or 'Unknown'}",
                        'description': block.description or f"Code block from {result.title}",
                        'metadata': block.metadata or {},
                        'filename': None
                    }
                    code_blocks_data.append(block_dict)
                
                # Use result processor to store snippets
                snippet_count = await self.result_processor._process_code_blocks(
                    session, doc, code_blocks_data, result.source_url
                )
            
            session.commit()
            return int(doc.id), snippet_count
    
    def _complete_job(self, job_id: str, success: bool, error_message: Optional[str] = None, 
                      snippets_extracted: int = 0) -> None:
        """Mark upload job as completed."""
        from ..database import UploadJob
        
        with self.db_manager.session_scope() as session:
            job = session.query(UploadJob).filter_by(id=job_id).first()
            if job:
                job.status = 'completed' if success else 'failed'
                job.completed_at = datetime.utcnow()
                job.error_message = error_message
                job.snippets_extracted = snippets_extracted
                session.commit()
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
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