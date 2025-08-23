"""Utility functions for crawling operations."""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)








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


    return url


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



