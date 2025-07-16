"""Page crawling implementation using Crawl4AI."""

import asyncio
import logging
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin

from crawl4ai import (
    AsyncWebCrawler,
    RateLimiter,
    SemaphoreDispatcher,
)

from .config import create_deep_crawl_config, create_single_page_config, BrowserConfig
from ..parser import CodeExtractor
from ..database import FailedPage, get_db_manager

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result from crawling a single page."""

    url: str
    title: str
    content: str
    content_hash: str
    links: List[Dict[str, str]]
    code_blocks: List[Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    markdown_content: Optional[str] = None


class PageCrawler:
    """Handles page crawling operations."""

    def __init__(self, browser_config: BrowserConfig, code_extractor: CodeExtractor):
        """Initialize page crawler.

        Args:
            browser_config: Browser configuration
            code_extractor: Code extractor instance
        """
        self.browser_config = browser_config
        self.code_extractor = code_extractor
        self.db_manager = get_db_manager()

    async def crawl_pages(
        self,
        urls: List[str],
        job_id: str,
        max_depth: int = 0,
        job_config: Optional[Dict[str, Any]] = None,
    ) -> List[CrawlResult]:
        """Crawl multiple pages.

        Args:
            urls: URLs to crawl
            job_id: Job ID
            max_depth: Maximum crawl depth (0 for single page)
            job_config: Job configuration

        Returns:
            List of crawl results
        """
        all_results = []

        for url in urls:
            results = await self.crawl_page(url, job_id, 0, max_depth, job_config)
            if results:
                all_results.extend(results)

        return all_results

    async def crawl_page(
        self,
        url: str,
        job_id: str,
        depth: int,
        max_depth: int = 0,
        job_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[CrawlResult]]:
        """Crawl a page or site using Crawl4AI.

        Args:
            url: URL to crawl
            job_id: Job ID for tracking
            depth: Current crawl depth
            max_depth: Maximum depth for deep crawling (0 for single page)
            job_config: Job configuration

        Returns:
            List of CrawlResult objects or None if failed
        """
        results = []

        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                if max_depth > 0:
                    # Deep crawl
                    results = await self._deep_crawl(crawler, url, job_id, max_depth, job_config)
                else:
                    # Single page crawl
                    result = await self._single_page_crawl(crawler, url, job_id, depth)
                    if result:
                        results.append(result)

                return results if results else None

        except asyncio.CancelledError:
            # Re-raise cancellation to properly propagate it
            logger.info(f"Crawl cancelled for {url}")
            raise
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            # Don't try to record failed page if it's a cancellation-related error
            if "cancelled" not in str(e).lower():
                try:
                    await self._record_failed_page(job_id, url, str(e))
                except asyncio.CancelledError:
                    # If recording fails due to cancellation, just re-raise
                    raise
            return None

    async def _deep_crawl(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        job_id: str,
        max_depth: int,
        job_config: Optional[Dict[str, Any]] = None,
    ) -> List[CrawlResult]:
        """Perform deep crawl using BFS strategy.

        Args:
            crawler: Crawler instance
            url: Start URL
            job_id: Job ID
            max_depth: Maximum depth
            job_config: Job configuration

        Returns:
            List of crawl results
        """
        logger.info(f"Starting deep crawl from {url} with max_depth={max_depth}")

        # Create configuration
        config = create_deep_crawl_config(
            start_urls=[url],
            max_depth=max_depth,
            domain_restrictions=job_config.get("domain_restrictions") if job_config else None,
            include_patterns=job_config.get("include_patterns") if job_config else None,
            exclude_patterns=job_config.get("exclude_patterns") if job_config else None,
            max_pages=job_config.get("max_pages", 1000) if job_config else 1000,
        )

        # Configure rate limiter and dispatcher
        max_concurrent = job_config.get("max_concurrent_crawls", 20) if job_config else 20
        rate_limiter = RateLimiter(base_delay=(1.0, 2.0), max_delay=30.0, max_retries=4)
        dispatcher = SemaphoreDispatcher(
            max_session_permit=max_concurrent,
            rate_limiter=rate_limiter,
        )

        results = []
        crawled_count = 0

        # Crawl with streaming
        crawl_results = await crawler.arun(url, config=config, dispatcher=dispatcher)
        async for result in crawl_results:
            crawled_count += 1
            
            # Check if job is cancelled
            with self.db_manager.session_scope() as session:
                from ..database.models import CrawlJob
                job = session.query(CrawlJob).filter_by(id=job_id).first()
                if job and job.status == "cancelled":
                    logger.info(f"Crawl job {job_id} is cancelled - stopping deep crawl")
                    raise asyncio.CancelledError("Job cancelled by user")

            if result.success:
                # Get depth from metadata
                page_depth = 0
                if hasattr(result, "metadata") and result.metadata and "depth" in result.metadata:
                    page_depth = result.metadata["depth"]

                # Convert to our format
                crawl_result = self._convert_library_result(result, page_depth)
                if crawl_result:
                    results.append(crawl_result)
                    logger.info(f"Crawled page {crawled_count}: {result.url} (depth: {page_depth})")
            else:
                logger.warning(f"Failed to crawl {result.url}: {result.error_message}")
                await self._record_failed_page(job_id, result.url, result.error_message)

        return results

    async def _single_page_crawl(
        self, crawler: AsyncWebCrawler, url: str, job_id: str, depth: int
    ) -> Optional[CrawlResult]:
        """Crawl a single page.

        Args:
            crawler: Crawler instance
            url: URL to crawl
            job_id: Job ID
            depth: Crawl depth

        Returns:
            CrawlResult or None
        """
        logger.info(f"Crawling single page: {url}")
        
        # Check if job is cancelled before crawling
        with self.db_manager.session_scope() as session:
            from ..database.models import CrawlJob
            job = session.query(CrawlJob).filter_by(id=job_id).first()
            if job and job.status == "cancelled":
                logger.info(f"Crawl job {job_id} is cancelled - skipping single page crawl")
                raise asyncio.CancelledError("Job cancelled by user")

        # Configure for single page
        config = create_single_page_config()

        # Crawl single page
        result_container = await crawler.arun(url, config=config)

        # Handle result container
        if hasattr(result_container, "results"):
            # Multiple results
            for result in result_container.results:
                if result.success:
                    crawl_result = self._convert_library_result(result, depth)
                    if crawl_result:
                        logger.info(f"Successfully crawled: {url}")
                        return crawl_result
                else:
                    logger.error(f"Failed to crawl {url}: {result.error_message}")
                    await self._record_failed_page(job_id, url, result.error_message)
        else:
            # Single result
            result = result_container
            if result.success:
                crawl_result = self._convert_library_result(result, depth)
                if crawl_result:
                    logger.info(f"Successfully crawled: {url}")
                    return crawl_result
            else:
                logger.error(f"Failed to crawl {url}: {result.error_message}")
                await self._record_failed_page(job_id, url, result.error_message)

        return None

    def _convert_library_result(self, result: Any, depth: int) -> Optional[CrawlResult]:
        """Convert Crawl4AI result to our format.

        Args:
            result: Crawl4AI result
            depth: Page depth

        Returns:
            CrawlResult or None
        """
        try:
            logger.debug(f"Converting result for URL: {result.url}")

            metadata = {
                "depth": depth,
                "status_code": 200 if result.success else 0,
                "success": result.success,
            }

            # Extract title
            title = ""
            if hasattr(result, "metadata") and result.metadata:
                title = result.metadata.get("title", "")

            # Extract links
            links = []
            if hasattr(result, "links") and result.links:
                for link in result.links.get("internal", []):
                    links.append(
                        {
                            "url": link.get("href", ""),
                            "text": link.get("text", ""),
                            "title": link.get("title", ""),
                        }
                    )

            # Extract markdown content
            markdown_content = None
            if hasattr(result, "markdown") and result.markdown:
                if isinstance(result.markdown, dict):
                    # markdown_content = result.markdown.get("raw_markdown", "")
                    # if not markdown_content:
                    markdown_content = result.markdown.get("fit_markdown", "")
                elif isinstance(result.markdown, str):
                    markdown_content = result.markdown
                else:
                    markdown_content = ""

                if not markdown_content:
                    logger.warning("No markdown content found in result")
                    return None
            else:
                logger.warning("No markdown attribute in result")
                return None

            # Extract code blocks
            logger.info("Extracting code blocks from markdown content...")
            code_blocks = self.code_extractor.extract_from_content(
                markdown_content, result.url, "markdown", markdown_content
            )
            logger.info(f"Extracted {len(code_blocks)} code blocks")

            # Calculate content hash
            content_hash = hashlib.md5((markdown_content or "").encode("utf-8")).hexdigest()

            # Add metadata
            if hasattr(result, "metadata") and result.metadata:
                metadata["crawl4ai_metadata"] = result.metadata

            return CrawlResult(
                url=result.url,
                title=title,
                content=markdown_content or "",
                content_hash=content_hash,
                links=links,
                code_blocks=code_blocks,
                metadata=metadata,
                markdown_content=markdown_content,
            )

        except Exception as e:
            logger.error(f"Error converting result: {e}")
            return None

    async def _record_failed_page(self, job_id: str, url: str, error_message: str) -> None:
        """Record a failed page.

        Args:
            job_id: Job ID
            url: Failed URL
            error_message: Error message
        """
        try:
            from uuid import UUID
            from ..database.models import CrawlJob

            # Handle job_id format
            if isinstance(job_id, str):
                try:
                    job_uuid = UUID(job_id)
                except ValueError:
                    logger.error(f"Invalid job ID format: {job_id}")
                    return
            else:
                job_uuid = job_id

            with self.db_manager.session_scope() as session:
                # First check if crawl job exists
                crawl_job = session.query(CrawlJob).filter_by(id=job_uuid).first()
                if not crawl_job:
                    logger.warning(f"Crawl job {job_uuid} not found in database - skipping failed page recording")
                    return
                
                # Check if job is cancelled
                if crawl_job.status == "cancelled":
                    logger.info(f"Crawl job {job_uuid} is cancelled - stopping crawler")
                    raise asyncio.CancelledError("Job cancelled by user")

                # Check if already exists
                existing = (
                    session.query(FailedPage).filter_by(crawl_job_id=job_uuid, url=url).first()
                )

                if not existing:
                    failed_page = FailedPage(
                        crawl_job_id=job_uuid,
                        url=url,
                        error_message=error_message,
                        failed_at=datetime.utcnow(),
                    )
                    session.add(failed_page)
                    session.commit()
                    logger.info(f"Recorded failed page: {url}")
        except Exception as e:
            logger.error(f"Failed to record failed page {url}: {e}")
