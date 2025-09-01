"""MCP tool implementations."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import text
from ..config import get_settings
from ..database import get_db_manager, CodeSearcher
from ..crawler import CrawlManager, CrawlConfig

logger = logging.getLogger(__name__)
settings = get_settings()


def create_error_response(
    error_message: str, status: str = "error", additional_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_message: The error message to return
        status: The status code (default: "error")
        additional_fields: Optional additional fields to include in response

    Returns:
        Standardized error response dictionary
    """
    response = {"status": status, "error": error_message}

    if additional_fields:
        response.update(additional_fields)

    return response


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
        version: Optional[str] = None,
        max_pages: Optional[int] = None,
        domain_filter: Optional[str] = None,
        url_patterns: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_concurrent_crawls: int | None = None,
    ) -> Dict[str, Any]:
        """Initialize a new crawl job.

        Args:
            name: Library/framework name (auto-detected if not provided)
            start_urls: URLs to start crawling
            max_depth: Maximum crawl depth (0-3)
            version: Optional version identifier (e.g., "v14", "v15", "2.0")
            domain_filter: Optional domain restriction
            url_patterns: Optional list of URL patterns to include (e.g., ["*docs*", "*guide*"])
                will keep only URLs matching these patterns
            metadata: Additional metadata
            max_concurrent_crawls: Maximum concurrent crawl sessions (default: from config)

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
                domain = parsed.netloc.replace("www.", "")
                name = f"[Auto-detecting from {domain}]"
                metadata["auto_detect_name"] = True

            metadata.update(
                {
                    "library_name": name,
                    "version": version,
                    "initiated_via": "mcp",
                    "initiated_at": datetime.now().isoformat(),
                }
            )

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
                logger.warning(
                    f"Deep crawl requested with depth={max_depth}. This may take several minutes."
                )

            # Create crawl configuration
            config = CrawlConfig(
                name=name,
                start_urls=start_urls,
                max_depth=max_depth,
                version=version,
                domain_restrictions=domain_restrictions,
                include_patterns=url_patterns or [],
                max_pages=max_pages,
                metadata=metadata,
                max_concurrent_crawls=max_concurrent_crawls
                or settings.crawling.max_concurrent_crawls,
            )

            # Start crawl job
            job_id = await self.crawl_manager.start_crawl(config)

            return {
                "job_id": job_id,
                "status": "started",
                "library_name": name,
                "version": version,
                "message": f"Crawl job initiated with {len(start_urls)} URLs at depth {max_depth}",
                "start_urls": start_urls,
                "max_depth": max_depth,
                "domain_restrictions": domain_restrictions,
                "url_patterns": url_patterns or [],
                "auto_detect_name": metadata.get("auto_detect_name", False),
            }

        except Exception as e:
            logger.error(f"Failed to initialize crawl: {e}")
            return create_error_response(str(e), "failed", {"library_name": name})

    async def search_libraries(
        self, query: str = "", limit: int = 20, page: int = 1
    ) -> dict[str, Any]:
        """Search for available libraries by name or keyword, or list all libraries.

        Args:
            query: Search query for library names (empty string returns all)
            limit: Maximum results per page (default: 20)
            page: Page number for paginated results (1-indexed)

        Returns:
            Dictionary with libraries and search results
        """
        try:
            with self.db_manager.session_scope() as session:
                searcher = CodeSearcher(session)

                # Calculate offset for pagination
                offset = (page - 1) * limit

                libraries, total_count = searcher.search_libraries(
                    query=query, limit=limit, offset=offset
                )

                if not libraries:
                    if query:
                        return {
                            "status": "no_matches",
                            "message": f"No libraries found matching '{query}'",
                            "suggestion": "Try a different search term or check if the library has been crawled",
                        }
                    else:
                        return {
                            "status": "empty",
                            "message": "No libraries have been crawled yet",
                            "suggestion": "Use init_crawl to add documentation sources",
                        }

                # Calculate total pages
                import math

                total_pages = math.ceil(total_count / limit) if total_count > 0 else 0

                # If no query provided, return all libraries
                if not query:
                    message = f"Found {total_count} available libraries"
                    if total_pages > 1:
                        message += f" (showing page {page} of {total_pages})"

                    return {
                        "status": "success",
                        "libraries": [
                            {
                                "library_id": lib["library_id"],
                                "name": lib["name"],
                                "version": lib.get("version"),
                                "description": lib["description"],
                                "snippet_count": lib["snippet_count"],
                            }
                            for lib in libraries
                        ],
                        "total_count": total_count,
                        "page": page,
                        "total_pages": total_pages,
                        "message": message,
                    }

                # For searches with query, find the best match
                best_match = libraries[0]  # Already sorted by relevance
                other_matches = libraries[1:5] if len(libraries) > 1 else []

                # Determine match quality
                exact_match = best_match["name"].lower() == query.lower()
                strong_match = query.lower() in best_match["name"].lower()

                # Build response
                response: dict[str, Any] = {
                    "status": "success",
                    "selected_library": {
                        "library_id": best_match["library_id"],
                        "name": best_match["name"],
                        "version": best_match.get("version"),
                        "description": best_match["description"],
                        "snippet_count": best_match["snippet_count"],
                    },
                }

                # Add versions if available
                if "versions" in best_match:
                    response["selected_library"]["versions"] = best_match["versions"]

                # Add explanation
                if exact_match:
                    response["explanation"] = f"Exact match found for '{query}'"
                elif strong_match:
                    response["explanation"] = (
                        f"Strong match found: '{best_match['name']}' contains '{query}'"
                    )
                else:
                    response["explanation"] = (
                        f"Best match based on similarity: '{best_match['name']}'"
                    )

                # Add similarity score if available
                if "similarity_score" in best_match:
                    response["match_confidence"] = f"{best_match['similarity_score']:.2%}"

                # Acknowledge other matches
                if other_matches:
                    response["other_matches"] = [
                        {
                            "library_id": lib["library_id"],
                            "name": lib["name"],
                            "version": lib.get("version"),
                            "snippet_count": lib["snippet_count"],
                        }
                        for lib in other_matches
                    ]
                    response["note"] = f"Found {total_count} total matches."
                    if total_pages > 1:
                        response["note"] += f" Showing page {page} of {total_pages}."
                    else:
                        response["note"] += " Showing the most relevant."

                # Add pagination info
                response["page"] = page
                response["total_pages"] = total_pages
                response["total_count"] = total_count

                # Add warning for low snippet count
                if best_match["snippet_count"] < 10:
                    response["warning"] = "This library has limited documentation coverage"

                return response

        except Exception as e:
            logger.error(f"Failed to search libraries: {e}")
            return create_error_response(str(e), "error", {"message": "Failed to search libraries"})

    async def get_content(
        self, library_id: str, query: str | None = None, limit: int = 20, page: int = 1
    ) -> str:
        """Get code snippets from a library with optional search.

        This tool searches through CODE SNIPPETS only (not full documentation text).
        Each result includes a SOURCE URL that can be used with get_page_markdown to retrieve
        the full documentation page where the code came from.

        Workflow example:
        1. get_content("react", "useState") → Returns code snippets with SOURCE URLs
        2. Use SOURCE URL with get_page_markdown() to get full documentation context

        Search scope:
        - Searches in: code content, titles, descriptions, function names, imports
        - Does NOT search: full markdown documentation text

        Args:
            library_id: Library ID (UUID) or library name - can use either format
            query: Optional search query to filter code snippets (not documentation)
            limit: Maximum results per page (default: 20)
            page: Page number for paginated results (1-indexed)

        Returns:
            Formatted code snippets with SOURCE URLs for full documentation access
        """
        try:
            with self.db_manager.session_scope() as session:
                searcher = CodeSearcher(session)

                # Check if library_id is a valid UUID
                import re

                uuid_pattern = re.compile(
                    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
                )
                is_uuid = bool(uuid_pattern.match(library_id))

                actual_library_id = library_id
                library_name = library_id  # Default to the input for display
                library_version = None  # Initialize version

                # If not a UUID, treat as library name and search for it
                if not is_uuid:
                    libraries, _ = searcher.search_libraries(query=library_id, limit=20)

                    if not libraries:
                        # No matches found, try to find all libraries and suggest the most similar
                        all_libraries, _ = searcher.search_libraries(query="", limit=100)
                        if all_libraries:
                            # Calculate similarity scores for all libraries
                            from difflib import SequenceMatcher

                            scored_libs = []
                            for lib in all_libraries:
                                # Use difflib for better similarity matching
                                similarity = SequenceMatcher(
                                    None, library_id.lower(), lib["name"].lower()
                                ).ratio()
                                scored_libs.append((lib, similarity))

                            # Sort by similarity and take top 5
                            scored_libs.sort(key=lambda x: x[1], reverse=True)
                            suggestions = []
                            for lib, score in scored_libs[:5]:
                                if (
                                    score > settings.search.library_suggestion_threshold
                                ):  # Only show somewhat similar libraries
                                    suggestions.append(
                                        f"  - {lib['name']} (similarity: {score:.0%}, snippets: {lib['snippet_count']})"
                                    )

                            if suggestions:
                                return (
                                    f"❌ No library found matching '{library_id}'.\n\n"
                                    f"📚 Did you mean one of these?\n"
                                    + "\n".join(suggestions)
                                    + "\n\n"
                                    "💡 Tip: Use the exact library name or copy the ID from search_libraries."
                                )
                            else:
                                return f"❌ No library found matching '{library_id}' and no similar libraries found.\n\n💡 Use search_libraries to find available libraries."
                        else:
                            return "❌ No libraries have been crawled yet. Use init_crawl to add documentation sources."

                    # Check for exact match first (case-insensitive)
                    exact_match = None
                    for lib in libraries:
                        if lib["name"].lower() == library_id.lower():
                            exact_match = lib
                            break

                    if exact_match:
                        # Use exact match
                        actual_library_id = exact_match["library_id"]
                        library_name = exact_match["name"]
                        library_version = exact_match.get("version")
                        logger.info(f"Exact match found: '{library_name}' for query '{library_id}'")
                    elif len(libraries) == 1:
                        # Single match, use it
                        actual_library_id = libraries[0]["library_id"]
                        library_name = libraries[0]["name"]
                        library_version = libraries[0].get("version")
                        logger.info(
                            f"Single match found: '{library_name}' for query '{library_id}'"
                        )
                    elif len(libraries) > 1:
                        # Check if we have a clear winner
                        first_score = libraries[0].get("similarity_score", 0)
                        second_score = (
                            libraries[1].get("similarity_score", 0) if len(libraries) > 1 else 0
                        )

                        # Use configurable thresholds: auto-select if first is good and significantly better than second
                        if (
                            first_score > settings.search.library_auto_select_threshold
                            and (first_score - second_score)
                            > settings.search.library_auto_select_gap
                        ):
                            actual_library_id = libraries[0]["library_id"]
                            library_name = libraries[0]["name"]
                            library_version = libraries[0].get("version")
                            logger.info(
                                f"Auto-selected best match: '{library_name}' (score: {first_score:.2f}) for query '{library_id}'"
                            )
                        else:
                            # Multiple close matches, ask user to be more specific
                            suggestions = []
                            for i, lib in enumerate(libraries[:5]):
                                score = lib.get("similarity_score", 0)
                                snippets = lib.get("snippet_count", 0)
                                suggestions.append(
                                    f"{lib['name']} (match: {score:.0%}, snippets: {snippets})"
                                )

                            return (
                                f"🤔 Multiple libraries match '{library_id}'. Please be more specific:\n\n"
                                + "\n".join(suggestions)
                                + "\n\n"
                                "💡 Tip: Use the exact library name for best results."
                            )

                # Calculate offset for pagination
                offset = (page - 1) * limit

                # Search with resolved library_id
                snippets, total_count = searcher.search(
                    query=query or "",  # Use empty string if query is None
                    job_id=actual_library_id,
                    limit=limit,
                    offset=offset,
                    include_context=False,  # Don't include context in search results
                )

                if not snippets:
                    if query:
                        no_results_msg = (
                            f"No results found for query '{query}' in library '{library_name}'"
                        )
                    else:
                        no_results_msg = f"No content found in library '{library_name}'"
                    return no_results_msg

                # Format results using the specified format
                formatted_results = searcher.format_search_results(snippets)

                # Calculate total pages
                import math

                total_pages = math.ceil(total_count / limit) if total_count > 0 else 0

                # Add summary header
                header = f"Found {total_count} results"
                if total_pages > 1:
                    header += f" (showing page {page} of {total_pages})"
                if query:
                    header += f" for query '{query}' in library '{library_name}"
                    if library_version:
                        header += f" {library_version}"
                    header += "'"
                else:
                    header += f" in library '{library_name}"
                    if library_version:
                        header += f" {library_version}"
                    header += "'"
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
                return create_error_response("Job not found", "not_found", {"job_id": job_id})

            # Calculate progress percentage
            progress = 0
            if status["total_pages"] > 0:
                progress = int((status["processed_pages"] / status["total_pages"]) * 100)

            result = {
                "job_id": job_id,
                "name": status["name"],
                "status": status["status"],
                "progress": f"{progress}%",
                "processed_pages": status["processed_pages"],  # Fixed key name
                "total_pages": status["total_pages"],
                "snippets_extracted": status["snippets_extracted"],
                "started_at": status["started_at"],
                "completed_at": status["completed_at"],
            }

            # Add error message if present
            if status.get("error_message"):
                result["error_message"] = status["error_message"]

            return result

        except Exception as e:
            logger.error(f"Failed to get crawl status: {e}")
            return {"error": str(e), "job_id": job_id}

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
                    "message": "Crawl job cancelled successfully",
                }
            else:
                return {
                    "error": "Failed to cancel job",
                    "job_id": job_id,
                    "message": "Job may have already completed or does not exist",
                }

        except Exception as e:
            logger.error(f"Failed to cancel crawl: {e}")
            return {"error": str(e), "job_id": job_id}

    async def get_page_markdown(
        self,
        url: str,
        query: Optional[str] = None,
        max_tokens: Optional[int] = None,
        chunk_index: Optional[int] = None,
        chunk_size: int = 2048,
    ) -> Dict[str, Any]:
        """Get full documentation markdown from a specific page URL.

        Use this tool to retrieve the complete documentation context for code snippets.
        The URL typically comes from the SOURCE field in get_content results.

        Features:
        1. Get full page: Just provide URL
        2. Search within page: Add query parameter to search/highlight within this specific document
        3. Limit content size: Use max_tokens to get only first N tokens
        4. Chunk large docs: Use chunk_index to paginate through large documents

        Common workflows:
        - After get_content(): Use SOURCE URL here to get full documentation
        - Search in page: get_page_markdown(url="...", query="specific term")
        - Get summary: get_page_markdown(url="...", max_tokens=500)
        - Navigate chunks: get_page_markdown(url="...", chunk_index=0, chunk_size=2048)

        Important notes:
        - This searches WITHIN a single document, not across all documents
        - The query parameter uses PostgreSQL full-text search with highlighting
        - Returns markdown format with code blocks, headers, etc. preserved

        Args:
            url: The URL of the documentation page (typically from SOURCE in get_content)
            query: Optional search within THIS document only (highlights matches)
            max_tokens: Limit response to first N tokens (useful for summaries)
            chunk_index: Get specific chunk of large documents (0-based)
            chunk_size: Size of each chunk in tokens (default: 2048)

        Returns:
            Dictionary with markdown content, search highlights, token counts, and pagination info
        """
        try:
            with self.db_manager.session_scope() as session:
                from ..database.models import Document, CrawlJob, UploadJob

                doc = session.query(Document).filter(Document.url == url).first()

                if not doc:
                    return {
                        "status": "not_found",
                        "error": f"No document found with URL: {url}",
                        "suggestion": "Check the URL is correct or that the page has been crawled",
                    }

                # Check if markdown content exists
                if not doc.markdown_content:
                    return {
                        "status": "no_content",
                        "error": f"Document exists but has no markdown content",
                        "url": url,
                        "title": doc.title,
                        "note": "This document may have been crawled before markdown storage was enabled",
                    }

                # Get library name from associated job
                library_name = None
                if doc.crawl_job_id:
                    crawl_job = (
                        session.query(CrawlJob).filter(CrawlJob.id == doc.crawl_job_id).first()
                    )
                    if crawl_job:
                        library_name = crawl_job.name
                elif doc.upload_job_id:
                    upload_job = (
                        session.query(UploadJob).filter(UploadJob.id == doc.upload_job_id).first()
                    )
                    if upload_job:
                        library_name = upload_job.name

                # Get content based on search or full document
                search_applied = False
                from sqlalchemy import text

                if query:
                    logger.info(f"Search query provided for document {url[:50]}: '{query}'")
                    # First check if the query matches the document using full-text search
                    try:
                        # Check if document matches the search query
                        match_result = session.execute(
                            text("""
                            SELECT 
                                markdown_search_vector @@ plainto_tsquery('english', :query) as matches,
                                ts_rank(markdown_search_vector, plainto_tsquery('english', :query)) as rank
                            FROM documents
                            WHERE url = :url
                            AND markdown_content IS NOT NULL
                            """),
                            {"url": url, "query": query},
                        ).first()

                        if match_result and match_result[0]:  # Document matches the query
                            # Get highlighted excerpts showing the matches
                            headline_result = session.execute(
                                text("""
                                SELECT ts_headline(
                                    'english',
                                    markdown_content,
                                    plainto_tsquery('english', :query),
                                    'MaxWords=' || :max_words || ', MinWords=100, StartSel=****, StopSel=****, 
                                     MaxFragments=5, FragmentDelimiter=\n\n---\n\n'
                                ) as content
                                FROM documents
                                WHERE url = :url
                                AND markdown_content IS NOT NULL
                                """),
                                {
                                    "url": url,
                                    "query": query,
                                    "max_words": min(chunk_size // 4, 500),  # Limit fragment size
                                },
                            ).scalar()

                            if headline_result:
                                # Add context header
                                content = f"## Search results for: {query}\n\n{headline_result}"
                                search_applied = True
                            else:
                                # Shouldn't happen if match was found, but fallback to full content
                                content = doc.markdown_content
                                search_applied = False
                        else:
                            # No matches found
                            content = f"No matches found for '{query}' in this document.\n\nYou may want to retrieve the full document without a search query."
                            search_applied = True
                    except Exception as e:
                        logger.error(f"Database query failed for document search: {e}")
                        # Fallback to full content if search fails
                        content = doc.markdown_content
                        search_applied = False
                else:
                    # Get full content if no search query
                    content = doc.markdown_content

                total_tokens = self._estimate_tokens(content)

                # Handle chunking if requested
                if max_tokens or chunk_index is not None:
                    content, chunk_info = self._chunk_content(
                        content,
                        max_tokens=max_tokens,
                        chunk_index=chunk_index,
                        chunk_size=chunk_size,
                    )
                    returned_tokens = self._estimate_tokens(content)
                else:
                    chunk_info = {"total_chunks": 1, "current_chunk": 0, "has_more": False}
                    returned_tokens = total_tokens

                # Prepare response with markdown and metadata
                response = {
                    "status": "success",
                    "url": url,
                    "title": doc.title or "Untitled",
                    "library_name": library_name or "Unknown",
                    "content_length": len(content),
                    "total_tokens": total_tokens,
                    "returned_tokens": returned_tokens,
                    "last_crawled": doc.last_crawled.isoformat() if doc.last_crawled else None,
                    "markdown_content": content,
                    **chunk_info,  # Add chunk information
                }

                # Add search information if query was applied
                if search_applied:
                    response["search_query"] = query
                    response["search_applied"] = True

                # Add metadata if available
                if doc.meta_data:
                    response["metadata"] = doc.meta_data

                return response

        except Exception as e:
            logger.error(f"Failed to get page markdown for URL {url}: {e}")
            return {"status": "error", "error": str(e), "url": url}

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses tiktoken for accurate counting, falls back to character-based estimation.
        """
        try:
            import tiktoken

            # Use cl100k_base encoding (used by GPT-4)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback: Approximate 4 characters per token
            return len(text) // 4

    def _chunk_content(
        self,
        content: str,
        max_tokens: Optional[int] = None,
        chunk_index: Optional[int] = None,
        chunk_size: int = 4000,
    ) -> tuple[str, dict]:
        """Chunk content by tokens with overlap.

        Returns:
            Tuple of (chunked_content, chunk_info)
        """
        # Split content into paragraphs for natural boundaries
        paragraphs = content.split("\n\n")

        # Calculate tokens per paragraph
        paragraph_tokens = []
        for para in paragraphs:
            tokens = self._estimate_tokens(para)
            paragraph_tokens.append((para, tokens))

        # Build chunks
        chunks = []
        current_chunk = []
        current_tokens = 0
        overlap_size = chunk_size // 10  # 10% overlap

        for para, tokens in paragraph_tokens:
            if current_tokens + tokens > chunk_size and current_chunk:
                # Save current chunk
                chunks.append("\n\n".join(current_chunk))

                # Start new chunk with overlap
                overlap_tokens = 0
                overlap_paras = []
                for p in reversed(current_chunk):
                    p_tokens = self._estimate_tokens(p)
                    if overlap_tokens + p_tokens <= overlap_size:
                        overlap_paras.insert(0, p)
                        overlap_tokens += p_tokens
                    else:
                        break

                current_chunk = overlap_paras
                current_tokens = overlap_tokens

            current_chunk.append(para)
            current_tokens += tokens

        # Add final chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # Handle max_tokens request
        if max_tokens:
            # Return content up to max_tokens
            result = []
            total = 0
            for chunk in chunks:
                chunk_tokens = self._estimate_tokens(chunk)
                if total + chunk_tokens <= max_tokens:
                    result.append(chunk)
                    total += chunk_tokens
                else:
                    # Add partial chunk
                    remaining = max_tokens - total
                    if remaining > 100:  # Only add if meaningful amount
                        # Approximate truncation
                        chars_per_token = len(chunk) // chunk_tokens
                        truncated = chunk[: remaining * chars_per_token]
                        result.append(truncated + "\n\n[Content truncated...]")
                    break

            return "\n\n".join(result), {
                "total_chunks": len(chunks),
                "current_chunk": 0,
                "has_more": len(result) < len(chunks),
            }

        # Handle chunk_index request
        if chunk_index is not None:
            if 0 <= chunk_index < len(chunks):
                return chunks[chunk_index], {
                    "total_chunks": len(chunks),
                    "current_chunk": chunk_index,
                    "has_more": chunk_index < len(chunks) - 1,
                }
            else:
                return "", {
                    "total_chunks": len(chunks),
                    "current_chunk": chunk_index,
                    "has_more": False,
                    "error": f"Chunk index {chunk_index} out of range (0-{len(chunks) - 1})",
                }

        # Default: return all content
        return content, {"total_chunks": len(chunks), "current_chunk": 0, "has_more": False}

    def _search_within_markdown_legacy(
        self, content: str, query: str, max_tokens: int = 2048
    ) -> str:
        """Search within markdown content and return relevant sections within token limit.

        Args:
            content: The markdown content to search
            query: Search query to match
            max_tokens: Maximum tokens to return (default: 2048)

        Returns:
            Filtered markdown content with relevant sections up to token limit
        """
        if not query or not content:
            return content

        # Split content into sections (by headers)
        lines = content.split("\n")
        sections = []
        current_section = []
        current_header = ""

        for line in lines:
            # Check if this is a header line
            if line.strip().startswith("#"):
                # Save previous section
                if current_section:
                    sections.append(
                        {
                            "header": current_header,
                            "content": "\n".join(current_section),
                            "full_content": current_header + "\n" + "\n".join(current_section)
                            if current_header
                            else "\n".join(current_section),
                        }
                    )

                # Start new section
                current_header = line
                current_section = []
            else:
                current_section.append(line)

        # Add final section
        if current_section or current_header:
            sections.append(
                {
                    "header": current_header,
                    "content": "\n".join(current_section),
                    "full_content": current_header + "\n" + "\n".join(current_section)
                    if current_header
                    else "\n".join(current_section),
                }
            )

        # Search for matching sections with token limit
        query_lower = query.lower()
        matching_sections = []
        total_tokens = 0

        for section in sections:
            # Check if query matches in header or content
            header_match = query_lower in section["header"].lower() if section["header"] else False
            content_match = query_lower in section["content"].lower()

            if header_match or content_match:
                section_tokens = self._estimate_tokens(section["full_content"])

                # Check if adding this section would exceed token limit
                if total_tokens + section_tokens <= max_tokens:
                    matching_sections.append(section["full_content"])
                    total_tokens += section_tokens
                elif total_tokens == 0:
                    # If first section is too large, truncate it
                    chars_per_token = (
                        len(section["full_content"]) // section_tokens if section_tokens > 0 else 4
                    )
                    truncated = section["full_content"][: max_tokens * chars_per_token]
                    matching_sections.append(
                        truncated + "\n\n[Section truncated to fit token limit...]"
                    )
                    break
                else:
                    # We've reached the token limit, add note
                    matching_sections.append(
                        f"\n[{len(matching_sections)} more matching sections omitted due to token limit]"
                    )
                    break

        # If no sections match, do a simple text search and return surrounding context
        if not matching_sections:
            lines = content.split("\n")
            context_lines = []
            estimated_tokens = 0

            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    # Add context around matching line
                    start = max(0, i - 5)
                    end = min(len(lines), i + 6)

                    # Estimate tokens for this context block
                    context_block = lines[start:end]
                    block_tokens = sum(self._estimate_tokens(line) for line in context_block)

                    # Check if we can fit this block
                    if estimated_tokens + block_tokens > max_tokens:
                        if estimated_tokens == 0:
                            # First match is too large, take what we can
                            tokens_so_far = 0
                            for j in range(start, end):
                                line_tokens = self._estimate_tokens(lines[j])
                                if tokens_so_far + line_tokens <= max_tokens:
                                    context_lines.append((lines[j], j, j))
                                    tokens_so_far += line_tokens
                                else:
                                    context_lines.append(
                                        ("[Results truncated to fit token limit...]", j, j)
                                    )
                                    break
                        else:
                            # We've hit the limit
                            context_lines.append(
                                (
                                    f"[Additional matches omitted due to {max_tokens} token limit]",
                                    i,
                                    i,
                                )
                            )
                        break

                    # Add section break if this is a new match area
                    if context_lines and start > context_lines[-1][1] + 1:
                        context_lines.append(("...", 0, 0))
                        estimated_tokens += 1  # Account for separator

                    # Add lines with context
                    for j in range(start, end):
                        if not any(
                            existing[1] <= j <= existing[2]
                            for existing in context_lines
                            if existing[0] != "..."
                        ):
                            context_lines.append((lines[j], j, j))

                    estimated_tokens += block_tokens

            if context_lines:
                # Remove duplicates and sort
                unique_lines = []
                seen_indices = set()

                for line_content, start_idx, end_idx in context_lines:
                    if (
                        line_content == "..."
                        or line_content.startswith("[")
                        or start_idx not in seen_indices
                    ):
                        unique_lines.append(line_content)
                        if line_content != "..." and not line_content.startswith("["):
                            seen_indices.add(start_idx)

                return "\n".join(unique_lines)

        # Return matching sections or original content if no matches
        return "\n\n".join(matching_sections) if matching_sections else content
