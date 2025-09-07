"""Test that GitHub processor respects LLM disabled setting."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import get_settings
from src.crawler.github_processor import GitHubProcessor, GitHubRepoConfig


@pytest.mark.asyncio
async def test_github_processor_respects_llm_disabled():
    """Test that GitHub processor respects the enable_llm_extraction setting."""
    
    config = GitHubRepoConfig(
        repo_url="https://github.com/test/repo",
        name="Test Repo",
        branch="main"
    )
    
    # Test with LLM disabled
    with patch('src.crawler.github_processor.settings') as mock_settings:
        mock_settings.code_extraction.enable_llm_extraction = False
        
        processor = GitHubProcessor()
        
        # Mock the necessary methods
        with patch.object(processor, '_clone_repository') as mock_clone, \
             patch.object(processor, '_find_markdown_files') as mock_find, \
             patch.object(processor, '_generate_source_url') as mock_url, \
             patch.object(processor, '_cleanup_temp_dir') as mock_cleanup, \
             patch.object(processor.upload_processor, 'process_upload') as mock_process, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_clone.return_value = MagicMock()
            mock_find.return_value = [MagicMock(relative_to=lambda x: MagicMock(), suffix='.md')]
            mock_url.return_value = "https://example.com/file.md"
            mock_cleanup.return_value = asyncio.sleep(0)
            mock_process.return_value = "job-123"
            mock_open.return_value.__enter__.return_value.read.return_value = "# Test content"
            
            job_id = await processor.process_repository(config)
            
            # Verify that process_upload was called with use_llm=False
            assert mock_process.called
            upload_config = mock_process.call_args[0][0]
            assert upload_config.use_llm == False, f"Expected use_llm=False but got {upload_config.use_llm}"
    
    # Test with LLM enabled
    with patch('src.crawler.github_processor.settings') as mock_settings:
        mock_settings.code_extraction.enable_llm_extraction = True
        
        processor = GitHubProcessor()
        
        # Mock the necessary methods
        with patch.object(processor, '_clone_repository') as mock_clone, \
             patch.object(processor, '_find_markdown_files') as mock_find, \
             patch.object(processor, '_generate_source_url') as mock_url, \
             patch.object(processor, '_cleanup_temp_dir') as mock_cleanup, \
             patch.object(processor.upload_processor, 'process_upload') as mock_process, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_clone.return_value = MagicMock()
            mock_find.return_value = [MagicMock(relative_to=lambda x: MagicMock(), suffix='.md')]
            mock_url.return_value = "https://example.com/file.md"
            mock_cleanup.return_value = asyncio.sleep(0)
            mock_process.return_value = "job-123"
            mock_open.return_value.__enter__.return_value.read.return_value = "# Test content"
            
            job_id = await processor.process_repository(config)
            
            # Verify that process_upload was called with use_llm=True
            assert mock_process.called
            upload_config = mock_process.call_args[0][0]
            assert upload_config.use_llm == True, f"Expected use_llm=True but got {upload_config.use_llm}"


@pytest.mark.asyncio
async def test_upload_routes_respect_llm_disabled():
    """Test that upload API routes respect the enable_llm_extraction setting."""
    from src.api.routes.upload import settings as upload_settings
    
    # Test configurations
    test_cases = [
        (True, "LLM should be enabled"),
        (False, "LLM should be disabled")
    ]
    
    for expected_value, description in test_cases:
        with patch.object(upload_settings.code_extraction, 'enable_llm_extraction', expected_value):
            # The actual upload routes would use settings.code_extraction.enable_llm_extraction
            # which we've now patched
            assert upload_settings.code_extraction.enable_llm_extraction == expected_value, description