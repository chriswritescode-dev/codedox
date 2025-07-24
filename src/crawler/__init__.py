"""Web crawling package."""

from .crawl_manager import CrawlManager, CrawlConfig
from .health_monitor import CrawlHealthMonitor, get_health_monitor
from .config import create_crawler_config, create_browser_config
from .job_manager import JobManager
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor
from .page_crawler import PageCrawler, CrawlResult
from .utils import is_allowed_domain, matches_patterns, should_crawl_url

__all__ = [
    # Main classes
    "CrawlManager",
    "CrawlConfig",
    "CrawlResult",
    # Managers
    "JobManager",
    "ProgressTracker",
    "ResultProcessor",
    "PageCrawler",
    # Health monitoring
    "CrawlHealthMonitor",
    "get_health_monitor",
    # Config factory functions
    "create_crawler_config",
    "create_browser_config",
    # Utility functions
    "is_allowed_domain",
    "matches_patterns",
    "should_crawl_url",
]
