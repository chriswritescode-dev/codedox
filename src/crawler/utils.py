"""Utility functions for crawling operations."""

import logging
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_allowed_domain(url: str, domain_restrictions: List[str]) -> bool:
    """Check if URL matches domain restrictions.

    Args:
        url: URL to check
        domain_restrictions: List of allowed domains

    Returns:
        True if allowed
    """
    if not domain_restrictions:
        return True

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for restriction in domain_restrictions:
        restriction = restriction.lower()
        if restriction.startswith("*."):
            # Wildcard subdomain
            if domain.endswith(restriction[2:]) or domain == restriction[2:]:
                return True
        elif domain == restriction or domain.endswith(f".{restriction}"):
            return True

    return False


def matches_patterns(url: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    """Check if URL matches include/exclude patterns.

    Args:
        url: URL to check
        include_patterns: Patterns to include
        exclude_patterns: Patterns to exclude

    Returns:
        True if matches
    """
    # Check exclude patterns first
    for pattern in exclude_patterns:
        if pattern in url:
            return False

    # If no include patterns, include everything not excluded
    if not include_patterns:
        return True

    # Check include patterns
    for pattern in include_patterns:
        if pattern in url:
            return True

    return False


def normalize_url(url: str) -> str:
    """Normalize URL for comparison.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    # Remove trailing slash
    if url.endswith("/"):
        url = url[:-1]

    # Remove fragment
    if "#" in url:
        url = url.split("#")[0]

    # Remove common tracking parameters
    if "?" in url:
        parsed = urlparse(url)
        # You could add logic here to remove tracking params

    return url


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL.

    Args:
        url: URL to extract from

    Returns:
        Domain or None
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception as e:
        logger.error(f"Failed to extract domain from {url}: {e}")
        return None


def is_valid_url(url: str) -> bool:
    """Check if URL is valid.

    Args:
        url: URL to check

    Returns:
        True if valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def should_crawl_url(
    url: str,
    domain_restrictions: List[str],
    include_patterns: List[str],
    exclude_patterns: List[str],
) -> bool:
    """Check if URL should be crawled based on all restrictions.

    Args:
        url: URL to check
        domain_restrictions: Domain restrictions
        include_patterns: Include patterns
        exclude_patterns: Exclude patterns

    Returns:
        True if should crawl
    """
    # Check if valid
    if not is_valid_url(url):
        return False

    # Check domain
    if not is_allowed_domain(url, domain_restrictions):
        return False

    # Check patterns
    if not matches_patterns(url, include_patterns, exclude_patterns):
        return False

    return True
