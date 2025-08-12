"""Domain utilities for crawl job management."""

from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Extract domain from URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain string (e.g., 'nextjs.org')
        
    Raises:
        ValueError: If URL is invalid or has no domain
    """
    try:
        # Handle URLs without scheme by adding one
        if not url.startswith(('http://', 'https://')):
            # Check if it looks like a domain (contains dots and no spaces)
            if '.' in url and ' ' not in url:
                url = f"https://{url}"
            else:
                raise ValueError(f"Invalid URL format: {url}")

        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValueError(f"Invalid URL or no domain found: {url}")
        return parsed.netloc.lower()
    except Exception as e:
        raise ValueError(f"Failed to parse URL '{url}': {e}")


def extract_domains_from_urls(urls: list[str]) -> list[str]:
    """Extract unique domains from a list of URLs.
    
    Args:
        urls: List of URLs to extract domains from
        
    Returns:
        List of unique domains
    """
    domains = []
    for url in urls:
        try:
            domain = extract_domain(url)
            if domain not in domains:
                domains.append(domain)
        except ValueError:
            # Skip invalid URLs
            continue
    return domains


def get_primary_domain(start_urls: list[str]) -> str | None:
    """Get the primary domain from start URLs.
    
    Args:
        start_urls: List of starting URLs for crawl
        
    Returns:
        Primary domain or None if no valid domains found
    """
    domains = extract_domains_from_urls(start_urls)
    return domains[0] if domains else None


def domains_match(url1: str, url2: str) -> bool:
    """Check if two URLs have the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if domains match, False otherwise
    """
    try:
        domain1 = extract_domain(url1)
        domain2 = extract_domain(url2)
        return domain1 == domain2
    except ValueError:
        return False
