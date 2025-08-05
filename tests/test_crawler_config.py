"""Tests for simplified crawler configuration."""

import pytest
from unittest.mock import Mock, patch
from src.crawler.config import create_crawler_config


class TestCrawlerConfig:
    """Test unified crawler configuration."""
    
    def test_single_page_config(self):
        """Test configuration for single page crawl."""
        config = create_crawler_config(
            max_depth=0,  # 0 for single page
        )
        
        assert config is not None
        assert not hasattr(config, 'deep_crawl_strategy') or config.deep_crawl_strategy is None
        assert config.cache_mode.value == "bypass"
        assert config.stream is True
        assert config.exclude_external_links is True
    
    def test_deep_crawl_config(self):
        """Test configuration for deep crawl."""
        config = create_crawler_config(
            max_depth=2,
            domain_restrictions=["example.com"],
            include_patterns=["*docs*"],
            exclude_patterns=["*api*"],
        )
        
        assert config is not None
        assert config.deep_crawl_strategy is not None
        assert config.deep_crawl_strategy.max_depth == 2
        assert config.deep_crawl_strategy.include_external is False
    
    def test_config_without_llm_extraction(self):
        """Test configuration does not include LLM extraction (handled separately)."""
        config = create_crawler_config(
            max_depth=1,
        )
        
        assert config is not None
        # LLM extraction is now handled separately in page_crawler
        assert not hasattr(config, 'extraction_strategy') or config.extraction_strategy is None
    
    def test_config_without_api_key(self):
        """Test configuration without API key doesn't add extraction."""
        config = create_crawler_config(
            max_depth=1,
        )
        
        assert config is not None
        assert not hasattr(config, 'extraction_strategy') or config.extraction_strategy is None


# LLM extraction tests removed - functionality moved to llm_retry.py and handled separately from crawler config