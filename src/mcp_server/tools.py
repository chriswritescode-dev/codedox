"""MCP tool implementations."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..config import get_settings
from ..database import get_db_manager, CodeSearcher
from ..crawler import CrawlManager, CrawlConfig

logger = logging.getLogger(__name__)
settings = get_settings()


class MCPTools:
    """Implementation of MCP tools for code extraction."""
    
    def __init__(self) -> None:
        """Initialize MCP tools."""
        self.db_manager = get_db_manager()
        self.crawl_manager = CrawlManager()
    
    async def init_crawl(
        self,
        name: Optional[str],
        start_urls: List[str],
        max_depth: int = 1,
        domain_filter: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize a new crawl job.
        
        Args:
            name: Library/framework name (auto-detected if not provided)
            start_urls: URLs to start crawling
            max_depth: Maximum crawl depth (0-3)
            domain_filter: Optional domain restriction
            metadata: Additional metadata
            
        Returns:
            Job initialization result
        """
        try:
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            # Generate temporary name if not provided
            if not name:
                from urllib.parse import urlparse
                parsed = urlparse(start_urls[0])
                domain = parsed.netloc.replace('www.', '')
                name = f"[Auto-detecting from {domain}]"
                metadata['auto_detect_name'] = True
            
            metadata.update({
                'library_name': name,
                'initiated_via': 'mcp',
                'initiated_at': datetime.utcnow().isoformat()
            })
            
            # Prepare domain restrictions
            domain_restrictions = []
            if domain_filter:
                domain_restrictions = [domain_filter]
            else:
                # Extract domains from start URLs
                from urllib.parse import urlparse
                for url in start_urls:
                    parsed = urlparse(url)
                    if parsed.netloc:
                        domain_restrictions.append(parsed.netloc)
            
            # Warn about deep crawls
            if max_depth > 1:
                logger.warning(f"Deep crawl requested with depth={max_depth}. This may take several minutes.")
            
            # Create crawl configuration
            config = CrawlConfig(
                name=name,
                start_urls=start_urls,
                max_depth=max_depth,
                domain_restrictions=domain_restrictions,
                metadata=metadata,
                max_pages=settings.crawling.max_pages_per_job
            )
            
            # Start crawl job
            job_id = await self.crawl_manager.start_crawl(config)
            
            return {
                "job_id": job_id,
                "status": "started",
                "library_name": name,
                "message": f"Crawl job initiated with {len(start_urls)} URLs at depth {max_depth}",
                "start_urls": start_urls,
                "max_depth": max_depth,
                "domain_restrictions": domain_restrictions,
                "auto_detect_name": metadata.get('auto_detect_name', False)
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize crawl: {e}")
            return {
                "error": str(e),
                "status": "failed",
                "library_name": name
            }
    
    async def get_sources(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of available sources/libraries.
        
        Args:
            job_id: Optional job ID to filter by
            
        Returns:
            List of source information
        """
        try:
            with self.db_manager.session_scope() as session:
                searcher = CodeSearcher(session)
                sources = searcher.get_sources(job_id=job_id)
                
                # Format sources for MCP output
                formatted_sources = []
                for source in sources:
                    formatted_source = {
                        "id": source['id'],  # Always include ID
                        "name": source['name'],
                        "repository": source.get('repository', ''),
                        "description": source.get('description', 'No description available'),
                        "status": source['status'],
                        "tokens": source['tokens'],
                        "snippets": source['snippet_count'],
                        "last_update": source.get('last_update_relative', 'Never')
                    }
                    
                    # Add additional job details if requested
                    if job_id:
                        formatted_source.update({
                            "job_id": source['id'],
                            "document_count": source['document_count'],
                            "last_update_iso": source.get('last_update')
                        })
                    
                    formatted_sources.append(formatted_source)
                
                return formatted_sources
                
        except Exception as e:
            logger.error(f"Failed to get sources: {e}")
            return [{
                "error": str(e),
                "message": "Failed to retrieve sources"
            }]
    
    async def search_content(
        self,
        query: str,
        source: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Search for content across all sources or in a specific source.
        
        Args:
            query: Search query
            source: Optional library/source name to filter by
            language: Optional language filter
            max_results: Maximum results to return
            
        Returns:
            Formatted search results as string
        """
        try:
            with self.db_manager.session_scope() as session:
                searcher = CodeSearcher(session)
                
                # Search with optional source filter
                snippets, total_count = searcher.search(
                    query=query,
                    source=source,
                    language=language,
                    limit=max_results,
                    include_context=False  # Don't include context in search results
                )
                
                if not snippets:
                    no_results_msg = f"No results found for query '{query}'"
                    if source:
                        no_results_msg += f" in source '{source}'"
                    if language:
                        no_results_msg += f" with language filter '{language}'"
                    return no_results_msg
                
                # Format results using the specified format
                formatted_results = searcher.format_search_results(snippets)
                
                # Add summary header
                header = f"Found {len(snippets)} results"
                if total_count > len(snippets):
                    header += f" (showing first {len(snippets)} of {total_count} total)"
                header += f" for query '{query}'"
                if source:
                    header += f" in {source}"
                if language:
                    header += f" (language: {language})"
                header += "\n\n"
                
                return header + formatted_results
                
        except Exception as e:
            logger.error(f"Failed to search content: {e}")
            return f"Error searching content: {str(e)}"
    
    async def get_crawl_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific crawl job.
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Job status information
        """
        try:
            status = self.crawl_manager.get_job_status(job_id)
            
            if not status:
                return {
                    "error": "Job not found",
                    "job_id": job_id
                }
            
            # Calculate progress percentage
            progress = 0
            if status['total_pages'] > 0:
                progress = int((status['processed_pages'] / status['total_pages']) * 100)
            
            result = {
                "job_id": job_id,
                "name": status['name'],
                "status": status['status'],
                "progress": f"{progress}%",
                "processed_pages": status['processed_pages'],  # Fixed key name
                "total_pages": status['total_pages'],
                "snippets_extracted": status['snippets_extracted'],
                "started_at": status['started_at'],
                "completed_at": status['completed_at']
            }
            
            # Add error message if present
            if status.get('error_message'):
                result['error_message'] = status['error_message']
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get crawl status: {e}")
            return {
                "error": str(e),
                "job_id": job_id
            }
    
    async def cancel_crawl(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running crawl job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            Cancellation result
        """
        try:
            success = await self.crawl_manager.cancel_job(job_id)
            
            if success:
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                    "message": "Crawl job cancelled successfully"
                }
            else:
                return {
                    "error": "Failed to cancel job",
                    "job_id": job_id,
                    "message": "Job may have already completed or does not exist"
                }
                
        except Exception as e:
            logger.error(f"Failed to cancel crawl: {e}")
            return {
                "error": str(e),
                "job_id": job_id
            }
    
    async def get_snippet_details(self, snippet_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific code snippet.
        
        Args:
            snippet_id: Snippet ID
            
        Returns:
            Detailed snippet information
        """
        try:
            with self.db_manager.session_scope() as session:
                from ..database.models import CodeSnippet, Document
                
                snippet = session.query(CodeSnippet).filter_by(id=snippet_id).first()
                
                if not snippet:
                    return {
                        "error": "Snippet not found",
                        "snippet_id": snippet_id
                    }
                
                # Get document information
                document = snippet.document
                
                result = {
                    "id": snippet.id,
                    "title": snippet.title or "Untitled",
                    "description": snippet.description or "No description",
                    "language": snippet.language,
                    "source_url": snippet.source_url,
                    "code": snippet.code_content,
                    "line_start": snippet.line_start,
                    "line_end": snippet.line_end,
                    "functions": snippet.functions or [],
                    "imports": snippet.imports or [],
                    "keywords": snippet.keywords or [],
                    "snippet_type": snippet.snippet_type,
                    "context_before": snippet.context_before,
                    "context_after": snippet.context_after,
                    "section_title": snippet.section_title,
                    "section_content": snippet.section_content,
                    "related_snippets": snippet.related_snippets or [],
                    "metadata": snippet.meta_data or {},
                    "created_at": snippet.created_at.isoformat(),
                    "updated_at": snippet.updated_at.isoformat() if snippet.updated_at else None
                }
                
                # Add document information if available
                if document:
                    result["document"] = {
                        "id": document.id,
                        "url": document.url,
                        "title": document.title,
                        "crawl_depth": document.crawl_depth,
                        "parent_url": document.parent_url,
                        "last_crawled": document.last_crawled.isoformat() if document.last_crawled else None,
                        "markdown_content": document.markdown_content
                    }
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to get snippet details: {e}")
            return {
                "error": str(e),
                "snippet_id": snippet_id
            }