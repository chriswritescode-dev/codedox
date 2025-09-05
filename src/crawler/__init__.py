"""Web crawling package."""

# Import non-crawl4ai dependent modules first
from .health_monitor import CrawlHealthMonitor, get_health_monitor
from .job_manager import JobManager
from .progress_tracker import ProgressTracker
from .result_processor import ResultProcessor
from .upload_processor import UploadConfig, UploadProcessor

# Try to import crawl4ai-dependent modules
try:
    from .config import create_browser_config, create_crawler_config
    from .crawl_manager import CrawlConfig, CrawlManager
    from .page_crawler import CrawlResult, PageCrawler
except ImportError:
    # Crawl4AI not installed - crawling features won't work
    # but upload features will still work
    create_browser_config = None
    create_crawler_config = None
    CrawlConfig = None
    CrawlManager = None
    CrawlResult = None
    PageCrawler = None

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
]
