"""PostgreSQL full-text search implementation."""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import Session

from .models import CodeSnippet, Document, CrawlJob
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CodeSearcher:
    """Handles full-text search operations for code snippets."""
    
    def __init__(self, session: Session):
        """Initialize searcher with database session."""
        self.session = session
        self.settings = settings.search
    
    def search(
        self,
        query: Optional[str] = None,
        source: Optional[str] = None,
        language: Optional[str] = None,
        job_id: Optional[str] = None,
        snippet_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_context: bool = True
    ) -> Tuple[List[CodeSnippet], int]:
        """Search code snippets with various filters.
        
        Args:
            query: Text search query
            source: Filter by source URL pattern
            language: Filter by programming language
            job_id: Filter by crawl job ID
            snippet_type: Filter by snippet type (function, class, etc.)
            limit: Maximum results to return
            offset: Pagination offset
            include_context: Whether to include context fields
            
        Returns:
            Tuple of (results, total_count)
        """
        limit = limit or self.settings.default_max_results
        
        # For full-text search, use raw SQL to leverage the generated search_vector column
        if query:
            # Build SQL query with all filters
            sql_parts = ["SELECT cs.id"]
            sql_parts.append("FROM code_snippets cs")
            
            where_clauses = ["cs.search_vector @@ plainto_tsquery(:query)"]
            params = {'query': query}
            
            # Always join with documents and crawl_jobs to filter out cancelled jobs
            sql_parts.append("JOIN documents d ON cs.document_id = d.id")
            sql_parts.append("JOIN crawl_jobs cj ON d.crawl_job_id = cj.id")
            
            # Always exclude cancelled jobs
            where_clauses.append("cj.status != 'cancelled'")
            
            if job_id:
                where_clauses.append("d.crawl_job_id = :job_id")
                params['job_id'] = job_id
            
            # Add source filter by name
            if source:
                where_clauses.append("cj.name = :source")
                params['source'] = source
            
            if language:
                where_clauses.append("cs.language = :language")
                params['language'] = language.lower()
            
            if snippet_type:
                where_clauses.append("cs.snippet_type = :snippet_type")
                params['snippet_type'] = snippet_type
            
            # Combine query
            sql_parts.append("WHERE " + " AND ".join(where_clauses))
            sql_parts.append("ORDER BY ts_rank(cs.search_vector, plainto_tsquery(:query)) DESC")
            sql_parts.append("LIMIT :limit OFFSET :offset")
            
            params['limit'] = limit
            params['offset'] = offset
            
            # Execute query
            sql = " ".join(sql_parts)
            result = self.session.execute(text(sql), params)
            
            # Get count
            count_sql = sql.replace("SELECT cs.id", "SELECT COUNT(*)")
            count_sql = count_sql.split("ORDER BY")[0]  # Remove ORDER BY and LIMIT
            total_count = int(self.session.execute(text(count_sql), {k: v for k, v in params.items() if k not in ['limit', 'offset']}).scalar() or 0)
            
            # Convert results to CodeSnippet objects
            results = []
            for row in result:
                snippet = self.session.query(CodeSnippet).filter(CodeSnippet.id == row.id).first()
                if snippet and not include_context:
                    snippet.context_before = ""  # Clear context
                    snippet.context_after = ""  # Clear context
                if snippet:
                    results.append(snippet)
            
            return results, total_count
        else:
            # Non-text search - use regular SQLAlchemy query
            base_query = self.session.query(CodeSnippet)
            filters = []
            
            # Always join with Document and CrawlJob to filter out cancelled jobs
            base_query = base_query.join(Document).join(CrawlJob)
            filters.append(CrawlJob.status != 'cancelled')
            
            if source:
                filters.append(CrawlJob.name == source)
            if job_id:
                filters.append(Document.crawl_job_id == job_id)
            
            if language:
                filters.append(CodeSnippet.language == language.lower())
            
            if snippet_type:
                filters.append(CodeSnippet.snippet_type == snippet_type)
            
            if filters:
                base_query = base_query.filter(and_(*filters))
            
            total_count = base_query.count()
            
            results = base_query.order_by(
                CodeSnippet.created_at.desc()
            ).offset(offset).limit(limit).all()
            
            if not include_context:
                for snippet in results:
                    snippet.context_before = ""  # Clear context
                    snippet.context_after = ""  # Clear context
            
            return results, total_count
    
    def search_by_function(self, function_name: str, limit: Optional[int] = None) -> List[CodeSnippet]:
        """Search for snippets containing specific function names.
        
        Args:
            function_name: Function name to search for
            limit: Maximum results
            
        Returns:
            List of matching snippets
        """
        limit = limit or self.settings.default_max_results
        
        results = self.session.query(CodeSnippet).join(Document).join(CrawlJob).filter(
            CodeSnippet.functions.contains([function_name]),
            CrawlJob.status != 'cancelled'
        ).limit(limit).all()
        
        return results
    
    def search_by_import(self, import_name: str, limit: Optional[int] = None) -> List[CodeSnippet]:
        """Search for snippets with specific imports.
        
        Args:
            import_name: Import to search for
            limit: Maximum results
            
        Returns:
            List of matching snippets
        """
        limit = limit or self.settings.default_max_results
        
        results = self.session.query(CodeSnippet).join(Document).join(CrawlJob).filter(
            CodeSnippet.imports.contains([import_name]),
            CrawlJob.status != 'cancelled'
        ).limit(limit).all()
        
        return results
    
    def search_similar(self, text: str, limit: Optional[int] = None) -> List[CodeSnippet]:
        """Find similar code using trigram similarity.
        
        Args:
            text: Text to find similar code to
            limit: Maximum results
            
        Returns:
            List of similar snippets
        """
        limit = limit or self.settings.default_max_results
        
        # Use pg_trgm for similarity search
        similarity = func.similarity(CodeSnippet.code_content, text)
        
        results = self.session.query(
            CodeSnippet,
            similarity.label('sim_score')
        ).join(Document).join(CrawlJob).filter(
            similarity > 0.1,  # Minimum similarity threshold
            CrawlJob.status != 'cancelled'
        ).order_by(
            similarity.desc()
        ).limit(limit).all()
        
        # Extract just the snippets
        return [r[0] for r in results]
    
    def search_libraries(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for libraries by name using fuzzy matching.
        
        Args:
            query: Search query for library names
            limit: Maximum results to return
            
        Returns:
            List of library information dictionaries
        """
        # Use PostgreSQL's similarity function for fuzzy matching
        sql_query = """
        SELECT 
            cj.id,
            cj.name,
            COALESCE(cj.config->>'description', '') as description,
            cj.config->>'versions' as versions_json,
            COUNT(DISTINCT cs.id) as snippet_count,
            similarity(LOWER(cj.name), LOWER(:query)) as name_similarity
        FROM crawl_jobs cj
        LEFT JOIN documents d ON d.crawl_job_id = cj.id
        LEFT JOIN code_snippets cs ON cs.document_id = d.id
        WHERE cj.status != 'cancelled'
        AND (
            LOWER(cj.name) LIKE LOWER(:pattern)
            OR similarity(LOWER(cj.name), LOWER(:query)) > 0.1
        )
        GROUP BY cj.id, cj.name, cj.config
        ORDER BY 
            CASE WHEN LOWER(cj.name) = LOWER(:query) THEN 0 ELSE 1 END,
            name_similarity DESC,
            snippet_count DESC
        LIMIT :limit
        """
        
        params = {
            'query': query,
            'pattern': f'%{query}%',
            'limit': limit
        }
        
        result = self.session.execute(text(sql_query), params)
        
        libraries = []
        for row in result:
            library = {
                'library_id': str(row.id),
                'name': row.name,
                'description': row.description or 'No description available',
                'snippet_count': row.snippet_count,
                'similarity_score': float(row.name_similarity) if row.name_similarity else 0.0
            }
            
            # Parse versions if available
            if row.versions_json:
                try:
                    import json
                    versions = json.loads(row.versions_json)
                    if isinstance(versions, list):
                        library['versions'] = versions
                except:
                    pass
            
            libraries.append(library)
        
        return libraries
    
    def get_sources(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of crawled sources with statistics.
        
        Args:
            job_id: Optional filter by specific job
            
        Returns:
            List of source information dictionaries
        """
        query = """
        SELECT 
            cj.id,
            cj.name,
            cj.status,
            COALESCE(cj.config->>'repository', '') as repository,
            COALESCE(cj.config->>'description', '') as description,
            COUNT(DISTINCT d.id) as document_count,
            COUNT(DISTINCT cs.id) as snippet_count,
            SUM(LENGTH(cs.code_content)) as total_tokens,
            MAX(cs.created_at) as last_updated
        FROM crawl_jobs cj
        LEFT JOIN documents d ON d.crawl_job_id = cj.id
        LEFT JOIN code_snippets cs ON cs.document_id = d.id
        """
        
        params = {}
        if job_id:
            query += " WHERE cj.id = :job_id"
            params['job_id'] = job_id
        
        query += """
        GROUP BY cj.id, cj.name, cj.status, cj.config
        ORDER BY cj.created_at DESC
        """
        
        result = self.session.execute(text(query), params)
        
        sources = []
        for row in result:
            source = {
                'id': str(row.id),
                'name': row.name,
                'repository': row.repository,
                'description': row.description,
                'status': row.status.capitalize(),
                'document_count': row.document_count,
                'snippet_count': row.snippet_count,
                'tokens': row.total_tokens or 0,
                'last_update': row.last_updated.isoformat() if row.last_updated else None
            }
            
            # Format last update as relative time
            if row.last_updated:
                delta = datetime.utcnow() - row.last_updated
                if delta.days == 0:
                    source['last_update_relative'] = "Today"
                elif delta.days == 1:
                    source['last_update_relative'] = "Yesterday"
                elif delta.days < 7:
                    source['last_update_relative'] = f"{delta.days} days ago"
                elif delta.days < 30:
                    weeks = delta.days // 7
                    source['last_update_relative'] = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                else:
                    source['last_update_relative'] = row.last_updated.strftime("%m/%d/%Y")
            
            sources.append(source)
        
        return sources
    
    def get_recent_snippets(
        self,
        hours: int = 24,
        language: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[CodeSnippet]:
        """Get recently added snippets.
        
        Args:
            hours: Hours to look back
            language: Optional language filter
            limit: Maximum results
            
        Returns:
            List of recent snippets
        """
        limit = limit or self.settings.default_max_results
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.session.query(CodeSnippet).join(Document).join(CrawlJob).filter(
            CodeSnippet.created_at >= cutoff_time,
            CrawlJob.status != 'cancelled'
        )
        
        if language:
            query = query.filter(CodeSnippet.language == language.lower())
        
        results = query.order_by(
            CodeSnippet.created_at.desc()
        ).limit(limit).all()
        
        return results
    
    def get_languages(self) -> List[Dict[str, Any]]:
        """Get list of all languages with counts.
        
        Returns:
            List of language statistics
        """
        result = self.session.query(
            CodeSnippet.language,
            func.count(CodeSnippet.id).label('count')
        ).join(Document).join(CrawlJob).filter(
            CrawlJob.status != 'cancelled'
        ).group_by(
            CodeSnippet.language
        ).order_by(
            func.count(CodeSnippet.id).desc()
        ).all()
        
        return [
            {'language': lang, 'count': count}
            for lang, count in result
            if lang  # Skip null languages
        ]
    
    def format_search_results(self, snippets: List[CodeSnippet]) -> str:
        """Format search results in the specified output format.
        
        Args:
            snippets: List of code snippets to format
            
        Returns:
            Formatted string with all results
        """
        if not snippets:
            return "No results found."
        
        formatted_results = []
        
        for snippet in snippets:
            formatted_results.append(snippet.format_output())
        
        return "\n".join(formatted_results)


class DocumentSearcher:
    """Handles search operations for documents."""
    
    def __init__(self, session: Session):
        """Initialize searcher with database session."""
        self.session = session
    
    def search_documents(
        self,
        query: str,
        job_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """Search documents by content.
        
        Args:
            query: Search query
            job_id: Optional job filter
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Tuple of (results, total_count)
        """
        base_query = self.session.query(Document)
        
        if job_id:
            base_query = base_query.filter(Document.crawl_job_id == job_id)
        
        # Simple text search on title and content
        if query:
            base_query = base_query.filter(
                or_(
                    Document.title.ilike(f'%{query}%'),
                    Document.markdown_content.ilike(f'%{query}%')
                )
            )
        
        total_count = base_query.count()
        
        results = base_query.order_by(
            Document.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return results, total_count