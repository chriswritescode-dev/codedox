"""Tests for HTML file upload and processing."""

import asyncio
from pathlib import Path

import pytest

from src.crawler.upload_processor import UploadConfig, UploadProcessor


def test_html_processing():
    """Test HTML processing with BeautifulSoup."""
    from bs4 import BeautifulSoup

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Documentation</title>
        <meta name="description" content="Test description">
    </head>
    <body>
        <h1>Main Title</h1>
        <p>This is a paragraph with <strong>bold</strong> text.</p>
        
        <h2>Code Example</h2>
        <p>Here's how to use it:</p>
        <pre><code class="language-python">
def hello_world():
    print("Hello, world!")
        </code></pre>
        
        <p>Another example:</p>
        <pre><code>
// JavaScript example
console.log("Hello");
        </code></pre>
    </body>
    </html>
    """

    soup = BeautifulSoup(html_content, "html.parser")

    # Check title extraction
    title = soup.find("title")
    assert title and title.get_text() == "Test Documentation"

    # Check text extraction
    text = soup.get_text()
    assert "Main Title" in text
    assert "Code Example" in text
    # Check that code is preserved
    assert "hello_world" in text
    assert "console.log" in text


@pytest.mark.asyncio
async def test_upload_processor_html_file():
    """Test upload processor with HTML file."""
    processor = UploadProcessor()

    html_content = """
    <html>
    <head><title>API Documentation</title></head>
    <body>
        <h1>API Reference</h1>
        <h2>Authentication</h2>
        <p>Use the following code to authenticate:</p>
        <pre><code class="language-python">
import requests

def authenticate(api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    return headers
        </code></pre>
        
        <h2>Making Requests</h2>
        <pre><code class="language-javascript">
fetch('/api/data', {
    method: 'GET',
    headers: { 'Authorization': 'Bearer YOUR_KEY' }
});
        </code></pre>
    </body>
    </html>
    """

    config = UploadConfig(
        name="test-html-upload",
        files=[
            {
                "path": "api.html",
                "content": html_content,
                "source_url": "upload://test/api.html",
                "content_type": "html",
            }
        ],
        use_llm=False,  # Disable LLM for testing
    )

    # Process the file
    result = await processor._process_file(html_content, "upload://test/api.html", "html")

    # Check result
    assert result.title == "API Documentation"
    assert len(result.code_blocks) == 2

    # Check first code block
    assert "authenticate" in result.code_blocks[0].code
    # Language detection is done by LLM, not HTML parsing
    # In test mode with use_llm=False, language will be None
    assert result.code_blocks[0].language is None

    # Check second code block
    assert "fetch" in result.code_blocks[1].code
    # Language detection is done by LLM, not HTML parsing
    assert result.code_blocks[1].language is None

    # Check that markdown content is generated
    assert result.content is not None
    assert "API Reference" in result.content


@pytest.mark.asyncio
async def test_upload_processor_html_file_crawl4ai_failure():
    """Test that HTML processing fails properly when Crawl4AI fails."""
    from src.crawler.upload_processor import UploadProcessor
    from src.crawler.github_processor import UploadConfig
    from unittest.mock import AsyncMock, patch

    processor = UploadProcessor()

    html_content = """
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Test Document</h1>
        <pre><code>test code</code></pre>
    </body>
    </html>
    """

    # Mock Crawl4AI to simulate failure
    with patch("src.crawler.upload_processor.AsyncWebCrawler") as mock_crawler:
        mock_instance = AsyncMock()
        mock_crawler.return_value.__aenter__.return_value = mock_instance

        # Simulate Crawl4AI failure
        mock_result = AsyncMock()
        mock_result.success = False
        mock_instance.arun.return_value = mock_result

        # Process the file - should raise ValueError
        result = await processor._process_file(html_content, "upload://test/fail.html", "html")

        # Check that error is captured in result
        assert result.error is not None
        assert "Crawl4AI processing failed" in result.error
        assert len(result.code_blocks) == 0


@pytest.mark.asyncio
async def test_github_processor_with_html():
    """Test that GitHub processor finds and processes HTML files."""
    from src.crawler.github_processor import GitHubProcessor

    processor = GitHubProcessor()

    # Create a test directory structure
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        (temp_path / "readme.md").write_text("# Project README")
        (temp_path / "docs").mkdir()
        (temp_path / "docs" / "api.html").write_text("""
        <html>
        <body>
            <h1>API Docs</h1>
            <pre><code>GET /api/users</code></pre>
        </body>
        </html>
        """)
        (temp_path / "docs" / "guide.md").write_text("# User Guide")

        # Find documentation files
        files = processor._find_markdown_files(temp_path)

        # Should find all three files
        assert len(files) == 3

        # Check that HTML file is included
        html_files = [f for f in files if f.suffix == ".html"]
        assert len(html_files) == 1
        assert html_files[0].name == "api.html"


if __name__ == "__main__":
    # Run tests
    test_html_processing()
    asyncio.run(test_upload_processor_html_file())
    asyncio.run(test_github_processor_with_html())
    print("All tests passed!")
