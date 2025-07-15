"""Crawler configuration factory functions."""

from typing import Optional, List, Dict, Any

from crawl4ai import (
    CrawlerRunConfig,
    BrowserConfig,
    DefaultMarkdownGenerator,
    CacheMode,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, URLPatternFilter

# Create prune filter
prune_filter = PruningContentFilter()


def create_deep_crawl_config(
    start_urls: List[str],
    max_depth: int = 2,
    domain_restrictions: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    max_pages: int = 1000,
) -> CrawlerRunConfig:
    """Create a CrawlerRunConfig for deep crawling.

    Args:
        start_urls: URLs to start crawling from
        max_depth: Maximum crawl depth
        domain_restrictions: List of allowed domains
        include_patterns: URL patterns to include
        exclude_patterns: URL patterns to exclude
        max_pages: Maximum number of pages to crawl

    Returns:
        Configured CrawlerRunConfig instance
    """
    # Create filters
    filters = []

    # Domain filter
    if domain_restrictions:
        filters.append(DomainFilter(allowed_domains=domain_restrictions))

    # URL pattern filters
    if include_patterns:
        filters.append(
            URLPatternFilter(
                patterns=include_patterns, use_glob=True, reverse=False  # Match patterns
            )
        )
    if exclude_patterns:
        filters.append(
            URLPatternFilter(
                patterns=exclude_patterns, use_glob=True, reverse=True  # Exclude patterns
            )
        )

    # Create filter chain
    filter_chain = FilterChain(filters) if filters else None

    # Create deep crawl strategy
    strategy = BFSDeepCrawlStrategy(
        max_depth=max_depth,
        include_external=False,
        filter_chain=filter_chain,
        max_pages=max_pages,
    )

    # Create and return config
    return CrawlerRunConfig(
        deep_crawl_strategy=strategy,
        markdown_generator=DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "escape_html": False,
                "ignore_images": True,
            },
            content_source="raw_html",
            content_filter=prune_filter,
        ),
        wait_until="domcontentloaded",
        page_timeout=30000,
        exclude_external_links=True,
        cache_mode=CacheMode.BYPASS,
        stream=True,
    )


def create_single_page_config() -> CrawlerRunConfig:
    """Create a CrawlerRunConfig for single page crawling.

    Returns:
        Configured CrawlerRunConfig instance for single page crawling
    """
    return CrawlerRunConfig(
        excluded_tags=["nav", "footer", "header", "aside", "button", "form"],
        markdown_generator=DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "escape_html": False,
                "ignore_images": True,
            },
            content_source="raw_html",
            content_filter=prune_filter,
        ),
        wait_until="domcontentloaded",
        page_timeout=60000,
        cache_mode=CacheMode.BYPASS,
    )


def create_browser_config(
    headless: bool = True,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    extra_headers: Optional[Dict[str, str]] = None,
) -> BrowserConfig:
    """Create a BrowserConfig instance.

    Args:
        headless: Whether to run browser in headless mode
        viewport_width: Browser viewport width
        viewport_height: Browser viewport height
        extra_headers: Additional HTTP headers

    Returns:
        Configured BrowserConfig instance
    """
    config_dict = {
        "headless": headless,
        "viewport": {"width": viewport_width, "height": viewport_height},
    }

    # BrowserConfig doesn't support extra_headers directly
    # Headers would need to be set on individual requests

    return BrowserConfig(**config_dict)
