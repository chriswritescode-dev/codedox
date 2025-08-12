"""Web crawling package."""

from .config import create_browser_config, create_crawler_config
from .crawl_manager import CrawlConfig, CrawlManager
from .health_monitor import CrawlHealthMonitor, get_health_monitor
from .job_manager import JobManager
from .page_crawler import CrawlResult, PageCrawler
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor
from .upload_processor import UploadConfig, UploadProcessor
from .utils import is_allowed_domain, matches_patterns, should_crawl_url

__all__ = [
    # Main classes
    "CrawlManager",
    "CrawlConfig",
    "CrawlResult",
    "UploadProcessor",
    "UploadConfig",
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
