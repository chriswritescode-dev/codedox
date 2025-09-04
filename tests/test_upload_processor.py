"""Tests for UploadProcessor."""


import pytest

from src.crawler.upload_processor import UploadProcessor


class TestUploadProcessor:
    """Test upload processor functionality."""

    def test_extract_title_with_h1(self):
        """Test title extraction when content has H1."""
        processor = UploadProcessor()

        content = """# My Document Title
        
Some content here."""
        title = processor._extract_title(content, "upload://test/file.md")
        assert title == "My Document Title"

    def test_extract_title_from_upload_url(self):
        """Test title extraction from upload:// URL when no H1."""
        processor = UploadProcessor()

        content = """Some content without a heading."""

        # Test with file extension
        title = processor._extract_title(content, "upload://test/my-document.md")
        assert title == "my-document"

        # Test without file extension
        title = processor._extract_title(content, "upload://test/another-file")
        assert title == "another-file"

        # Test with nested path
        title = processor._extract_title(content, "upload://source/path/to/file.md")
        assert title == "path/to/file"

    def test_extract_title_from_file_url(self):
        """Test title extraction from file:// URL when no H1."""
        processor = UploadProcessor()

        content = """Some content without a heading."""
        title = processor._extract_title(content, "file:///path/to/document.md")
        assert title == "document.md"

    def test_extract_title_fallback(self):
        """Test fallback to 'Untitled Document' for unknown URL formats."""
        processor = UploadProcessor()

        content = """Some content without a heading."""
        title = processor._extract_title(content, "http://example.com/doc")
        assert title == "Untitled Document"

    def test_extract_title_priority(self):
        """Test that H1 has priority over filename."""
        processor = UploadProcessor()

        content = """# Title from H1
        
Some content."""
        title = processor._extract_title(content, "upload://test/different-name.md")
        assert title == "Title from H1"

    @pytest.mark.asyncio
    async def test_process_file_sets_correct_title(self):
        """Test that _process_file correctly sets document title."""
        processor = UploadProcessor()

        # Test with H1 in content
        content_with_h1 = """# Documentation Title

```python
def hello():
    print("Hello")
```
"""
        result = await processor._process_file(
            content_with_h1, "upload://MyDocs/readme.md", "markdown"
        )
        assert result.title == "Documentation Title"

        # Test without H1, should use filename
        content_no_h1 = """Some content without heading.

```python
def world():
    print("World")
```
"""
        result = await processor._process_file(
            content_no_h1, "upload://MyDocs/api-guide.md", "markdown"
        )
        assert result.title == "api-guide"
