"""MCP tool implementations."""

import logging
from datetime import datetime
from typing import Any

from ..config import get_settings
from ..crawler import CrawlConfig, CrawlManager
from ..database import CodeSearcher, get_db_manager

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
        name: str | None,
        start_urls: list[str],
        max_depth: int = 1,
        domain_filter: str | None = None,
        url_patterns: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        max_concurrent_crawls: int | None = None
    ) -> dict[str, Any]:
        """Initialize a new crawl job.
        
        Args:
            name: Library/framework name (auto-detected if not provided)
            start_urls: URLs to start crawling
            max_depth: Maximum crawl depth (0-3)
            domain_filter: Optional domain restriction
            url_patterns: Optional list of URL patterns to filter (e.g., ["*docs*", "*guide*"]) will keep only URLs matching these patterns
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
                domain = parsed.netloc.replace('www.', '')
                name = f"[Auto-detecting from {domain}]"
                metadata['auto_detect_name'] = True

            metadata.update({
                'library_name': name,
                'initiated_via': 'mcp',
                'initiated_at': datetime.now().isoformat()
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
                include_patterns=url_patterns or [],
                metadata=metadata,
                max_concurrent_crawls=max_concurrent_crawls or settings.crawling.max_concurrent_crawls
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
                "url_patterns": url_patterns or [],
                "auto_detect_name": metadata.get('auto_detect_name', False)
            }

        except Exception as e:
            logger.error(f"Failed to initialize crawl: {e}")
            return {
                "error": str(e),
                "status": "failed",
                "library_name": name
            }


    async def search_libraries(
        self,
        query: str = "",
        limit: int = 20,
        page: int = 1
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
                    query=query,
                    limit=limit,
                    offset=offset
                )

                if not libraries:
                    if query:
                        return {
                            "status": "no_matches",
                            "message": f"No libraries found matching '{query}'",
                            "suggestion": "Try a different search term or check if the library has been crawled"
                        }
                    else:
                        return {
                            "status": "empty",
                            "message": "No libraries have been crawled yet",
                            "suggestion": "Use init_crawl to add documentation sources"
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
                                "library_id": lib['library_id'],
                                "name": lib['name'],
                                "description": lib['description'],
                                "snippet_count": lib['snippet_count']
                            }
                            for lib in libraries
                        ],
                        "total_count": total_count,
                        "page": page,
                        "total_pages": total_pages,
                        "message": message
                    }

                # For searches with query, find the best match
                best_match = libraries[0]  # Already sorted by relevance
                other_matches = libraries[1:5] if len(libraries) > 1 else []

                # Determine match quality
                exact_match = best_match['name'].lower() == query.lower()
                strong_match = query.lower() in best_match['name'].lower()

                # Build response
                response: dict[str, Any] = {
                    "status": "success",
                    "selected_library": {
                        "library_id": best_match['library_id'],
                        "name": best_match['name'],
                        "description": best_match['description'],
                        "snippet_count": best_match['snippet_count']
                    }
                }

                # Add versions if available
                if 'versions' in best_match:
                    response["selected_library"]["versions"] = best_match['versions']

                # Add explanation
                if exact_match:
                    response["explanation"] = f"Exact match found for '{query}'"
                elif strong_match:
                    response["explanation"] = f"Strong match found: '{best_match['name']}' contains '{query}'"
                else:
                    response["explanation"] = f"Best match based on similarity: '{best_match['name']}'"

                # Add similarity score if available
                if 'similarity_score' in best_match:
                    response["match_confidence"] = f"{best_match['similarity_score']:.2%}"

                # Acknowledge other matches
                if other_matches:
                    response["other_matches"] = [
                        {
                            "library_id": lib['library_id'],
                            "name": lib['name'],
                            "snippet_count": lib['snippet_count']
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
                if best_match['snippet_count'] < 10:
                    response["warning"] = "This library has limited documentation coverage"

                return response

        except Exception as e:
            logger.error(f"Failed to search libraries: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to search libraries"
            }

    async def get_content(
        self,
        library_id: str,
        query: str | None = None,
        limit: int = 20,
        page: int = 1
    ) -> str:
        """Get content from a specific library, optionally filtered by search query.
        
        Args:
            library_id: Library ID (UUID) or library name - can use either format
            query: Optional search query to filter results
            limit: Maximum results per page (default: 20)
            page: Page number for paginated results (1-indexed)
            
        Returns:
            Formatted search results as string
        """
        try:
            with self.db_manager.session_scope() as session:
                searcher = CodeSearcher(session)

                # Check if library_id is a valid UUID
                import re
                uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
                is_uuid = bool(uuid_pattern.match(library_id))

                actual_library_id = library_id
                library_name = library_id  # Default to the input for display

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
                                similarity = SequenceMatcher(None, library_id.lower(), lib['name'].lower()).ratio()
                                scored_libs.append((lib, similarity))

                            # Sort by similarity and take top 5
                            scored_libs.sort(key=lambda x: x[1], reverse=True)
                            suggestions = []
                            for lib, score in scored_libs[:5]:
                                if score > settings.search.library_suggestion_threshold:  # Only show somewhat similar libraries
                                    suggestions.append(f"  - {lib['name']} (similarity: {score:.0%}, snippets: {lib['snippet_count']})")

                            if suggestions:
                                return (f"❌ No library found matching '{library_id}'.\n\n"
                                       f"📚 Did you mean one of these?\n" + "\n".join(suggestions) + "\n\n"
                                       "💡 Tip: Use the exact library name or copy the ID from search_libraries.")
                            else:
                                return f"❌ No library found matching '{library_id}' and no similar libraries found.\n\n💡 Use search_libraries to find available libraries."
                        else:
                            return "❌ No libraries have been crawled yet. Use init_crawl to add documentation sources."

                    # Check for exact match first (case-insensitive)
                    exact_match = None
                    for lib in libraries:
                        if lib['name'].lower() == library_id.lower():
                            exact_match = lib
                            break

                    if exact_match:
                        # Use exact match
                        actual_library_id = exact_match['library_id']
                        library_name = exact_match['name']
                        logger.info(f"Exact match found: '{library_name}' for query '{library_id}'")
                    elif len(libraries) == 1:
                        # Single match, use it
                        actual_library_id = libraries[0]['library_id']
                        library_name = libraries[0]['name']
                        logger.info(f"Single match found: '{library_name}' for query '{library_id}'")
                    elif len(libraries) > 1:
                        # Check if we have a clear winner
                        first_score = libraries[0].get('similarity_score', 0)
                        second_score = libraries[1].get('similarity_score', 0) if len(libraries) > 1 else 0

                        # Use configurable thresholds: auto-select if first is good and significantly better than second
                        if first_score > settings.search.library_auto_select_threshold and (first_score - second_score) > settings.search.library_auto_select_gap:
                            actual_library_id = libraries[0]['library_id']
                            library_name = libraries[0]['name']
                            logger.info(f"Auto-selected best match: '{library_name}' (score: {first_score:.2f}) for query '{library_id}'")
                        else:
                            # Multiple close matches, ask user to be more specific
                            suggestions = []
                            for i, lib in enumerate(libraries[:5]):
                                score = lib.get('similarity_score', 0)
                                snippets = lib.get('snippet_count', 0)
                                # Add emoji indicators for clarity
                                if i == 0:
                                    emoji = "🥇"
                                elif i == 1:
                                    emoji = "🥈"
                                elif i == 2:
                                    emoji = "🥉"
                                else:
                                    emoji = "  "
                                suggestions.append(f"{emoji} {lib['name']} (match: {score:.0%}, snippets: {snippets})")

                            return (f"🤔 Multiple libraries match '{library_id}'. Please be more specific:\n\n" +
                                   "\n".join(suggestions) + "\n\n"
                                   "💡 Tip: Use the exact library name for best results.")

                # Calculate offset for pagination
                offset = (page - 1) * limit

                # Search with resolved library_id
                snippets, total_count = searcher.search(
                    query=query or "",  # Use empty string if query is None
                    job_id=actual_library_id,
                    limit=limit,
                    offset=offset,
                    include_context=False  # Don't include context in search results
                )

                if not snippets:
                    if query:
                        no_results_msg = f"No results found for query '{query}' in library '{library_name}'"
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
                    header += f" for query '{query}' in library '{library_name}'"
                else:
                    header += f" in library '{library_name}'"
                header += "\n\n"

                return header + formatted_results

        except Exception as e:
            logger.error(f"Failed to search content: {e}")
            return f"Error searching content: {str(e)}"

    async def get_crawl_status(self, job_id: str) -> dict[str, Any]:
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

    async def cancel_crawl(self, job_id: str) -> dict[str, Any]:
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
