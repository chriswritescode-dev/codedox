"""PostgreSQL full-text search implementation."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from ..config import get_settings
from .models import CodeSnippet, CrawlJob, Document, UploadJob

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
        query: str | None = None,
        source: str | None = None,
        language: str | None = None,
        job_id: str | None = None,
        snippet_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        include_context: bool = True,
        search_mode: str = "code",
    ) -> tuple[list[CodeSnippet], int]:
        """Search code snippets with various filters.

        Args:
            query: Text search query
            source: Filter by source name (supports fuzzy/domain matching)
            language: Filter by programming language
            job_id: Filter by crawl job ID
            snippet_type: Filter by snippet type (function, class, etc.)
            limit: Maximum results to return
            offset: Pagination offset
            include_context: Whether to include context fields
            search_mode: Search strategy - "code" (default) uses threshold-based markdown fallback,
                        "enhanced" always searches markdown for maximum results

        Returns:
            Tuple of (results, total_count)
        """
        limit = limit or self.settings.default_max_results

        # Resolve source name to job IDs if provided
        resolved_job_ids = []
        if source and not job_id:
            # Use search_libraries to resolve source name (supports domain matching)
            libraries, _ = self.search_libraries(query=source, limit=10, offset=0)
            if libraries:
                # Collect all matching job IDs
                resolved_job_ids = [lib["library_id"] for lib in libraries]
                # For single best match, use only the first one
                if len(libraries) == 1 or (
                    len(libraries) > 1 and libraries[0].get("similarity_score", 0) > 0.8
                ):
                    # Use only the best match if it's clearly the right one
                    resolved_job_ids = [libraries[0]["library_id"]]

        # For full-text search, use raw SQL to leverage the generated search_vector column
        if query:
            # Build SQL query with all filters
            sql_parts = ["SELECT cs.id"]
            sql_parts.append("FROM code_snippets cs")

            where_clauses = ["cs.search_vector @@ plainto_tsquery(:query)"]
            params = {"query": query}

            # Join with documents and both job types
            sql_parts.append("JOIN documents d ON cs.document_id = d.id")
            sql_parts.append("LEFT JOIN crawl_jobs cj ON d.crawl_job_id = cj.id")
            sql_parts.append("LEFT JOIN upload_jobs uj ON d.upload_job_id = uj.id")

            # Include all jobs regardless of status

            # Filter by job IDs (either explicit job_id or resolved from source)
            if job_id or resolved_job_ids:
                if job_id:
                    # Explicit job_id takes precedence
                    where_clauses.append("(d.crawl_job_id = :job_id OR d.upload_job_id = :job_id)")
                    params["job_id"] = job_id
                else:
                    # Use resolved job IDs from source search
                    where_clauses.append(
                        "(d.crawl_job_id = ANY(:job_ids) OR d.upload_job_id = ANY(:job_ids))"
                    )
                    params["job_ids"] = resolved_job_ids

            if language:
                where_clauses.append("cs.language = :language")
                params["language"] = language.lower()

            if snippet_type:
                where_clauses.append("cs.snippet_type = :snippet_type")
                params["snippet_type"] = snippet_type

            # Combine query
            sql_parts.append("WHERE " + " AND ".join(where_clauses))
            sql_parts.append("ORDER BY ts_rank(cs.search_vector, plainto_tsquery(:query)) DESC")
            sql_parts.append("LIMIT :limit OFFSET :offset")

            params["limit"] = limit
            params["offset"] = offset

            # Execute query
            sql = " ".join(sql_parts)
            result = self.session.execute(text(sql), params)

            # Get count
            count_sql = sql.replace("SELECT cs.id", "SELECT COUNT(*)")
            count_sql = count_sql.split("ORDER BY")[0]  # Remove ORDER BY and LIMIT
            total_count = int(
                self.session.execute(
                    text(count_sql),
                    {k: v for k, v in params.items() if k not in ["limit", "offset"]},
                ).scalar()
                or 0
            )

            # Convert results to CodeSnippet objects
            results = []
            seen_ids = set()
            for row in result:
                snippet = self.session.query(CodeSnippet).filter(CodeSnippet.id == row.id).first()
                if snippet and not include_context:
                    snippet.context_before = ""  # Clear context
                    snippet.context_after = ""  # Clear context
                if snippet:
                    results.append(snippet)
                    seen_ids.add(snippet.id)

            # Use the database function to find related snippets
            if results and len(results) < limit and self.settings.include_related_snippets:
                # For now, let's use a simpler approach without the database function
                # We'll use the existing relationship finding logic
                related_results = self._find_related_snippets(
                    results, seen_ids, limit - len(results), job_id, language, snippet_type
                )
                results.extend(related_results)
                total_count += len(related_results)

            # Markdown fallback: Search markdown based on mode or threshold
            if query and (
                search_mode == "enhanced"  # Force markdown search in enhanced mode
                or (
                    self.settings.markdown_fallback_enabled
                    and len(results) < self.settings.markdown_fallback_threshold
                )
            ):
                if search_mode == "enhanced":
                    logger.info(
                        f"Enhanced search mode: searching markdown for '{query}' to maximize results (found {len(results)} direct matches)"
                    )
                else:
                    logger.info(
                        f"Only {len(results)} direct matches found for '{query}', searching markdown for additional snippets"
                    )

                # Search documents using markdown content
                markdown_docs = self.search_markdown_documents(
                    query=query,
                    job_id=job_id or (resolved_job_ids[0] if resolved_job_ids else None),
                    limit=self.settings.markdown_fallback_doc_limit,
                )

                if markdown_docs:
                    logger.info(
                        f"Found {len(markdown_docs)} documents matching '{query}' in markdown"
                    )
                    # Get document IDs from markdown search
                    doc_ids = [doc.id for doc in markdown_docs]

                    # Calculate the offset for markdown snippets
                    # We need to account for snippets that would have appeared on previous pages
                    markdown_offset = 0
                    if offset > 0:
                        # If we're beyond the first page, we need to skip markdown snippets
                        # that would have been shown on previous pages
                        # First, figure out how many direct search results came before this page
                        direct_results_before = min(offset, total_count)
                        # Then calculate how many markdown results we need to skip
                        markdown_offset = max(0, offset - direct_results_before)

                    # Get snippets from those documents with proper offset
                    markdown_snippets = self.get_snippets_from_documents(
                        document_ids=doc_ids,
                        exclude_snippet_ids=seen_ids,
                        language=language,
                        snippet_type=snippet_type,
                        limit=limit - len(results),  # Only get enough to fill the limit
                        offset=markdown_offset,  # Apply offset for proper pagination
                    )

                    # Mark these snippets as discovered via markdown
                    for snippet in markdown_snippets:
                        snippet._discovery_method = "markdown"
                        # Find which document it came from and its rank
                        for doc in markdown_docs:
                            if snippet.document_id == doc.id:
                                snippet._markdown_rank = getattr(doc, "_search_rank", 0.5)
                                break

                    # Add markdown-discovered snippets to results
                    results.extend(markdown_snippets)

                    # For total count, we need to get the full count of markdown snippets
                    # without limit to know the true total
                    all_markdown_snippets_count = (
                        self.session.query(CodeSnippet)
                        .filter(CodeSnippet.document_id.in_(doc_ids))
                        .filter(~CodeSnippet.id.in_(seen_ids) if seen_ids else True)
                    )
                    if language:
                        all_markdown_snippets_count = all_markdown_snippets_count.filter(
                            CodeSnippet.language == language.lower()
                        )
                    if snippet_type:
                        all_markdown_snippets_count = all_markdown_snippets_count.filter(
                            CodeSnippet.snippet_type == snippet_type
                        )
                    markdown_total = all_markdown_snippets_count.count()
                    total_count += markdown_total

                    logger.info(
                        f"Found {len(markdown_snippets)} additional snippets via markdown search (total available: {markdown_total})"
                    )
                else:
                    logger.info(f"No documents found matching '{query}' in markdown content")

            return results, total_count
        else:
            # Non-text search - use regular SQLAlchemy query
            base_query = self.session.query(CodeSnippet)
            filters = []

            # Join with Document and optionally with job tables
            base_query = base_query.join(Document)
            base_query = base_query.outerjoin(CrawlJob, Document.crawl_job_id == CrawlJob.id)
            base_query = base_query.outerjoin(UploadJob, Document.upload_job_id == UploadJob.id)

            # Include all jobs regardless of status

            # Filter by job IDs (either explicit job_id or resolved from source)
            if job_id or resolved_job_ids:
                if job_id:
                    # Explicit job_id takes precedence
                    filters.append(
                        or_(Document.crawl_job_id == job_id, Document.upload_job_id == job_id)
                    )
                else:
                    # Use resolved job IDs from source search
                    filters.append(
                        or_(
                            Document.crawl_job_id.in_(resolved_job_ids),
                            Document.upload_job_id.in_(resolved_job_ids),
                        )
                    )

            if language:
                filters.append(CodeSnippet.language == language.lower())

            if snippet_type:
                filters.append(CodeSnippet.snippet_type == snippet_type)

            if filters:
                base_query = base_query.filter(and_(*filters))

            total_count = base_query.count()

            results = (
                base_query.order_by(CodeSnippet.created_at.desc()).offset(offset).limit(limit).all()
            )

            if not include_context:
                for snippet in results:
                    snippet.context_before = ""  # Clear context
                    snippet.context_after = ""  # Clear context

            return results, total_count

    def search_by_function(self, function_name: str, limit: int | None = None) -> list[CodeSnippet]:
        """Search for snippets containing specific function names.

        Args:
            function_name: Function name to search for
            limit: Maximum results

        Returns:
            List of matching snippets
        """
        limit = limit or self.settings.default_max_results

        results = (
            self.session.query(CodeSnippet)
            .join(Document)
            .join(CrawlJob)
            .filter(CodeSnippet.functions.contains([function_name]))
            .limit(limit)
            .all()
        )

        return results

    def search_by_import(self, import_name: str, limit: int | None = None) -> list[CodeSnippet]:
        """Search for snippets with specific imports.

        Args:
            import_name: Import to search for
            limit: Maximum results

        Returns:
            List of matching snippets
        """
        limit = limit or self.settings.default_max_results

        results = (
            self.session.query(CodeSnippet)
            .join(Document)
            .join(CrawlJob)
            .filter(CodeSnippet.imports.contains([import_name]))
            .limit(limit)
            .all()
        )

        return results

    def search_similar(self, text: str, limit: int | None = None) -> list[CodeSnippet]:
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

        results = (
            self.session.query(CodeSnippet, similarity.label("sim_score"))
            .join(Document)
            .join(CrawlJob)
            .filter(
                similarity > 0.1  # Minimum similarity threshold
            )
            .order_by(similarity.desc())
            .limit(limit)
            .all()
        )

        # Extract just the snippets
        return [r[0] for r in results]

    def search_libraries(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """Search for libraries by name using fuzzy matching.

        Args:
            query: Search query for library names
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Tuple of (list of library information dictionaries, total count)
        """
        # Use PostgreSQL's similarity function for fuzzy matching
        # Union query to get both crawl and upload jobs
        sql_query = """
        WITH all_sources AS (
            SELECT
                cj.id,
                cj.name,
                cj.version,
                cj.domain,
                'crawl' as source_type,
                COALESCE(cj.config->>'description', '') as description,
                cj.config->>'versions' as versions_json,
                COUNT(DISTINCT cs.id) as snippet_count,
                similarity(LOWER(cj.name), LOWER(:query)) as name_similarity,
                CASE
                    WHEN cj.domain IS NOT NULL
                    THEN similarity(LOWER(SPLIT_PART(cj.domain, '.', 1)), LOWER(:query))
                    ELSE 0
                END as domain_similarity
            FROM crawl_jobs cj
            LEFT JOIN documents d ON d.crawl_job_id = cj.id
            LEFT JOIN code_snippets cs ON cs.document_id = d.id
            WHERE (
                LOWER(cj.name) LIKE LOWER(:pattern)
                OR (cj.domain IS NOT NULL AND LOWER(SPLIT_PART(cj.domain, '.', 1)) LIKE LOWER(:pattern))
                OR similarity(LOWER(cj.name), LOWER(:query)) > 0.1
                OR (cj.domain IS NOT NULL AND similarity(LOWER(SPLIT_PART(cj.domain, '.', 1)), LOWER(:query)) > 0.1)
            )
            GROUP BY cj.id, cj.name, cj.version, cj.domain, cj.config
            
            UNION ALL
            
            SELECT
                uj.id,
                uj.name,
                uj.version,
                NULL as domain,
                'upload' as source_type,
                COALESCE(uj.config->>'description', '') as description,
                NULL as versions_json,
                COUNT(DISTINCT cs.id) as snippet_count,
                similarity(LOWER(uj.name), LOWER(:query)) as name_similarity,
                0 as domain_similarity
            FROM upload_jobs uj
            LEFT JOIN documents d ON d.upload_job_id = uj.id
            LEFT JOIN code_snippets cs ON cs.document_id = d.id
            WHERE (
                LOWER(uj.name) LIKE LOWER(:pattern)
                OR similarity(LOWER(uj.name), LOWER(:query)) > 0.1
            )
            GROUP BY uj.id, uj.name, uj.version, uj.config
        )
        SELECT * FROM all_sources
        ORDER BY
            CASE
                WHEN LOWER(name) = LOWER(:query) THEN 0
                WHEN domain IS NOT NULL AND LOWER(SPLIT_PART(domain, '.', 1)) = LOWER(:query) THEN 0
                ELSE 1
            END,
            GREATEST(name_similarity, COALESCE(domain_similarity, 0)) DESC,
            snippet_count DESC
        LIMIT :limit OFFSET :offset
        """

        # First get total count
        count_query = """
        SELECT COUNT(*) FROM (
            SELECT cj.id
            FROM crawl_jobs cj
            WHERE (
                LOWER(cj.name) LIKE LOWER(:pattern)
                OR (cj.domain IS NOT NULL AND LOWER(SPLIT_PART(cj.domain, '.', 1)) LIKE LOWER(:pattern))
                OR similarity(LOWER(cj.name), LOWER(:query)) > 0.1
                OR (cj.domain IS NOT NULL AND similarity(LOWER(SPLIT_PART(cj.domain, '.', 1)), LOWER(:query)) > 0.1)
            )
            
            UNION ALL
            
            SELECT uj.id
            FROM upload_jobs uj
            WHERE (
                LOWER(uj.name) LIKE LOWER(:pattern)
                OR similarity(LOWER(uj.name), LOWER(:query)) > 0.1
            )
        ) AS all_sources
        """

        safe_query = query.replace("%", r"\%").replace("_", r"\_")
        params = {"query": query, "pattern": f"%{safe_query}%", "limit": limit, "offset": offset}

        total_count = (
            self.session.execute(
                text(count_query), {"query": query, "pattern": f"%{safe_query}%"}
            ).scalar()
            or 0
        )

        # Get paginated results
        result = self.session.execute(text(sql_query), params)

        libraries = []
        for row in result:
            library = {
                "library_id": str(row.id),
                "name": row.name,
                "version": row.version,
                "source_type": row.source_type,
                "description": row.description or "No description available",
                "snippet_count": row.snippet_count,
                "similarity_score": float(row.name_similarity) if row.name_similarity else 0.0,
            }

            # Parse versions if available
            if row.versions_json:
                try:
                    import json

                    versions = json.loads(row.versions_json)
                    if isinstance(versions, list):
                        library["versions"] = versions
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            libraries.append(library)

        return libraries, total_count

    def get_sources(self, job_id: str | None = None) -> list[dict[str, Any]]:
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
            params["job_id"] = job_id

        query += """
        GROUP BY cj.id, cj.name, cj.status, cj.config
        ORDER BY cj.created_at DESC
        """

        result = self.session.execute(text(query), params)

        sources = []
        for row in result:
            source = {
                "id": str(row.id),
                "name": row.name,
                "repository": row.repository,
                "description": row.description,
                "status": row.status.capitalize(),
                "document_count": row.document_count,
                "snippet_count": row.snippet_count,
                "tokens": row.total_tokens or 0,
                "last_update": row.last_updated.isoformat() if row.last_updated else None,
            }

            # Format last update as relative time
            if row.last_updated:
                delta = datetime.now(timezone.utc) - row.last_updated
                if delta.days == 0:
                    source["last_update_relative"] = "Today"
                elif delta.days == 1:
                    source["last_update_relative"] = "Yesterday"
                elif delta.days < 7:
                    source["last_update_relative"] = f"{delta.days} days ago"
                elif delta.days < 30:
                    weeks = delta.days // 7
                    source["last_update_relative"] = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                else:
                    source["last_update_relative"] = row.last_updated.strftime("%m/%d/%Y")

            sources.append(source)

        return sources

    def get_recent_snippets(
        self, hours: int = 24, language: str | None = None, limit: int | None = None
    ) -> list[CodeSnippet]:
        """Get recently added snippets.

        Args:
            hours: Hours to look back
            language: Optional language filter
            limit: Maximum results

        Returns:
            List of recent snippets
        """
        limit = limit or self.settings.default_max_results

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            self.session.query(CodeSnippet)
            .join(Document)
            .join(CrawlJob)
            .filter(CodeSnippet.created_at >= cutoff_time)
        )

        if language:
            query = query.filter(CodeSnippet.language == language.lower())

        results = query.order_by(CodeSnippet.created_at.desc()).limit(limit).all()

        return results

    def get_languages(self) -> list[dict[str, Any]]:
        """Get list of all languages with counts.

        Returns:
            List of language statistics
        """
        result = (
            self.session.query(CodeSnippet.language, func.count(CodeSnippet.id).label("count"))
            .join(Document)
            .join(CrawlJob)
            .group_by(CodeSnippet.language)
            .order_by(func.count(CodeSnippet.id).desc())
            .all()
        )

        return [
            {"language": lang, "count": count}
            for lang, count in result
            if lang  # Skip null languages
        ]

    def search_markdown_documents(
        self, query: str, job_id: str | None = None, limit: int = 10
    ) -> list[Document]:
        """Search documents using markdown content.

        Args:
            query: Search query
            job_id: Optional job ID filter
            limit: Maximum documents to return

        Returns:
            List of matching documents ranked by relevance
        """
        sql = """
        SELECT d.*,
               ts_rank(d.markdown_search_vector, plainto_tsquery('english', :query)) as rank
        FROM documents d
        WHERE d.markdown_search_vector @@ plainto_tsquery('english', :query)
        """

        params = {"query": query, "limit": limit}

        if job_id:
            sql += " AND (d.crawl_job_id = :job_id OR d.upload_job_id = :job_id)"
            params["job_id"] = job_id

        sql += " ORDER BY rank DESC LIMIT :limit"

        result = self.session.execute(text(sql), params)

        documents = []
        for row in result:
            doc = self.session.query(Document).filter(Document.id == row.id).first()
            if doc:
                doc._search_rank = float(row.rank)
                documents.append(doc)

        return documents

    def get_snippets_from_documents(
        self,
        document_ids: list[int],
        exclude_snippet_ids: set[int] | None = None,
        language: str | None = None,
        snippet_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CodeSnippet]:
        """Get all code snippets from specified documents.

        Args:
            document_ids: List of document IDs to get snippets from
            exclude_snippet_ids: Set of snippet IDs to exclude (avoid duplicates)
            language: Optional language filter
            snippet_type: Optional snippet type filter
            limit: Maximum snippets to return
            offset: Pagination offset for consistent results

        Returns:
            List of code snippets from the specified documents
        """
        if not document_ids:
            return []

        # Join with Document first for ordering
        query = (
            self.session.query(CodeSnippet)
            .join(Document)
            .filter(CodeSnippet.document_id.in_(document_ids))
        )

        if exclude_snippet_ids:
            query = query.filter(~CodeSnippet.id.in_(exclude_snippet_ids))

        if language:
            query = query.filter(CodeSnippet.language == language.lower())

        if snippet_type:
            query = query.filter(CodeSnippet.snippet_type == snippet_type)

        # Order by document relevance (if available) and creation date
        query = query.order_by(Document.id.in_(document_ids).desc(), CodeSnippet.created_at.desc())

        # Apply offset for pagination
        if offset > 0:
            query = query.offset(offset)

        # Apply limit after ordering
        if limit:
            query = query.limit(limit)

        return query.all()

    def _find_related_snippets(
        self,
        primary_results: list[CodeSnippet],
        seen_ids: set,
        max_additional: int,
        job_id: str | None = None,
        language: str | None = None,
        snippet_type: str | None = None,
    ) -> list[CodeSnippet]:
        """Find snippets related to the primary search results using the relationship table.

        Args:
            primary_results: Initial search results
            seen_ids: Set of snippet IDs already in results
            max_additional: Maximum additional snippets to return
            job_id: Optional job filter
            language: Optional language filter
            snippet_type: Optional type filter

        Returns:
            List of related snippets
        """
        if not primary_results or max_additional <= 0:
            return []

        related_snippets = []
        related_info: dict[str, dict] = {}  # Map of snippet_id to relationship info

        # Get IDs of primary results
        primary_ids = [s.id for s in primary_results]

        # Use the database function to find related snippets
        sql = """
        SELECT * FROM find_related_snippets(
            :snippet_ids,
            NULL,  -- all relationship types
            :limit
        )
        """

        result = self.session.execute(
            text(sql),
            {
                "snippet_ids": primary_ids,
                "limit": max_additional * 2,
            },  # Get extra to account for filtering
        )

        # Build the related_info map from database results
        primary_map = {s.id: s for s in primary_results}

        for row in result:
            source_id = row.snippet_id
            target_id = row.related_snippet_id

            # Skip if already seen
            if target_id in seen_ids:
                continue

            # Get the primary snippet
            primary_snippet = primary_map.get(source_id)
            if primary_snippet:
                if target_id not in related_info:
                    related_info[target_id] = []
                related_info[target_id].append(
                    {
                        "primary_snippet": primary_snippet,
                        "relationship": {
                            "relationship_type": row.relationship_type,
                            "description": row.description
                            or f"{row.relationship_type} relationship",
                        },
                    }
                )

        if not related_info:
            return []

        # Build query for related snippets
        query = self.session.query(CodeSnippet).join(Document).join(CrawlJob)

        # Apply filters
        filters = [CodeSnippet.id.in_(list(related_info.keys()))]

        if job_id:
            filters.append(Document.crawl_job_id == job_id)
        if language:
            filters.append(CodeSnippet.language == language.lower())
        if snippet_type:
            filters.append(CodeSnippet.snippet_type == snippet_type)

        query = query.filter(and_(*filters))

        # Get related snippets
        related = query.limit(max_additional).all()

        # Add relationship context to each related snippet
        for rel_snippet in related:
            if rel_snippet.id in related_info:
                # Add context about why this was included
                rel_snippet._search_context = []
                for info in related_info[rel_snippet.id]:
                    primary = info["primary_snippet"]
                    relationship = info["relationship"]
                    rel_snippet._search_context.append(
                        {
                            "related_to": primary.title or f"Snippet {primary.id}",
                            "relationship": relationship.get("relationship_type", "related"),
                            "description": relationship.get("description", "Related code"),
                        }
                    )

        related_snippets.extend(related)

        return related_snippets

    def format_search_results(self, snippets: list[CodeSnippet]) -> str:
        """Format search results in the specified output format.

        Args:
            snippets: List of code snippets to format

        Returns:
            Formatted string with all results
        """
        if not snippets:
            return "No results found."

        formatted_results = []

        for _i, snippet in enumerate(snippets):
            # Add discovery method context if found via markdown
            if hasattr(snippet, "_discovery_method") and snippet._discovery_method == "markdown":
                rank = getattr(snippet, "_markdown_rank", 0.5)
                formatted_results.append(
                    f"[Found via documentation search - relevance: {rank:.2f}]"
                )

            # Add relationship context if this is a related result
            if hasattr(snippet, "_search_context") and snippet._search_context:
                context_lines = []
                for ctx in snippet._search_context:
                    rel_type = ctx["relationship"]
                    related_to = ctx["related_to"]
                    desc = ctx["description"]
                    context_lines.append(f"[Related via {rel_type} to '{related_to}': {desc}]")

                formatted_results.append("\n".join(context_lines))

            formatted_results.append(snippet.format_output())

        return "\n".join(formatted_results)


class DocumentSearcher:
    """Handles search operations for documents."""

    def __init__(self, session: Session):
        """Initialize searcher with database session."""
        self.session = session

    def search_documents(
        self, query: str, job_id: str | None = None, limit: int = 10, offset: int = 0
    ) -> tuple[list[Document], int]:
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

        # Simple text search on title only
        if query:
            base_query = base_query.filter(Document.title.ilike(f"%{query}%"))

        total_count = base_query.count()

        results = base_query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

        return results, total_count
