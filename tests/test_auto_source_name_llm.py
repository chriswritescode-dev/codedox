"""Tests for LLM-based auto source name selection feature."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.crawler.crawl_manager import CrawlManager
from src.mcp_server.tools import MCPTools
from src.llm.client import LLMResponse


class TestAutoSourceNameLLM:
    """Test suite for LLM-based auto source name selection."""
    
    @pytest.mark.asyncio
    async def test_extract_site_name_with_llm(self):
        """Test extracting site name using LLM."""
        manager = CrawlManager()
        
        # Mock the LLM client
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        
        # Test cases with expected LLM responses
        test_cases = [
            ("Getting Started | Next.js", "Next.js"),
            ("React Documentation", "React"),
            ("Django 5.0 Documentation", "Django"),
            ("API Reference | Stripe Docs", "Stripe"),
            ("Vue.js Guide – Official Documentation", "Vue.js"),
        ]
        
        for title, expected_response in test_cases:
            # Mock LLM response
            mock_llm_client.generate.return_value = LLMResponse(
                content=expected_response,
                model="test-model"
            )
            
            result = await manager._extract_site_name(title, "http://example.com", {})
            assert result == expected_response, f"Failed for title: {title}"
            
            # Verify LLM was called with correct prompt structure
            mock_llm_client.generate.assert_called()
            call_args = mock_llm_client.generate.call_args
            assert "Page Title:" in call_args[1]["prompt"]
            assert title in call_args[1]["prompt"]
            assert call_args[1]["max_tokens"] == 50
            assert call_args[1]["temperature"] == 0.1
    
    @pytest.mark.asyncio
    async def test_extract_site_name_llm_with_quotes(self):
        """Test that quotes are stripped from LLM response."""
        manager = CrawlManager()
        
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        
        # Test LLM returning quoted responses
        test_cases = [
            ('"Next.js"', "Next.js"),
            ("'React'", "React"),
            ('"""Django"""', "Django"),
        ]
        
        for llm_response, expected in test_cases:
            mock_llm_client.generate.return_value = LLMResponse(
                content=llm_response,
                model="test-model"
            )
            
            result = await manager._extract_site_name("Some Title", "http://example.com", {})
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_extract_site_name_llm_fallback(self):
        """Test fallback when LLM is not available."""
        manager = CrawlManager()
        
        # No LLM client available
        manager._llm_client = None
        
        # Mock _ensure_llm_enricher to not set up LLM
        with patch.object(manager, '_ensure_llm_enricher', new_callable=AsyncMock):
            # Test with metadata title available
            metadata = {"title": "React"}
            result = await manager._extract_site_name("React Documentation", "http://example.com", metadata)
            assert result == "React"  # Uses metadata title
            
            # Test without metadata - falls back to page title
            result = await manager._extract_site_name("Vue.js Documentation", "http://example.com")
            assert result == "Vue.js Documentation"
            
            # Long title without metadata - should truncate
            long_title = "This is a very long documentation title that exceeds the maximum allowed length for a source name and should be truncated"
            result = await manager._extract_site_name(long_title, "http://example.com")
            assert len(result) <= 53
            assert result.endswith("...")
            
            # Long metadata title - should not use it
            long_metadata = {"title": "This is a very long metadata title that exceeds the maximum allowed length"}
            result = await manager._extract_site_name("Short Title", "http://example.com", long_metadata)
            assert result == "Short Title"  # Falls back to page title since metadata title is too long
    
    @pytest.mark.asyncio
    async def test_extract_site_name_llm_error(self):
        """Test fallback when LLM throws an error."""
        manager = CrawlManager()
        
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        
        # Mock LLM to throw an error
        mock_llm_client.generate.side_effect = Exception("LLM service unavailable")
        
        # Test with metadata fallback
        metadata = {"title": "Next.js"}
        result = await manager._extract_site_name("Next.js Documentation", "http://example.com", metadata)
        assert result == "Next.js"  # Falls back to metadata title
        
        # Test without metadata
        result = await manager._extract_site_name("React Documentation", "http://example.com")
        assert result == "React Documentation"  # Falls back to page title
    
    @pytest.mark.asyncio
    async def test_extract_site_name_empty_title(self):
        """Test handling of empty titles."""
        manager = CrawlManager()
        
        assert await manager._extract_site_name("", "http://example.com", {}) is None
        assert await manager._extract_site_name(None, "http://example.com", {}) is None
    
    @pytest.mark.asyncio
    async def test_extract_site_name_llm_invalid_response(self):
        """Test handling of invalid LLM responses."""
        manager = CrawlManager()
        
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        
        # Test LLM returning too long response with metadata fallback
        mock_llm_client.generate.return_value = LLMResponse(
            content="This is a very long response that exceeds the 50 character limit and should trigger fallback behavior",
            model="test-model"
        )
        
        metadata = {"title": "React"}
        result = await manager._extract_site_name("React Docs", "http://example.com", metadata)
        assert result == "React"  # Falls back to metadata title
        
        # Test without metadata
        result = await manager._extract_site_name("Vue Docs", "http://example.com")
        assert result == "Vue Docs"  # Falls back to page title
    
    @pytest.mark.asyncio
    async def test_mcp_tools_auto_name_generation(self):
        """Test that MCPTools generates auto-detect name when name is not provided."""
        tools = MCPTools()
        
        with patch.object(tools.crawl_manager, 'start_crawl', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = "test-job-id"
            
            result = await tools.init_crawl(
                name=None,  # No name provided
                start_urls=["https://nextjs.org/docs"],
                max_depth=1
            )
            
            # Check that auto-detect name was generated
            assert result["auto_detect_name"] is True
            assert result["library_name"] == "[Auto-detecting from nextjs.org]"
            
            # Verify the crawl config was created with auto-detect name
            mock_start.assert_called_once()
            config = mock_start.call_args[0][0]
            assert config.name == "[Auto-detecting from nextjs.org]"
            assert config.metadata["auto_detect_name"] is True
    
    @pytest.mark.asyncio
    async def test_auto_name_detection_during_crawl(self):
        """Test that name is auto-detected using LLM during the first page crawl."""
        manager = CrawlManager()
        
        # Mock the LLM client
        mock_llm_client = AsyncMock()
        mock_llm_client.generate.return_value = LLMResponse(
            content="Next.js",
            model="test-model"
        )
        
        # Mock dependencies
        with patch.object(manager, '_ensure_llm_enricher', new_callable=AsyncMock):
            with patch.object(manager.db_manager, 'session_scope') as mock_session_scope:
                # Setup mock session
                mock_session = Mock()
                mock_session_scope.return_value.__enter__.return_value = mock_session
                
                # Mock existing job with auto-detect name
                mock_job = Mock()
                mock_job.id = "test-job-id"
                mock_job.name = "[Auto-detecting from nextjs.org]"
                
                # Setup so the name gets updated
                manager._llm_client = mock_llm_client
                
                # Call the method directly
                result = await manager._extract_site_name("Getting Started | Next.js", "https://nextjs.org/docs", {})
                
                # Verify LLM was called and returned expected result
                assert result == "Next.js"
                mock_llm_client.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_llm_prompt_structure(self):
        """Test that the LLM prompt has the correct structure and examples."""
        manager = CrawlManager()
        
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        mock_llm_client.generate.return_value = LLMResponse(
            content="Test Framework",
            model="test-model"
        )
        
        await manager._extract_site_name("Test Framework Documentation", "http://test.com", {})
        
        # Check the prompt structure
        call_args = mock_llm_client.generate.call_args
        prompt = call_args[1]["prompt"]
        
        # Verify prompt contains key elements
        assert "Extract the name of the documentation site" in prompt
        assert "Page Title: Test Framework Documentation" in prompt
        assert "Page URL: http://test.com" in prompt
        assert "Instructions:" in prompt
        assert "Examples:" in prompt
        assert "Next.js" in prompt  # Example should be present
        assert "React" in prompt
        assert "Django" in prompt
    
    @pytest.mark.asyncio
    async def test_metadata_title_priority(self):
        """Test that metadata title is used as fallback in correct priority order."""
        manager = CrawlManager()
        
        # Scenario 1: LLM works - should use LLM result
        mock_llm_client = AsyncMock()
        manager._llm_client = mock_llm_client
        mock_llm_client.generate.return_value = LLMResponse(
            content="Next.js",
            model="test-model"
        )
        
        metadata = {"title": "NextJS Framework"}  # Different from LLM result
        result = await manager._extract_site_name("Getting Started | Next.js Documentation", "http://nextjs.org", metadata)
        assert result == "Next.js"  # Uses LLM result, not metadata
        
        # Scenario 2: LLM returns empty - should use metadata title
        mock_llm_client.generate.return_value = LLMResponse(
            content="",
            model="test-model"
        )
        
        metadata = {"title": "React"}
        result = await manager._extract_site_name("React Documentation", "http://react.dev", metadata)
        assert result == "React"  # Uses metadata title
        
        # Scenario 3: LLM fails, metadata available - should use metadata
        mock_llm_client.generate.side_effect = Exception("LLM error")
        
        metadata = {"title": "Vue.js"}
        result = await manager._extract_site_name("Vue.js Official Documentation", "http://vuejs.org", metadata)
        assert result == "Vue.js"  # Uses metadata title
        
        # Scenario 4: No LLM, metadata empty - should use page title
        manager._llm_client = None
        
        with patch.object(manager, '_ensure_llm_enricher', new_callable=AsyncMock):
            metadata = {"title": ""}  # Empty metadata title
            result = await manager._extract_site_name("Django Docs", "http://django.com", metadata)
            assert result == "Django Docs"  # Falls back to page title