"""Simplified crawler configuration."""

from typing import Optional, List

from crawl4ai import (
    CrawlerRunConfig,
    BrowserConfig,  
    CacheMode,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, URLPatternFilter


def create_browser_config(
    headless: bool = True,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    user_agent: str = None,
) -> BrowserConfig:
    """Create browser configuration."""
    config = BrowserConfig(
        headless=headless,
        viewport={"width": viewport_width, "height": viewport_height},
    )
    
    # Set custom user agent if provided
    if user_agent:
        config.user_agent = user_agent
    
    return config


def create_crawler_config(
    max_depth: int = 0,
    domain_restrictions: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    user_agent: Optional[str] = None,
    max_pages: Optional[int] = None,
) -> CrawlerRunConfig:
    """Create unified crawler configuration for both single page and deep crawl.
    
    Args:
        max_depth: Maximum crawl depth (0 for single page)
        domain_restrictions: List of allowed domains
        include_patterns: URL patterns to include
        exclude_patterns: URL patterns to exclude
        user_agent: Custom user agent string for HTTP requests
        max_pages: Maximum number of pages to crawl
    
    Returns:
        Configured CrawlerRunConfig instance
    """
    config_dict = {
        
        "wait_until": "networkidle",
        "page_timeout": 60000,
        "cache_mode": CacheMode.BYPASS,
        "stream": True,
        "verbose": True,
        "exclude_external_links": True,
    }
    
    # Add custom user agent if provided
    if user_agent:
        config_dict["user_agent"] = user_agent

    # Add deep crawl strategy if max_depth > 0
    if max_depth > 0:
        # Create filters
        filters = []

        if domain_restrictions:
            filters.append(DomainFilter(allowed_domains=domain_restrictions))

        if include_patterns:
            filters.append(
                URLPatternFilter(
                    patterns=include_patterns, 
                    use_glob=True, 
                    reverse=False
                )
            )

        if exclude_patterns:
            filters.append(
                URLPatternFilter(
                    patterns=exclude_patterns, 
                    use_glob=True, 
                    reverse=True
                )
            )

        # Create deep crawl strategy
        strategy_kwargs = {
            "max_depth": max_depth,
            "include_external": False,
        }
        if max_pages is not None:
            strategy_kwargs["max_pages"] = max_pages
        
        # Only add filter_chain if we have filters
        if filters:
            strategy_kwargs["filter_chain"] = FilterChain(filters)
        
        config_dict["deep_crawl_strategy"] = BFSDeepCrawlStrategy(**strategy_kwargs)

    return CrawlerRunConfig(**config_dict)
